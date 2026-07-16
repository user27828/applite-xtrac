"""Explicit resource limits and bounded execution for PyConvert."""

from __future__ import annotations

import asyncio
from functools import partial
import os
import signal
from typing import Any, Callable, Optional, TypeVar

import anyio
from fastapi import HTTPException, UploadFile


T = TypeVar("T")
MIB = 1024 * 1024


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
    return value


MAX_INPUT_BYTES = _positive_int("APPLITEXTRAC_MAX_INPUT_BYTES", 512 * MIB)
MAX_OUTPUT_BYTES = _positive_int("APPLITEXTRAC_MAX_OUTPUT_BYTES", 512 * MIB)
CONVERSION_TIMEOUT_SECONDS = _positive_int("APPLITEXTRAC_CONVERSION_TIMEOUT", 120)
SUBPROCESS_STDERR_BYTES = _positive_int("APPLITEXTRAC_SUBPROCESS_STDERR_BYTES", 1 * MIB)
SUBPROCESS_STDOUT_BYTES = _positive_int("APPLITEXTRAC_SUBPROCESS_STDOUT_BYTES", MAX_OUTPUT_BYTES)
WORKER_CONCURRENCY = _positive_int("APPLITEXTRAC_WORKER_CONCURRENCY", 2)
RENDER_CONCURRENCY = _positive_int("APPLITEXTRAC_RENDER_CONCURRENCY", 1)

_worker_limiter: Optional[anyio.CapacityLimiter] = None
_render_limiter: Optional[anyio.CapacityLimiter] = None


class ContentLengthLimitMiddleware:
    """Reject oversized declared bodies before Starlette parses multipart data."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            raw_length = dict(scope.get("headers", [])).get(b"content-length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    await self._send_error(send, 400, b"Invalid Content-Length header")
                    return
                if content_length < 0:
                    await self._send_error(send, 400, b"Invalid Content-Length header")
                    return
                if content_length > MAX_INPUT_BYTES:
                    await self._send_error(send, 413, b"Request exceeds the configured size limit")
                    return
        await self.app(scope, receive, send)

    @staticmethod
    async def _send_error(send, status: int, body: bytes) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})


def _get_worker_limiter() -> anyio.CapacityLimiter:
    global _worker_limiter
    if _worker_limiter is None:
        _worker_limiter = anyio.CapacityLimiter(WORKER_CONCURRENCY)
    return _worker_limiter


def _get_render_limiter() -> anyio.CapacityLimiter:
    global _render_limiter
    if _render_limiter is None:
        _render_limiter = anyio.CapacityLimiter(RENDER_CONCURRENCY)
    return _render_limiter


async def run_blocking(function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run native/blocking conversion work under the service's own limiter."""
    return await anyio.to_thread.run_sync(
        partial(function, *args, **kwargs),
        limiter=_get_worker_limiter(),
    )


async def run_render_blocking(function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run high-memory rendering under a separate, stricter limiter."""
    return await anyio.to_thread.run_sync(
        partial(function, *args, **kwargs),
        limiter=_get_render_limiter(),
    )


async def copy_upload_to_path(upload: UploadFile, destination: str) -> int:
    """Copy an upload to disk while enforcing declared and actual byte limits."""
    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > MAX_INPUT_BYTES:
        raise HTTPException(status_code=413, detail="Input exceeds the configured size limit")

    total_bytes = 0
    await upload.seek(0)
    with open(destination, "wb") as destination_file:
        while chunk := await upload.read(MIB):
            total_bytes += len(chunk)
            if total_bytes > MAX_INPUT_BYTES:
                raise HTTPException(status_code=413, detail="Input exceeds the configured size limit")
            destination_file.write(chunk)
    return total_bytes


async def read_upload_bounded(upload: UploadFile) -> bytes:
    """Read transformations that require bytes, with a hard streaming limit."""
    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > MAX_INPUT_BYTES:
        raise HTTPException(status_code=413, detail="Input exceeds the configured size limit")

    chunks = []
    total_bytes = 0
    await upload.seek(0)
    while chunk := await upload.read(MIB):
        total_bytes += len(chunk)
        if total_bytes > MAX_INPUT_BYTES:
            raise HTTPException(status_code=413, detail="Input exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def ensure_output_size(content: bytes) -> bytes:
    """Reject in-memory output before it can exceed the service contract."""
    if len(content) > MAX_OUTPUT_BYTES:
        raise HTTPException(status_code=413, detail="Output exceeds the configured size limit")
    return content


async def _read_stream_bounded(stream: asyncio.StreamReader, limit: int) -> tuple[bytes, bool]:
    retained = bytearray()
    truncated = False
    while chunk := await stream.read(64 * 1024):
        remaining = limit - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True
    return bytes(retained), truncated


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


async def run_subprocess(
    command: list[str],
    *,
    stdout_limit: int = SUBPROCESS_STDOUT_BYTES,
    stderr_limit: int = SUBPROCESS_STDERR_BYTES,
    timeout: int = CONVERSION_TIMEOUT_SECONDS,
) -> tuple[int, bytes, bytes, bool, bool]:
    """Execute a process group with a deadline and bounded captured output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_task = asyncio.create_task(_read_stream_bounded(process.stdout, stdout_limit))
    stderr_task = asyncio.create_task(_read_stream_bounded(process.stderr, stderr_limit))
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except BaseException:
        termination_task = asyncio.create_task(_terminate_process_group(process))
        try:
            await asyncio.shield(termination_task)
        except asyncio.CancelledError:
            # Preserve cancellation, but do not leave the native process group or
            # pipe-reader tasks detached from request ownership.
            await termination_task
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        raise

    stdout, stdout_truncated = await stdout_task
    stderr, stderr_truncated = await stderr_task
    return process.returncode or 0, stdout, stderr, stdout_truncated, stderr_truncated

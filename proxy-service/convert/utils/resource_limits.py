"""Central byte limits and streaming helpers for proxy boundaries."""

from __future__ import annotations

import os
from typing import AsyncIterator, Any

from fastapi import HTTPException, Request, UploadFile
import httpx


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


MAX_REQUEST_BYTES = _positive_int("APPLITEXTRAC_MAX_INPUT_BYTES", 512 * MIB)
MAX_RESPONSE_BYTES = _positive_int("APPLITEXTRAC_MAX_OUTPUT_BYTES", 512 * MIB)
MAX_ERROR_BYTES = _positive_int("APPLITEXTRAC_MAX_ERROR_BYTES", 1 * MIB)


class ContentLengthLimitMiddleware:
    """Reject oversized declared request bodies before multipart parsing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw_length = headers.get(b"content-length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    await self._send_error(send, 400, b"Invalid Content-Length header")
                    return
                if content_length < 0:
                    await self._send_error(send, 400, b"Invalid Content-Length header")
                    return
                if content_length > MAX_REQUEST_BYTES:
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


def validate_request_content_length(request: Request) -> None:
    """Reject an oversized declared body before parsing multipart content."""
    content_length = request.headers.get("Content-Length")
    if content_length is None:
        return
    try:
        declared_size = int(content_length)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc
    if declared_size < 0:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header")
    if declared_size > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Request exceeds the configured size limit")


def validate_upload_size(upload: UploadFile) -> None:
    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")


async def bounded_request_stream(request: Request) -> AsyncIterator[bytes]:
    """Forward an unparsed body with an actual-byte limit."""
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="Request exceeds the configured size limit")
        yield chunk


async def read_upload_bounded(upload: UploadFile) -> bytes:
    """Buffer only local transformations that require bytes, under a hard limit."""
    validate_upload_size(upload)
    await upload.seek(0)
    chunks = []
    total_bytes = 0
    while chunk := await upload.read(MIB):
        total_bytes += len(chunk)
        if total_bytes > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


async def bounded_response_stream(response: httpx.Response) -> AsyncIterator[bytes]:
    """Stream and close a downstream response with an actual-byte limit."""
    total_bytes = 0
    try:
        try:
            buffered_content = response.content
        except (httpx.ResponseNotRead, AttributeError):
            buffered_content = None
        if buffered_content is not None:
            if len(buffered_content) > MAX_RESPONSE_BYTES:
                raise HTTPException(status_code=502, detail="Downstream response exceeds the configured size limit")
            yield buffered_content
            return
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_RESPONSE_BYTES:
            raise HTTPException(status_code=502, detail="Downstream response exceeds the configured size limit")
        async for chunk in response.aiter_bytes():
            total_bytes += len(chunk)
            if total_bytes > MAX_RESPONSE_BYTES:
                raise HTTPException(status_code=502, detail="Downstream response exceeds the configured size limit")
            yield chunk
    finally:
        if hasattr(response, "aclose"):
            await response.aclose()


async def read_response_bounded(response: httpx.Response, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    """Buffer only transformations that inherently require full output."""
    chunks = []
    total_bytes = 0
    try:
        try:
            buffered_content = response.content
        except (httpx.ResponseNotRead, AttributeError):
            buffered_content = None
        if buffered_content is not None:
            if len(buffered_content) > limit:
                raise HTTPException(status_code=502, detail="Downstream response exceeds the configured size limit")
            return buffered_content
        async for chunk in response.aiter_bytes():
            total_bytes += len(chunk)
            if total_bytes > limit:
                raise HTTPException(status_code=502, detail="Downstream response exceeds the configured size limit")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if hasattr(response, "aclose"):
            await response.aclose()


async def read_streaming_response_bounded(response: Any, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    """Consume an internal Starlette response and retain its cleanup semantics."""
    chunks = []
    total_bytes = 0
    try:
        async for chunk in response.body_iterator:
            content = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
            total_bytes += len(content)
            if total_bytes > limit:
                raise HTTPException(status_code=502, detail="Internal response exceeds the configured size limit")
            chunks.append(content)
        return b"".join(chunks)
    finally:
        background = getattr(response, "background", None)
        if background is not None:
            response.background = None
            await background()

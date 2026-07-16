"""Focused regression coverage for bounded resource ownership."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys

import httpx
import pytest

from convert.config import ConversionService
from convert.utils.conversion_core import _defer_input_cleanup
from convert.utils.http_client import HTTPClientFactory
from convert.utils.resource_limits import bounded_response_stream
from convert.utils.screenshot_utils import copy_response_to_spooled_pdf
from convert.utils.temp_file_manager import TempFileManager
from convert.utils.url_processor import TempFileInput, URLFileWrapper, URLProcessor
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask


REPOSITORY_ROOT = Path(__file__).parents[3]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_temp_manager_uses_unique_paths_and_deregisters_cleanup(tmp_path):
    manager = TempFileManager(base_dir=str(tmp_path), service="url_fetcher")

    files = [
        manager.create_temp_file(content=b"payload", filename="same-name.pdf")
        for _ in range(8)
    ]

    assert len({temp_file.path for temp_file in files}) == len(files)
    assert all(Path(temp_file.path).read_bytes() == b"payload" for temp_file in files)
    manager.cleanup_all()
    assert manager.get_stats()["file_count"] == 0
    assert not any(Path(temp_file.path).exists() for temp_file in files)


@pytest.mark.asyncio
async def test_temp_url_input_closes_every_wrapper_and_cleans_once(tmp_path):
    manager = TempFileManager(base_dir=str(tmp_path), service="url_fetcher")
    temp_file = manager.create_temp_file(content=b"downloaded", filename="document.pdf")
    owner_wrapper = URLFileWrapper(temp_file.path, "document.pdf", "application/pdf")
    conversion_input = TempFileInput(
        owner_wrapper,
        {"temp_file_path": temp_file.path},
        manager,
    )

    first_wrapper = await conversion_input.get_for_service(ConversionService.PANDOC)
    second_wrapper = await conversion_input.get_for_service(ConversionService.LIBREOFFICE)
    assert await first_wrapper.read() == b"downloaded"
    assert await second_wrapper.read() == b"downloaded"

    await conversion_input.cleanup()
    await conversion_input.cleanup()

    assert not Path(temp_file.path).exists()
    assert manager.get_stats()["file_count"] == 0
    assert first_wrapper._file is None
    assert second_wrapper._file is None


@pytest.mark.asyncio
async def test_url_fetch_failure_removes_partial_file(tmp_path, monkeypatch):
    manager = TempFileManager(base_dir=str(tmp_path), service="url_fetcher")
    processor = URLProcessor()

    monkeypatch.setattr(
        processor.file_manager,
        "create_empty_temp_file",
        lambda filename: (manager, manager.create_temp_file(filename=filename)),
    )

    async def fail_after_partial_write(_url, destination, **_kwargs):
        Path(destination).write_bytes(b"partial")
        raise asyncio.CancelledError

    monkeypatch.setattr(processor.fetcher, "fetch_to_file", fail_after_partial_write)

    with pytest.raises(asyncio.CancelledError):
        await processor._fetch_to_temp_file("https://example.test/document.pdf")

    assert manager.get_stats()["file_count"] == 0
    assert not list(manager.service_dir.iterdir())


@pytest.mark.asyncio
async def test_response_background_defers_input_cleanup():
    class ConversionInputStub:
        cleaned = False

        async def cleanup(self):
            self.cleaned = True

    conversion_input = ConversionInputStub()
    response = _defer_input_cleanup(StreamingResponse(iter([b"result"])), conversion_input)

    assert conversion_input.cleaned is False
    await response.background()
    assert conversion_input.cleaned is True


@pytest.mark.asyncio
async def test_intermediate_response_consumption_runs_background_cleanup():
    state = {"cleaned": False}

    async def cleanup():
        state["cleaned"] = True

    response = StreamingResponse(
        iter([b"%PDF-test"]),
        background=BackgroundTask(cleanup),
    )

    intermediate = await copy_response_to_spooled_pdf(response)
    try:
        assert intermediate.read() == b"%PDF-test"
        assert state["cleaned"] is True
        assert response.background is None
    finally:
        intermediate.close()


def test_timeout_configuration_rejects_unlimited_zero(monkeypatch):
    monkeypatch.setenv("APPLITEXTRAC_HTTP_TIMEOUT", "0")
    factory = HTTPClientFactory()

    with pytest.raises(RuntimeError):
        factory._get_timeout()


@pytest.mark.asyncio
async def test_bounded_response_stream_closes_downstream_response():
    class TrackingStream(httpx.AsyncByteStream):
        def __init__(self):
            self.closed = False

        async def __aiter__(self):
            yield b"one"
            yield b"two"

        async def aclose(self):
            self.closed = True

    stream = TrackingStream()
    response = httpx.Response(200, stream=stream)

    assert b"".join([chunk async for chunk in bounded_response_stream(response)]) == b"onetwo"
    assert stream.closed is True


def test_declared_oversized_request_is_rejected_before_parsing(client):
    response = client.post(
        "/pandoc",
        headers={"Content-Length": str(513 * 1024 * 1024)},
        content=b"",
    )

    assert response.status_code == 413


def test_pyconvert_temp_manager_is_collision_free(tmp_path):
    module = _load_module(
        "pyconvert_temp_manager_test",
        REPOSITORY_ROOT / "pyconvert-service" / "utils" / "temp_file_manager.py",
    )
    manager = module.TempFileManager(base_dir=str(tmp_path), service="pandoc")

    first = manager.create_temp_file(content=b"first", filename="resume.docx")
    second = manager.create_temp_file(content=b"second", filename="resume.docx")

    assert first.path != second.path
    manager.cleanup_all()
    assert manager.get_stats()["file_count"] == 0


@pytest.mark.asyncio
async def test_subprocess_output_is_capped_and_timeout_kills_group():
    module = _load_module(
        "pyconvert_resource_control_test",
        REPOSITORY_ROOT / "pyconvert-service" / "utils" / "resource_control.py",
    )

    return_code, stdout, stderr, stdout_truncated, stderr_truncated = await module.run_subprocess(
        [sys.executable, "-c", "print('x' * 1000)"],
        stdout_limit=32,
        stderr_limit=32,
        timeout=5,
    )
    assert return_code == 0
    assert len(stdout) == 32
    assert stdout_truncated is True
    assert stderr == b""
    assert stderr_truncated is False

    with pytest.raises(asyncio.TimeoutError):
        await module.run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=0.05,
        )

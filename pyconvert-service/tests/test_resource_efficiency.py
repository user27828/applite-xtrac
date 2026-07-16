"""PyConvert request-lifecycle regressions."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import asyncio
import threading
import time

import anyio
from fastapi.testclient import TestClient
import pytest

import app as pyconvert_app
from utils import resource_control


@pytest.fixture
def isolated_temp_manager(tmp_path, monkeypatch):
    original_manager = pyconvert_app.TempFileManager

    class IsolatedManager(original_manager):
        def __init__(self, service="pandoc"):
            super().__init__(base_dir=str(tmp_path), service=service)

    monkeypatch.setattr(pyconvert_app, "TempFileManager", IsolatedManager)
    return tmp_path


def test_concurrent_same_name_pandoc_requests_leave_no_temp_files(
    isolated_temp_manager,
    monkeypatch,
):
    async def fake_subprocess(command, **_kwargs):
        output_path = command[command.index("-o") + 1]
        Path(output_path).write_bytes(b"converted")
        return 0, b"", b"", False, False

    monkeypatch.setattr(pyconvert_app, "run_subprocess", fake_subprocess)

    def convert_once(_index):
        with TestClient(pyconvert_app.app) as client:
            response = client.post(
                "/pandoc",
                files={"file": ("same-name.md", b"# heading", "text/markdown")},
                data={"output_format": "html"},
            )
            return response.status_code, response.content

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(convert_once, range(12)))

    assert results == [(200, b"converted")] * 12
    assert not list(isolated_temp_manager.rglob("*.*"))


def test_pandoc_error_cleans_request_files(isolated_temp_manager, monkeypatch):
    async def fail_subprocess(_command, **_kwargs):
        raise RuntimeError("conversion failed")

    monkeypatch.setattr(pyconvert_app, "run_subprocess", fail_subprocess)

    with TestClient(pyconvert_app.app) as client:
        response = client.post(
            "/pandoc",
            files={"file": ("failure.md", b"content", "text/markdown")},
            data={"output_format": "html"},
        )

    assert response.status_code == 500
    assert not list(isolated_temp_manager.rglob("*.*"))


@pytest.mark.asyncio
async def test_render_admission_limiter_serializes_native_work(monkeypatch):
    monkeypatch.setattr(resource_control, "_render_limiter", anyio.CapacityLimiter(1))
    state = {"active": 0, "maximum": 0}
    lock = threading.Lock()

    def render_job():
        with lock:
            state["active"] += 1
            state["maximum"] = max(state["maximum"], state["active"])
        time.sleep(0.05)
        with lock:
            state["active"] -= 1

    await asyncio.gather(
        resource_control.run_render_blocking(render_job),
        resource_control.run_render_blocking(render_job),
        resource_control.run_render_blocking(render_job),
    )

    assert state["maximum"] == 1

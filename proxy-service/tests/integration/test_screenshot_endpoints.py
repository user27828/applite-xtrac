"""End-to-end tests for the public screenshot and thumbnail endpoints.

These tests intentionally use the real proxy URL. They must not be replaced
with TestClient, mocked service clients, or direct utility-function calls.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.service,
    pytest.mark.conversion,
]


def _upload(client, path: Path, endpoint: str, data: dict | None = None):
    """POST one fixture to the real public proxy endpoint."""
    with path.open("rb") as file_handle:
        response = client.post(
            endpoint,
            files={"file": (path.name, file_handle, "application/octet-stream")},
            data=data or {},
        )
    assert response.status_code == 200, response.text
    return response


def _png_dimensions(content: bytes) -> tuple[int, int]:
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")


def _jpeg_dimensions(content: bytes) -> tuple[int, int]:
    assert content.startswith(b"\xff\xd8")
    offset = 2
    sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))

    while offset < len(content):
        while offset < len(content) and content[offset] != 0xFF:
            offset += 1
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break

        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break

        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if marker in sof_markers:
            assert offset + 7 <= len(content)
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            return width, height
        offset += segment_length

    raise AssertionError("JPEG dimensions were not found")


def test_screenshot_page_one_returns_real_jpeg_with_bounded_width(
    integration_client,
    fixtures_dir,
):
    response = _upload(
        integration_client,
        fixtures_dir / "sample.pdf",
        "/convert/screenshot",
        {"page": "1", "width": "320", "format": "jpg", "quality": "80"},
    )

    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["x-conversion-service"] == "PYMUPDF_RENDER"
    width, height = _jpeg_dimensions(response.content)
    assert 0 < width <= 320
    assert height > 0


def test_screenshot_page_x_returns_real_png_from_multipage_input(
    integration_client,
    fixtures_dir,
):
    response = _upload(
        integration_client,
        fixtures_dir / "sample.tiff",
        "/convert/screenshot",
        {"page": "2", "width": "320", "format": "png"},
    )

    assert response.headers["content-type"].startswith("image/png")
    width, height = _png_dimensions(response.content)
    assert 0 < width <= 320
    assert height > 0


def test_screenshot_all_returns_real_zip_with_each_page(
    integration_client,
    fixtures_dir,
):
    response = _upload(
        integration_client,
        fixtures_dir / "sample.tiff",
        "/convert/screenshot",
        {"page": "all", "width": "320", "format": "jpg", "quality": "80"},
    )

    assert response.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["sample_page_0001.jpg", "sample_page_0002.jpg"]
        for name in archive.namelist():
            width, height = _jpeg_dimensions(archive.read(name))
            assert 0 < width <= 320
            assert height > 0


def test_thumb_defaults_match_explicit_jpg_quality_80(
    integration_client,
    fixtures_dir,
):
    default_response = _upload(
        integration_client,
        fixtures_dir / "sample.pdf",
        "/convert/thumb",
    )
    explicit_response = _upload(
        integration_client,
        fixtures_dir / "sample.pdf",
        "/convert/thumb",
        {"page": "1", "width": "480", "format": "jpg", "quality": "80"},
    )

    assert default_response.headers["content-type"].startswith("image/jpeg")
    assert default_response.content == explicit_response.content
    width, height = _jpeg_dimensions(default_response.content)
    assert 0 < width <= 480
    assert height > 0


def test_png_quality_is_rejected_by_real_endpoint(
    integration_client,
    fixtures_dir,
):
    with (fixtures_dir / "sample.pdf").open("rb") as file_handle:
        response = integration_client.post(
            "/convert/screenshot",
            files={"file": ("sample.pdf", file_handle, "application/pdf")},
            data={"page": "1", "width": "320", "format": "png", "quality": "80"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_PARAMETER"

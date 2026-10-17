"""OCR page-cap regressions at the Unstructured receiver boundary."""

import asyncio
from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from convert.config import ConversionService
from convert.utils import conversion_core


def test_unstructured_ocr_rejects_over_limit_before_dispatch(client, monkeypatch):
    calls = {"page_count": 0, "ocr": 0}

    async def rendered_page_count(*_args, **_kwargs):
        calls["page_count"] += 1
        return 16

    async def ocr_post(*_args, **_kwargs):
        calls["ocr"] += 1
        return httpx.Response(200, json=[])

    monkeypatch.setattr(conversion_core, "_count_rendered_pages", rendered_page_count)
    monkeypatch.setattr(conversion_core, "_post_streaming", ocr_post)

    response = client.post(
        "/convert/docx-md",
        files={"file": ("resume.docx", b"test document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"service": "unstructured-io", "max_pages": "15", "strategy": "ocr_only"},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "RESUME_CV_PAGE_LIMIT_EXCEEDED"
    assert response.json()["detail"]["page_count"] == 16
    assert response.json()["detail"]["max_pages"] == 15
    assert calls == {"page_count": 1, "ocr": 0}


def test_unstructured_ocr_at_limit_does_not_forward_receiver_only_parameter(client, monkeypatch):
    captured = {}

    async def rendered_page_count(*_args, **_kwargs):
        return 15

    async def ocr_post(_client, _url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(conversion_core, "_count_rendered_pages", rendered_page_count)
    monkeypatch.setattr(conversion_core, "_post_streaming", ocr_post)

    response = client.post(
        "/convert/docx-md",
        files={"file": ("resume.docx", b"test document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"service": "unstructured-io", "max_pages": "15", "strategy": "ocr_only"},
    )

    assert response.status_code == 200
    assert "max_pages" not in captured["data"]


def test_ocr_page_limit_rejects_invalid_values_before_counting(client, monkeypatch):
    async def fail_if_counted(*_args, **_kwargs):
        raise AssertionError("invalid page limit must be rejected before rendering")

    monkeypatch.setattr(conversion_core, "_count_rendered_pages", fail_if_counted)

    response = client.post(
        "/convert/docx-md",
        files={"file": ("resume.docx", b"test document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"service": "unstructured-io", "max_pages": "15.5", "strategy": "ocr_only"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_PARAMETER"


def test_docx_page_count_renders_to_pdf_then_uses_metadata_endpoint(monkeypatch):
    calls = []

    async def render_to_pdf(**kwargs):
        calls.append(("render", kwargs["service"], kwargs["output_format"]))
        return StreamingResponse(BytesIO(b"rendered pdf"), media_type="application/pdf")

    async def count_pdf(client, url, **kwargs):
        calls.append(("count", url, kwargs["files"]["file"][0]))
        return httpx.Response(200, json={"page_count": 2})

    class RequestStub:
        class AppStub:
            class StateStub:
                pyconvert_client = object()

            state = StateStub()

        app = AppStub()

    class UploadStub:
        filename = "resume.docx"

    monkeypatch.setattr(conversion_core, "_convert_file_impl", render_to_pdf)
    monkeypatch.setattr(conversion_core, "_post_streaming", count_pdf)

    page_count = asyncio.run(
        conversion_core._count_rendered_pages(
            RequestStub(), UploadStub(), "docx", 15
        )
    )

    assert page_count == 2
    assert calls[0] == ("render", ConversionService.GOTENBERG, "pdf")
    assert calls[1][0] == "count"
    assert calls[1][1].endswith("/pymupdf/pdf-info")
    assert calls[1][2] == "resume.pdf"


def test_pdf_page_count_normalizes_upload_name_to_pdf(monkeypatch):
    captured = {}

    async def count_pdf(_client, _url, **kwargs):
        captured["filename"] = kwargs["files"]["file"][0]
        return httpx.Response(200, json={"page_count": 1})

    class RequestStub:
        class AppStub:
            class StateStub:
                pyconvert_client = object()

            state = StateStub()

        app = AppStub()

    class UploadStub:
        filename = "resume.bin"
        file = BytesIO(b"pdf bytes")

        async def seek(self, position):
            self.file.seek(position)

    monkeypatch.setattr(conversion_core, "_post_streaming", count_pdf)

    page_count = asyncio.run(
        conversion_core._count_rendered_pages(
            RequestStub(), UploadStub(), "pdf", 15
        )
    )

    assert page_count == 1
    assert captured["filename"] == "resume.pdf"


def test_page_count_unavailable_fails_closed(monkeypatch):
    async def render_to_pdf(**_kwargs):
        raise RuntimeError("renderer unavailable")

    class RequestStub:
        app = type("AppStub", (), {"state": type("StateStub", (), {})()})()

    class UploadStub:
        filename = "resume.docx"

    monkeypatch.setattr(conversion_core, "_convert_file_impl", render_to_pdf)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            conversion_core._count_rendered_pages(
                RequestStub(), UploadStub(), "docx", 15
            )
        )

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "RESUME_CV_PAGE_COUNT_UNAVAILABLE"

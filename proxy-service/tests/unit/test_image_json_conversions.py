"""Unit tests for image conversion support."""

from io import BytesIO

from fastapi.responses import StreamingResponse

from convert.config import ConversionService
from convert.utils.conversion_lookup import get_conversion_methods, get_supported_conversions


class FakeResponse:
    """Minimal async response stub for mocked service calls."""

    def __init__(self, status_code=200, content=b'[{"type":"Title","text":"Sample OCR text"}]', text='[{"type":"Title","text":"Sample OCR text"}]'):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeAsyncClient:
    """Minimal async client stub for Unstructured IO endpoint tests."""

    async def post(self, url, files=None, data=None, json=None):
        return FakeResponse()


def test_image_formats_exposed_in_supported_conversions():
    """Supported conversions should list direct image-to-JSON routes."""
    supported = get_supported_conversions()

    assert "jpg" in supported
    assert "jpeg" in supported
    assert "png" in supported
    assert "json" in supported["jpg"]
    assert "json" in supported["jpeg"]
    assert "json" in supported["png"]


def test_jpg_json_uses_unstructured_io():
    """Lookup for JPG to JSON should resolve to Unstructured IO."""
    methods = get_conversion_methods("jpg", "json")

    assert methods == [
        (ConversionService.UNSTRUCTURED_IO, "Image OCR and structure extraction"),
    ]


def test_jpg_json_endpoint_returns_json(client, monkeypatch):
    """The dynamic JPG to JSON endpoint should route through the Unstructured path."""
    from convert.utils import conversion_core

    async def fake_get_service_client(service, request):
        assert service == ConversionService.UNSTRUCTURED_IO
        return FakeAsyncClient()

    monkeypatch.setattr(conversion_core, "_get_service_client", fake_get_service_client)

    response = client.post(
        "/convert/jpg-json",
        files={"file": ("scan.jpg", BytesIO(b"fake-jpeg-bytes"), "image/jpeg")},
        data={"strategy": "hi_res", "languages": "eng+fra+deu+spa+por"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-conversion-service"] == "unstructured-io"
    assert response.json() == [{"type": "Title", "text": "Sample OCR text"}]


def test_image_formats_exposed_for_pdf_conversions():
    """Supported conversions should list direct image-to-PDF routes."""
    supported = get_supported_conversions()

    assert "pdf" in supported["jpg"]
    assert "pdf" in supported["jpeg"]
    assert "pdf" in supported["png"]
    assert "pdf" in supported["tiff"]
    assert "pdf" in supported["heic"]


def test_heic_pdf_uses_weasyprint_first():
    """HEIC to PDF should prefer WeasyPrint and fall back to Gotenberg."""
    methods = get_conversion_methods("heic", "pdf")

    assert methods[0] == (ConversionService.WEASYPRINT, "Image to PDF using WeasyPrint")
    assert methods[1] == (ConversionService.GOTENBERG, "Image to PDF using Gotenberg")


def test_jpg_pdf_endpoint_returns_pdf(client, monkeypatch):
    """The dynamic JPG to PDF endpoint should use the image-PDF rendering path."""
    from convert.utils import conversion_core

    monkeypatch.setattr(conversion_core, "build_image_pdf_html", lambda *args, **kwargs: "<html><body><img src='data:image/png;base64,AA=='></body></html>")

    async def fake_proxy_pyconvert(*args, **kwargs):
        return StreamingResponse(
            BytesIO(b"%PDF-1.7\n%mock pdf\n"),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=scan.pdf",
                "X-Conversion-Service": "weasyprint",
            },
        )

    monkeypatch.setattr(conversion_core, "_proxy_pyconvert", fake_proxy_pyconvert)

    response = client.post(
        "/convert/jpg-pdf",
        files={"file": ("scan.jpg", BytesIO(b"fake-jpeg-bytes"), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
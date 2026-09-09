"""Tests for explicit conversion-service selection on dynamic endpoints."""

import asyncio

import pytest
from fastapi import HTTPException

from convert import router as conversion_router
from convert.config import ConversionService


class _FormRequest:
    def __init__(self, form_data):
        self.form_data = form_data

    async def form(self):
        return self.form_data


def test_dynamic_endpoint_forwards_requested_service_and_removes_form_control(
    monkeypatch,
):
    captured = {}

    async def fake_convert(*args, **kwargs):
        captured.update(kwargs)
        return "converted"

    monkeypatch.setattr(conversion_router, "_convert_file", fake_convert)

    response = asyncio.run(
        conversion_router.convert_dynamic(
            _FormRequest(
                {
                    "file": object(),
                    "service": " libreoffice ",
                    "opts[]": "--filter=writer_pdf_Export",
                }
            ),
            "odt",
            "pdf",
            object(),
        )
    )

    assert response == "converted"
    assert captured["service"] == ConversionService.LIBREOFFICE
    assert captured["extra_params"] == {"opts[]": "--filter=writer_pdf_Export"}


def test_dynamic_endpoint_rejects_service_not_in_conversion_matrix(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("conversion should not start for an unsupported service")

    monkeypatch.setattr(conversion_router, "_convert_file", fail_if_called)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            conversion_router.convert_dynamic(
                _FormRequest({"file": object(), "service": "gotenberg"}),
                "odt",
                "docx",
                object(),
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail["error"] == "CONVERSION_NOT_SUPPORTED"
    assert error.value.detail["service"] == "gotenberg"

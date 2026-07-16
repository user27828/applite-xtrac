"""Helpers for the public screenshot and thumbnail conversion endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .error_handling import ErrorCode, create_http_exception
from .resource_limits import MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES


MAX_SCREENSHOT_INPUT_BYTES = MAX_REQUEST_BYTES
MAX_INTERMEDIATE_PDF_BYTES = MAX_RESPONSE_BYTES
SPOOLED_MEMORY_LIMIT = 1024 * 1024
DEFAULT_SCREENSHOT_WIDTH = 2_048
DEFAULT_THUMB_WIDTH = 480
DEFAULT_THUMB_JPEG_QUALITY = 80
MIN_RENDER_WIDTH = 64
MAX_RENDER_WIDTH = 4_096


def get_input_format(filename: str) -> str:
    """Return a validated extension suitable for a conversion-matrix lookup."""
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if not suffix or not suffix.isalnum():
        raise create_http_exception(
            ErrorCode.INVALID_FILE,
            details="A filename with a supported document extension is required",
        )
    return suffix


def validate_upload_size(file: UploadFile) -> None:
    """Reject inputs above the screenshot API's hard size limit without reading them."""
    declared_size = getattr(file, "size", None)
    if isinstance(declared_size, int):
        size = declared_size
    else:
        position = file.file.tell()
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(position)

    if size > MAX_SCREENSHOT_INPUT_BYTES:
        raise create_http_exception(
            ErrorCode.FILE_TOO_LARGE,
            details=f"Input exceeds the {MAX_SCREENSHOT_INPUT_BYTES // (1024 * 1024)} MiB limit",
        )


def validate_render_request(page: str, width: int, image_format: str, quality: int | None) -> None:
    """Perform inexpensive public validation before any document conversion starts."""
    normalized_page = str(page).strip().lower()
    if normalized_page != "all":
        try:
            if int(normalized_page) < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise create_http_exception(
                ErrorCode.INVALID_PARAMETER,
                details="page must be a positive 1-based number or 'all'",
            ) from exc

    if not MIN_RENDER_WIDTH <= width <= MAX_RENDER_WIDTH:
        raise create_http_exception(
            ErrorCode.PARAMETER_OUT_OF_RANGE,
            details=f"width must be between {MIN_RENDER_WIDTH} and {MAX_RENDER_WIDTH} pixels",
        )

    normalized_format = image_format.strip().lower()
    if normalized_format not in {"png", "jpg", "jpeg"}:
        raise create_http_exception(
            ErrorCode.INVALID_FORMAT,
            details="format must be either 'png' or 'jpg'",
        )
    if normalized_format == "png" and quality is not None:
        raise create_http_exception(
            ErrorCode.INVALID_PARAMETER,
            details="quality is only applicable to JPG output",
        )
    if quality is not None and not 1 <= quality <= 100:
        raise create_http_exception(
            ErrorCode.PARAMETER_OUT_OF_RANGE,
            details="quality must be between 1 and 100",
        )


async def copy_response_to_spooled_pdf(response: StreamingResponse) -> BinaryIO:
    """Copy a conversion response to a bounded, disk-spilling temporary PDF."""
    temporary_pdf = tempfile.SpooledTemporaryFile(max_size=SPOOLED_MEMORY_LIMIT, mode="w+b")
    total_bytes = 0

    try:
        try:
            async for chunk in response.body_iterator:
                content = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
                total_bytes += len(content)
                if total_bytes > MAX_INTERMEDIATE_PDF_BYTES:
                    raise create_http_exception(
                        ErrorCode.FILE_TOO_LARGE,
                        details=(
                            f"Converted PDF exceeds the "
                            f"{MAX_INTERMEDIATE_PDF_BYTES // (1024 * 1024)} MiB limit"
                        ),
                    )
                temporary_pdf.write(content)
        finally:
            background = response.background
            if background is not None:
                response.background = None
                await background()
        temporary_pdf.seek(0)
        return temporary_pdf
    except BaseException:
        temporary_pdf.close()
        raise


def raise_pyconvert_error(status_code: int, body: bytes) -> None:
    """Translate a bounded internal-service error into a public HTTP error."""
    detail = body.decode("utf-8", errors="replace")[:500]
    raise HTTPException(status_code=status_code, detail=f"PyMuPDF rendering failed: {detail}")

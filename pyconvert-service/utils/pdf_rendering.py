"""Bounded page-image rendering for PDF documents."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import sqrt
from pathlib import Path
import os
import re
import tempfile
from typing import Optional, Sequence
from zipfile import ZIP_STORED, ZipFile

from fastapi import HTTPException

from .resource_control import MAX_OUTPUT_BYTES


MAX_INPUT_BYTES = 512 * 1024 * 1024
MAX_ALL_PAGE_COUNT = 2_000
MIN_WIDTH = 64
MAX_WIDTH = 4_096
DEFAULT_SCREENSHOT_WIDTH = 2_048
DEFAULT_THUMB_WIDTH = 480
DEFAULT_JPEG_QUALITY = 85
MAX_PAGE_PIXELS = 32_000_000
MAX_SINGLE_IMAGE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class RenderOptions:
    """Validated output settings for a PDF page-rendering request."""

    pages: str
    max_width: int
    image_format: str
    quality: Optional[int]


@dataclass(frozen=True)
class RenderResult:
    """The single-image bytes or archive path produced by a render operation."""

    page_number: Optional[int] = None
    image_bytes: Optional[bytes] = None
    archive_path: Optional[str] = None


def validate_render_options(
    page: str,
    max_width: int,
    image_format: str,
    quality: Optional[int],
) -> RenderOptions:
    """Validate public rendering parameters before opening a PDF."""
    normalized_page = str(page).strip().lower()
    if normalized_page != "all":
        try:
            if int(normalized_page) < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="page must be a positive 1-based number or 'all'") from exc

    if not MIN_WIDTH <= max_width <= MAX_WIDTH:
        raise HTTPException(
            status_code=400,
            detail=f"max_width must be between {MIN_WIDTH} and {MAX_WIDTH} pixels",
        )

    normalized_format = image_format.strip().lower()
    if normalized_format == "jpeg":
        normalized_format = "jpg"
    if normalized_format not in {"png", "jpg"}:
        raise HTTPException(status_code=400, detail="format must be either 'png' or 'jpg'")

    if normalized_format == "png":
        if quality is not None:
            raise HTTPException(status_code=400, detail="quality is only applicable to JPG output")
        normalized_quality = None
    else:
        normalized_quality = DEFAULT_JPEG_QUALITY if quality is None else quality
        if not 1 <= normalized_quality <= 100:
            raise HTTPException(status_code=400, detail="quality must be between 1 and 100")

    return RenderOptions(
        pages=normalized_page,
        max_width=max_width,
        image_format=normalized_format,
        quality=normalized_quality,
    )


def render_pdf_pages(pdf_path: str, original_filename: str, options: RenderOptions) -> RenderResult:
    """Render selected PDF pages without retaining all rendered pages in memory."""
    try:
        import fitz
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="PyMuPDF library is not available") from exc

    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to open PDF: {exc}") from exc

    try:
        if document.needs_pass:
            raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported")

        page_numbers = _select_pages(document.page_count, options.pages)
        if options.pages != "all":
            page_number = page_numbers[0]
            image_bytes = _render_page(document, page_number, options, fitz)
            return RenderResult(page_number=page_number, image_bytes=image_bytes)

        archive_path = _render_archive(document, page_numbers, original_filename, options, fitz)
        return RenderResult(archive_path=archive_path)
    finally:
        document.close()


def extract_pdf_content(pdf_path: str, original_filename: str, output_format: str) -> bytes:
    """Extract bounded HTML or text with exception-safe native document ownership."""
    try:
        import fitz
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="PyMuPDF library is not available") from exc

    if output_format not in {"html", "txt"}:
        raise ValueError(f"Unsupported PyMuPDF extraction format: {output_format}")

    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to open PDF: {exc}") from exc

    try:
        if document.needs_pass:
            raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported")
        if document.page_count > MAX_ALL_PAGE_COUNT:
            raise HTTPException(
                status_code=400,
                detail=f"PDF extraction supports at most {MAX_ALL_PAGE_COUNT} pages",
            )

        if output_format == "html":
            parts = [
                "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">",
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
                "<title>PDF to HTML Conversion</title><style>",
                "body{font-family:Arial,sans-serif;margin:20px}.page{margin-bottom:20px;",
                "border:1px solid #ccc;padding:10px}</style></head><body>",
                f"<h1>PDF to HTML Conversion</h1><p>Converted from: {escape(original_filename)}</p>",
            ]
            total_bytes = sum(len(part.encode("utf-8")) for part in parts)
            for page_number in range(document.page_count):
                page_html = document.load_page(page_number).get_text("html")
                part = f"<div class='page' data-page='{page_number + 1}'>\n{page_html}\n</div>\n"
                total_bytes += len(part.encode("utf-8"))
                if total_bytes > MAX_OUTPUT_BYTES:
                    raise HTTPException(status_code=413, detail="Extracted output exceeds the configured size limit")
                parts.append(part)
            parts.append("</body></html>")
        else:
            parts = []
            total_bytes = 0
            for page_number in range(document.page_count):
                page_text = document.load_page(page_number).get_text()
                part = f"--- Page {page_number + 1} ---\n{page_text}\n\n"
                total_bytes += len(part.encode("utf-8"))
                if total_bytes > MAX_OUTPUT_BYTES:
                    raise HTTPException(status_code=413, detail="Extracted output exceeds the configured size limit")
                parts.append(part)

        output = "".join(parts).encode("utf-8")
        if len(output) > MAX_OUTPUT_BYTES:
            raise HTTPException(status_code=413, detail="Extracted output exceeds the configured size limit")
        return output
    finally:
        document.close()


def _select_pages(page_count: int, requested_page: str) -> Sequence[int]:
    if page_count < 1:
        raise HTTPException(status_code=400, detail="PDF does not contain any pages")

    if requested_page == "all":
        if page_count > MAX_ALL_PAGE_COUNT:
            raise HTTPException(
                status_code=400,
                detail=f"page=all supports at most {MAX_ALL_PAGE_COUNT} pages; this PDF has {page_count}",
            )
        return range(1, page_count + 1)

    page_number = int(requested_page)
    if page_number > page_count:
        raise HTTPException(status_code=400, detail=f"page must be between 1 and {page_count}")
    return (page_number,)


def _render_page(document, page_number: int, options: RenderOptions, fitz) -> bytes:
    page = document.load_page(page_number - 1)
    rect = page.rect
    if rect.width <= 0 or rect.height <= 0:
        raise HTTPException(status_code=400, detail=f"Page {page_number} has invalid dimensions")

    scale = min(
        options.max_width / rect.width,
        sqrt(MAX_PAGE_PIXELS / (rect.width * rect.height)),
    )
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    if pixmap.width * pixmap.height > MAX_PAGE_PIXELS:
        adjusted_scale = scale * sqrt(MAX_PAGE_PIXELS / (pixmap.width * pixmap.height))
        pixmap = page.get_pixmap(matrix=fitz.Matrix(adjusted_scale, adjusted_scale), alpha=False)

    if options.image_format == "jpg":
        image_bytes = pixmap.tobytes("jpeg", jpg_quality=options.quality)
    else:
        image_bytes = pixmap.tobytes("png")

    if len(image_bytes) > MAX_SINGLE_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Rendered page {page_number} exceeds the {MAX_SINGLE_IMAGE_BYTES // (1024 * 1024)} MiB output limit",
        )
    return image_bytes


def _render_archive(document, page_numbers: Sequence[int], original_filename: str, options: RenderOptions, fitz) -> str:
    safe_stem = _safe_stem(original_filename)
    archive_file = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f"{safe_stem}_pages_",
        suffix=".zip",
        delete=False,
    )
    archive_path = archive_file.name
    total_image_bytes = 0

    try:
        with archive_file, ZipFile(archive_file, mode="w", compression=ZIP_STORED) as archive:
            for page_number in page_numbers:
                image_bytes = _render_page(document, page_number, options, fitz)
                total_image_bytes += len(image_bytes)
                if total_image_bytes > MAX_ARCHIVE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Rendered archive exceeds the {MAX_ARCHIVE_BYTES // (1024 * 1024)} MiB output limit",
                    )
                archive.writestr(f"{safe_stem}_page_{page_number:04d}.{options.image_format}", image_bytes)

        if os.path.getsize(archive_path) > MAX_ARCHIVE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Rendered archive exceeds the {MAX_ARCHIVE_BYTES // (1024 * 1024)} MiB output limit",
            )
        return archive_path
    except Exception:
        _delete_file(archive_path)
        raise


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "document").stem
    normalized = _SAFE_STEM_RE.sub("_", stem).strip("._")
    return normalized[:120] or "document"


def delete_rendered_archive(path: str) -> None:
    """Best-effort response-background cleanup for a rendered ZIP archive."""
    _delete_file(path)


def build_download_filename(filename: str, page: str, image_format: str) -> str:
    """Return a safe, descriptive download filename for a render result."""
    stem = _safe_stem(filename)
    if page == "all":
        return f"{stem}_pages.zip"
    return f"{stem}_page_{int(page):04d}.{image_format}"


def _delete_file(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass

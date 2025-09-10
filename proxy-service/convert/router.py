"""
Conversion router for the /convert endpoints.

This module provides high-level conversion aliases that automatically route
to the most reliable service for each conversion type.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
from typing import Optional
from io import BytesIO
from urllib.parse import urlparse
import re

# Import local conversion factory
from ._local_ import LocalConversionFactory

# Import Excel processing libraries (for backwards compatibility)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    xlrd = None
    XLRD_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    openpyxl = None
    OPENPYXL_AVAILABLE = False

# Import unstructured libraries for JSON to markdown/text conversion
try:
    from unstructured.staging.base import elements_to_md, dict_to_elements
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    elements_to_md = None
    dict_to_elements = None
    UNSTRUCTURED_AVAILABLE = False

from .config import (
    ConversionService
)
from .utils.conversion_lookup import (
    get_primary_conversion,
    get_supported_conversions,
    get_service_urls
)
from .utils.conversion_chaining import (
    get_conversion_steps,
    is_chained_conversion
)
from .utils.conversion_core import (
    _convert_file,
    _get_service_client,
    validate_url,
    SERVICE_URLS,
    DYNAMIC_SERVICE_URLS,
    get_dynamic_service_urls
)
from .utils.conversion_chaining import chain_conversions, ConversionStep
from .utils.special_handlers import process_presentation_to_html

# Import URL conversion manager
from .utils.url_conversion_manager import URLConversionManager

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/convert", tags=["conversions"])


# doc conversions
@router.post("/doc-md")
async def convert_doc_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOC to Markdown (chained conversion: DOC → DOCX → Markdown)"""
    return await _convert_file(request, file=file, input_format="doc", output_format="md")


# docx conversions
@router.post("/docx-json")
async def convert_docx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to JSON structure (Document analysis)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="json")


@router.post("/docx-md")
async def convert_docx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to Markdown (Content extraction)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="md")


@router.post("/docx-pdf")
async def convert_docx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to PDF (Resume/CV priority - high quality via Gotenberg)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="pdf")


@router.post("/docx-html")
async def convert_docx_to_html(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to HTML (Document to web format)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="html")


@router.post("/docx-tex")
async def convert_docx_to_tex(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to LaTeX (Document to academic format)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="tex")


@router.post("/docx-txt")
async def convert_docx_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to plain text (Content extraction)"""
    return await _convert_file(request, file=file, input_format="docx", output_format="txt")


# html conversions
@router.post("/html-docx")
async def convert_html_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert HTML to DOCX (Document creation)"""
    return await _convert_file(request, file=file, input_format="html", output_format="docx")


@router.post("/html-json")
async def convert_html_to_json(request: Request, file: UploadFile = File(...)):
    """Convert HTML to JSON structure (Web content analysis)"""
    return await _convert_file(request, file=file, input_format="html", output_format="json")


@router.post("/html-md")
async def convert_html_to_md(request: Request, file: UploadFile = File(...)):
    """Convert HTML to Markdown (Content extraction)"""
    return await _convert_file(request, file=file, input_format="html", output_format="md")


@router.post("/html-pdf")
async def convert_html_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert HTML to PDF (Web content priority - high fidelity via Gotenberg)"""
    return await _convert_file(request, file=file, input_format="html", output_format="pdf")


@router.post("/html-tex")
async def convert_html_to_tex(request: Request, file: UploadFile = File(...)):
    """Convert HTML to LaTeX (Web content to academic format)"""
    return await _convert_file(request, file=file, input_format="html", output_format="tex")


@router.post("/html-txt")
async def convert_html_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert HTML to plain text (Web content extraction)"""
    return await _convert_file(request, file=file, input_format="html", output_format="txt")


# latex conversions
@router.post("/latex-docx")
async def convert_latex_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to DOCX (Academic content to Word - alias for tex-docx)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="docx")


@router.post("/latex-html")
async def convert_latex_to_html(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to HTML (Academic content to web format - alias for tex-html)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="html")


@router.post("/latex-md")
async def convert_latex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority - alias for tex-md)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="md")


@router.post("/latex-txt")
async def convert_latex_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Text (Academic content to plain text - alias for tex-txt)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="txt")


@router.post("/latex-pdf")
async def convert_latex_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to PDF (Academic content to PDF)"""
    return await _convert_file(request, file=file, input_format="latex", output_format="pdf")


@router.post("/latex-json")
async def convert_latex_to_json(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to JSON structure (Academic content analysis)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="json")


# md conversions
@router.post("/md-docx")
async def convert_md_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to DOCX (Document creation)"""
    return await _convert_file(request, file=file, input_format="md", output_format="docx")


@router.post("/md-json")
async def convert_md_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to JSON structure (Markdown analysis)"""
    return await _convert_file(request, file=file, input_format="md", output_format="json")


@router.post("/md-pdf")
async def convert_md_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to PDF (Text content priority)"""
    return await _convert_file(request, file=file, input_format="md", output_format="pdf")


@router.post("/md-html")
async def convert_md_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to HTML (Text to web format)"""
    return await _convert_file(request, file=file, input_format="md", output_format="html")


@router.post("/md-tex")
async def convert_md_to_tex(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to LaTeX (Text to academic format)"""
    return await _convert_file(request, file=file, input_format="md", output_format="tex")


@router.post("/md-txt")
async def convert_md_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to plain text (Content extraction)"""
    return await _convert_file(request, file=file, input_format="md", output_format="txt")


# eml conversions
@router.post("/eml-json")
async def convert_eml_to_json(request: Request, file: UploadFile = File(...)):
    """Convert EML to JSON structure (Email analysis)"""
    return await _convert_file(request, file=file, input_format="eml", output_format="json")


# epub conversions
@router.post("/epub-json")
async def convert_epub_to_json(request: Request, file: UploadFile = File(...)):
    """Convert EPUB to JSON structure (Ebook analysis)"""
    return await _convert_file(request, file=file, input_format="epub", output_format="json")


@router.post("/epub-md")
async def convert_epub_to_md(request: Request, file: UploadFile = File(...)):
    """Convert EPUB to Markdown (Ebook content extraction)"""
    return await _convert_file(request, file=file, input_format="epub", output_format="md")


@router.post("/epub-pdf")
async def convert_epub_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert EPUB to PDF (Ebook to document format)"""
    return await _convert_file(request, file=file, input_format="epub", output_format="pdf")


# msg conversions
@router.post("/msg-json")
async def convert_msg_to_json(request: Request, file: UploadFile = File(...)):
    """Convert MSG to JSON structure (Email analysis)"""
    return await _convert_file(request, file=file, input_format="msg", output_format="json")


# numbers conversions
@router.post("/numbers-html")
async def convert_numbers_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to HTML (Numbers spreadsheet to HTML)"""
    return await _convert_file(request, file=file, input_format="numbers", output_format="html")


@router.post("/numbers-json")
async def convert_numbers_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to JSON structure (chained conversion: Numbers → XLSX → JSON)"""
    return await _convert_file(request, file=file, input_format="numbers", output_format="json")


@router.post("/numbers-md")
async def convert_numbers_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to Markdown (chained conversion: Numbers → XLSX → Markdown)"""
    return await _convert_file(request, file=file, input_format="numbers", output_format="md")


@router.post("/numbers-txt")
async def convert_numbers_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to Text (Numbers spreadsheet to Text)"""
    return await _convert_file(request, file=file, input_format="numbers", output_format="txt")


@router.post("/numbers-xlsx")
async def convert_numbers_to_xlsx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to XLSX (Numbers to Excel)"""
    return await _convert_file(request, file=file, input_format="numbers", output_format="xlsx")


# ods conversions
@router.post("/ods-html")
async def convert_ods_to_html(request: Request, file: UploadFile = File(...)):
    """Convert ODS to HTML (OpenDocument spreadsheet to HTML)"""
    return await _convert_file(request, file=file, input_format="ods", output_format="html")


@router.post("/ods-md")
async def convert_ods_to_md(request: Request, file: UploadFile = File(...)):
    """Convert ODS to Markdown (OpenDocument spreadsheet to Markdown)"""
    return await _convert_file(request, file=file, input_format="ods", output_format="md")


@router.post("/ods-pdf")
async def convert_ods_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODS to PDF (OpenDocument spreadsheet to PDF)"""
    return await _convert_file(request, file=file, input_format="ods", output_format="pdf")


@router.post("/ods-txt")
async def convert_ods_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert ODS to Text (OpenDocument spreadsheet to Text)"""
    return await _convert_file(request, file=file, input_format="ods", output_format="txt")


# odt conversions
@router.post("/odt-docx")
async def convert_odt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert ODT to DOCX (OpenDocument to Word)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="docx")


@router.post("/odt-html")
async def convert_odt_to_html(request: Request, file: UploadFile = File(...)):
    """Convert ODT to HTML (OpenDocument to HTML)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="html")


@router.post("/odt-json")
async def convert_odt_to_json(request: Request, file: UploadFile = File(...)):
    """Convert ODT to JSON structure (OpenDocument analysis)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="json")


@router.post("/odt-md")
async def convert_odt_to_md(request: Request, file: UploadFile = File(...)):
    """Convert ODT to Markdown (OpenDocument to Markdown)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="md")


@router.post("/odt-pdf")
async def convert_odt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODT to PDF (Open document priority)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="pdf")


@router.post("/odt-txt")
async def convert_odt_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert ODT to Text (OpenDocument to Text)"""
    return await _convert_file(request, file=file, input_format="odt", output_format="txt")


# pages conversions
@router.post("/pages-docx")
async def convert_pages_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to DOCX"""
    return await _convert_file(request, file=file, input_format="pages", output_format="docx")


@router.post("/pages-html")
async def convert_pages_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to HTML"""
    return await _convert_file(request, file=file, input_format="pages", output_format="html")


@router.post("/pages-pdf")
async def convert_pages_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to PDF"""
    return await _convert_file(request, file=file, input_format="pages", output_format="pdf")


@router.post("/pages-txt")
async def convert_pages_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to TXT (chained conversion: Pages → docx → TXT)"""
    return await _convert_file(request, file=file, input_format="pages", output_format="txt")


@router.post("/pages-json")
async def convert_pages_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to JSON structure (chained conversion: Pages → DOCX → JSON)"""
    return await _convert_file(request, file=file, input_format="pages", output_format="json")


@router.post("/pages-md")
async def convert_pages_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to Markdown (chained conversion: Pages → DOCX → Markdown)"""
    return await _convert_file(request, file=file, input_format="pages", output_format="md")


# key conversions
@router.post("/key-odp")
async def convert_key_to_odp(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to ODP"""
    return await _convert_file(request, file=file, input_format="key", output_format="odp")


@router.post("/key-pdf")
async def convert_key_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to PDF"""
    return await _convert_file(request, file=file, input_format="key", output_format="pdf")


@router.post("/key-pptx")
async def convert_key_to_pptx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to PPTX"""
    return await _convert_file(request, file=file, input_format="key", output_format="pptx")


@router.post("/key-md")
async def convert_key_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to Markdown (chained: KEY → PPTX → Markdown)"""
    return await _convert_file(request, file=file, input_format="key", output_format="md")


@router.post("/key-txt")
async def convert_key_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to plain text (chained: KEY → PPTX → Text)"""
    return await _convert_file(request, file=file, input_format="key", output_format="txt")


@router.post("/key-html")
async def convert_key_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Keynote to HTML (KEY → PPTX → JSON → HTML)"""
    return await _convert_file(request, file=file, input_format="key", output_format="html")


# pdf conversions
@router.post("/pdf-json") 
async def convert_pdf_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PDF to JSON structure (Document analysis)"""
    return await _convert_file(request, file=file, input_format="pdf", output_format="json")


@router.post("/pdf-md")
async def convert_pdf_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PDF to Markdown (Content extraction)"""
    return await _convert_file(request, file=file, input_format="pdf", output_format="md")


@router.post("/pdf-txt")
async def convert_pdf_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert PDF to plain text (Content extraction)"""
    return await _convert_file(request, file=file, input_format="pdf", output_format="txt")


@router.post("/pdf-docx")
async def convert_pdf_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert PDF to DOCX (chained conversion: PDF → JSON → DOCX)"""
    return await _convert_file(request, file=file, input_format="pdf", output_format="docx")


@router.post("/pdf-html")
async def convert_pdf_to_html(request: Request, file: UploadFile = File(...)):
    """Convert PDF to HTML (PDF to HTML structure extraction)"""
    return await _convert_file(request, file=file, input_format="pdf", output_format="html")


# ppt conversions
@router.post("/ppt-pdf")
async def convert_ppt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPT to PDF (Legacy presentation priority)"""
    return await _convert_file(request, file=file, input_format="ppt", output_format="pdf")


@router.post("/ppt-json")
async def convert_ppt_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PPT to JSON structure (Legacy presentation analysis)"""
    return await _convert_file(request, file=file, input_format="ppt", output_format="json")


@router.post("/ppt-md")
async def convert_ppt_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PPT to Markdown (Legacy presentation content extraction)"""
    return await _convert_file(request, file=file, input_format="ppt", output_format="md")


@router.post("/ppt-txt")
async def convert_ppt_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert PPT to plain text (Legacy presentation text extraction)"""
    return await _convert_file(request, file=file, input_format="ppt", output_format="txt")


@router.post("/ppt-html")
async def convert_ppt_to_html(request: Request, file: UploadFile = File(...)):
    """Convert PPT to HTML (Legacy presentation to web format)"""
    return await _convert_file(request, file=file, input_format="ppt", output_format="html")


# pptx conversions
@router.post("/pptx-json")
async def convert_pptx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to JSON structure (Presentation analysis)"""
    return await _convert_file(request, file=file, input_format="pptx", output_format="json")


@router.post("/pptx-pdf")
async def convert_pptx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to PDF (Presentation priority - high quality via Gotenberg)"""
    return await _convert_file(request, file=file, input_format="pptx", output_format="pdf")


@router.post("/pptx-md")
async def convert_pptx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to Markdown (Presentation content extraction)"""
    return await _convert_file(request, file=file, input_format="pptx", output_format="md")


@router.post("/pptx-txt")
async def convert_pptx_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to plain text (Presentation text extraction)"""
    return await _convert_file(request, file=file, input_format="pptx", output_format="txt")


@router.post("/pptx-html")
async def convert_pptx_to_html(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to HTML (Presentation to web format)"""
    return await _convert_file(request, file=file, input_format="pptx", output_format="html")


# odp conversions
@router.post("/odp-pdf")
async def convert_odp_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODP to PDF (OpenDocument presentation priority)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="pdf")


@router.post("/odp-json")
async def convert_odp_to_json(request: Request, file: UploadFile = File(...)):
    """Convert ODP to JSON structure (chained: ODP → PPTX → JSON)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="json")


@router.post("/odp-md")
async def convert_odp_to_md(request: Request, file: UploadFile = File(...)):
    """Convert ODP to Markdown (chained: ODP → PPTX → Markdown)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="md")


@router.post("/odp-txt")
async def convert_odp_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert ODP to plain text (chained: ODP → PPTX → Text)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="txt")


@router.post("/odp-html")
async def convert_odp_to_html(request: Request, file: UploadFile = File(...)):
    """Convert ODP to HTML (ODP → PPTX → JSON → HTML)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="html")


@router.post("/odp-pptx")
async def convert_odp_to_pptx(request: Request, file: UploadFile = File(...)):
    """Convert ODP to PPTX (OpenDocument presentation to PowerPoint)"""
    return await _convert_file(request, file=file, input_format="odp", output_format="pptx")


# rtf conversions
@router.post("/rtf-docx")
async def convert_rtf_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert RTF to DOCX (Format upgrade)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="docx")


@router.post("/rtf-pdf")
async def convert_rtf_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert RTF to PDF (Legacy text format priority)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="pdf")


@router.post("/rtf-html")
async def convert_rtf_to_html(request: Request, file: UploadFile = File(...)):
    """Convert RTF to HTML (Legacy text to web format)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="html")


@router.post("/rtf-json")
async def convert_rtf_to_json(request: Request, file: UploadFile = File(...)):
    """Convert RTF to JSON structure (Legacy text analysis)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="json")


@router.post("/rtf-md")
async def convert_rtf_to_md(request: Request, file: UploadFile = File(...)):
    """Convert RTF to Markdown (Legacy text to markup)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="md")


@router.post("/rtf-txt")
async def convert_rtf_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert RTF to plain text (Legacy text extraction)"""
    return await _convert_file(request, file=file, input_format="rtf", output_format="txt")


# tex conversions
@router.post("/tex-docx")
async def convert_tex_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to DOCX (Academic content to Word)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="docx")


@router.post("/tex-html")
async def convert_tex_to_html(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to HTML (Academic content to web format)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="html")


@router.post("/tex-md")
async def convert_tex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="md")


@router.post("/tex-txt")
async def convert_tex_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Text (Academic content to plain text)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="txt")


@router.post("/tex-pdf")
async def convert_tex_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to PDF (chained conversion: LaTeX → DOCX → PDF)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="pdf")


@router.post("/tex-json")
async def convert_tex_to_json(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to JSON structure (Academic content analysis)"""
    return await _convert_file(request, file=file, input_format="tex", output_format="json")


# txt conversions
@router.post("/txt-docx")
async def convert_txt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Text to DOCX (Document creation)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="docx")


@router.post("/txt-pdf")
async def convert_txt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Text to PDF (Simple content priority)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="pdf")


@router.post("/txt-html")
async def convert_txt_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Text to HTML (Plain text to web format)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="html")


@router.post("/txt-json")
async def convert_txt_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Text to JSON structure (Text analysis)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="json")


@router.post("/txt-md")
async def convert_txt_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Text to Markdown (Plain text to markup)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="md")


@router.post("/txt-tex")
async def convert_txt_to_tex(request: Request, file: UploadFile = File(...)):
    """Convert Text to LaTeX (Plain text to academic format)"""
    return await _convert_file(request, file=file, input_format="txt", output_format="tex")

# xls conversions
@router.post("/xls-html")
async def convert_xls_to_html(request: Request, file: UploadFile = File(...)):
    """Convert XLS to HTML (Legacy spreadsheet to HTML)"""
    return await _convert_file(request, file=file, input_format="xls", output_format="html")


@router.post("/xls-json")
async def convert_xls_to_json(request: Request, file: UploadFile = File(...)):
    """Convert XLS to JSON structure (Legacy Excel analysis)"""
    return await _convert_file(request, file=file, input_format="xls", output_format="json")


@router.post("/xls-pdf")
async def convert_xls_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLS to PDF (Legacy spreadsheet to PDF)"""
    return await _convert_file(request, file=file, input_format="xls", output_format="pdf")


@router.post("/xls-md")
async def convert_xls_to_md(request: Request, file: UploadFile = File(...)):
    """Convert XLS to Markdown (Legacy spreadsheet to Markdown)"""
    return await _convert_file(request, file=file, input_format="xls", output_format="md")


@router.post("/xls-txt")
async def convert_xls_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert XLS to Text (Legacy spreadsheet to Text)"""
    return await _convert_file(request, file=file, input_format="xls", output_format="txt")


# xlsx conversions
@router.post("/xlsx-html")
async def convert_xlsx_to_html(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to HTML (Spreadsheet to HTML)"""
    return await _convert_file(request, file=file, input_format="xlsx", output_format="html")


@router.post("/xlsx-json")
async def convert_xlsx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to JSON structure (Spreadsheet analysis)"""
    return await _convert_file(request, file=file, input_format="xlsx", output_format="json")


@router.post("/xlsx-pdf")
async def convert_xlsx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to PDF (Spreadsheet to PDF)"""
    return await _convert_file(request, file=file, input_format="xlsx", output_format="pdf")


@router.post("/xlsx-md")
async def convert_xlsx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to Markdown (Spreadsheet to Markdown)"""
    return await _convert_file(request, file=file, input_format="xlsx", output_format="md")


@router.post("/xlsx-txt")
async def convert_xlsx_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to Text (Spreadsheet to Text)"""
    return await _convert_file(request, file=file, input_format="xlsx", output_format="txt")

#-- URL to {format} conversions
#-------------------------------------------------------------------------------
@router.post("/url-{output_format}")
async def convert_url_dynamic(request: Request, output_format: str, url: str = Form(...)):
    """Convert URL to specified output format (dynamic endpoint)"""
    # Validate output format is supported
    supported_conversions = get_supported_conversions()
    valid_output_formats = set()
    for input_fmt, output_fmts in supported_conversions.items():
        valid_output_formats.update(output_fmts)
    
    # Also include passthrough formats
    from .config import PASSTHROUGH_FORMATS
    valid_output_formats.update(PASSTHROUGH_FORMATS)
    
    if output_format not in valid_output_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported output format: {output_format}. Supported formats: {sorted(valid_output_formats)}"
        )
    
    # Use dedicated URL manager to determine input format and prepare conversion
    url_manager = URLConversionManager()
    conversion_input = await url_manager.process_url_conversion(url, output_format)
    
    # Get detected input format
    input_format = conversion_input.metadata["detected_format"]
    
    # For non-passthrough conversions, validate that the conversion pair exists
    if input_format != output_format or input_format not in PASSTHROUGH_FORMATS:
        from .utils.conversion_lookup import get_conversion_methods
        conversion_methods = get_conversion_methods(input_format, output_format)
        if not conversion_methods:
            raise HTTPException(
                status_code=400,
                detail=f"No conversion available from {input_format} to {output_format}"
            )
    
    # Pass to standard conversion pipeline (which handles passthrough automatically)
    return await _convert_file(
        request=request,
        file=None,
        url_input=conversion_input,
        input_format=input_format,
        output_format=output_format
    )

#-- Utility endpoints
#-------------------------------------------------------------------------------
@router.get("/supported")
async def get_supported_conversions_endpoint():
    """Get all supported conversion format pairs"""
    return JSONResponse(content={
        "supported_conversions": get_supported_conversions()
    })


@router.get("/url-info/{input_format}-{output_format}")
async def get_url_conversion_info_endpoint(input_format: str, output_format: str, url: str = None):
    """Get information about URL conversion capabilities"""
    methods = get_primary_conversion(input_format, output_format)
    if not methods:
        raise HTTPException(status_code=404, detail=f"Conversion {input_format} to {output_format} not supported")

    service, description = methods

    info = {
        "input_format": input_format,
        "output_format": output_format,
        "primary_service": service.value,
        "description": description,
        "url_support": {
            "direct_url": service.value in ["gotenberg"],  # Services that support direct URL input
            "fetch_required": service.value in ["unstructured-io", "libreoffice", "pandoc"],
            "supported": True
        }
    }

    if url:
        # Add URL-specific information if URL is provided
        try:
            url_manager = URLConversionManager()
            path_info = url_manager.get_optimal_conversion_path(url, output_format)
            info["url_analysis"] = {
                "detected_format": path_info["detected_format"],
                "conversion_path": path_info["conversion_path"],
                "requires_temp_file": path_info["requires_temp_file"]
            }
        except Exception as e:
            info["url_analysis"] = {
                "error": str(e),
                "detected_format": "unknown"
            }

    return JSONResponse(content=info)


@router.post("/validate-url")
async def validate_url_endpoint_post(url: str = Form(...)):
    """
    Validate a URL and its content format for conversion (POST method).

    This endpoint fetches the URL content and validates that the format
    is supported for conversion, without performing the actual conversion.
    """
    return await _validate_url_common(url)


@router.get("/validate-url")
async def validate_url_endpoint_get(url: str = Query(..., description="URL to validate")):
    """
    Validate a URL and its content format for conversion (GET method).

    This endpoint fetches the URL content and validates that the format
    is supported for conversion, without performing the actual conversion.

    Example: /convert/validate-url?url=https://example.com
    """
    return await _validate_url_common(url)


async def _validate_url_common(url: str):
    """
    Common validation logic for both GET and POST methods.
    """
    try:
        # Use the new URL manager to validate and analyze the URL
        url_manager = URLConversionManager()
        
        # Try to process the URL to see if it's valid
        conversion_input = await url_manager.process_url_conversion(url, "html")
        
        # Clean up the temp file since we're just validating
        await conversion_input.cleanup()
        
        return JSONResponse(content={
            "valid": True,
            "url": url,
            "detected_format": conversion_input.metadata.get('detected_format'),
            "conversion_path": conversion_input.metadata.get('conversion_path'),
            "message": f"URL is valid and format '{conversion_input.metadata.get('detected_format')}' is supported for conversion"
        })

    except HTTPException as e:
        return JSONResponse(content={
            "valid": False,
            "url": url,
            "error": e.detail,
            "supported_formats": ["html", "pdf", "docx", "xlsx", "pptx", "txt", "md", "json", "doc", "xls", "ppt", "odt", "ods", "odp", "rtf", "tex", "epub", "eml", "msg", "pages", "numbers", "key"]  # Common supported formats
        }, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={
            "valid": False,
            "url": url,
            "error": f"Validation failed: {str(e)}",
            "supported_formats": ["html", "pdf", "docx", "xlsx", "pptx", "txt", "md", "json", "doc", "xls", "ppt", "odt", "ods", "odp", "rtf", "tex", "epub", "eml", "msg", "pages", "numbers", "key"]  # Common supported formats
        }, status_code=500)

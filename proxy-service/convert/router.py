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
    get_primary_conversion,
    ConversionService, 
    get_supported_conversions,
    get_service_urls
)
from .utils.url_helpers import (
    handle_url_conversion_request,
    cleanup_conversion_temp_files,
    get_url_conversion_info,
    validate_url_conversion_request,
    get_supported_input_formats
)
from .utils.conversion_core import (
    _convert_file,
    _get_service_client,
    validate_url,
    SERVICE_URLS,
    DYNAMIC_SERVICE_URLS,
    get_dynamic_service_urls
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/convert", tags=["conversions"])


# doc conversions
@router.post("/doc-md")
async def convert_doc_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOC to Markdown (chained conversion: DOC → DOCX → Markdown)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="doc",
                output_format="docx",
                description="Convert legacy DOC to DOCX using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="docx",
                output_format="md",
                extra_params={"extra_args": "--from=docx"},
                description="Convert DOCX to Markdown using Pandoc"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="md",
            final_content_type="text/markdown"
        )

    except Exception as e:
        logger.error(f"Error in doc_to_md conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


# docx conversions
@router.post("/docx-json")
async def convert_docx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("docx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="json", service=service)


@router.post("/docx-md")
async def convert_docx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to Markdown (Content extraction)"""
    service, description = get_primary_conversion("docx", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="md", service=service)


@router.post("/docx-pdf")
async def convert_docx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to PDF (Resume/CV priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("docx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="pdf", service=service)


# html conversions
@router.post("/html-docx")
async def convert_html_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert HTML to DOCX (Document creation)"""
    # Try primary service (LibreOffice) first
    primary_service, primary_desc = get_primary_conversion("html", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    
    try:
        return await _convert_file(request, file=file, input_format="html", output_format="docx", service=primary_service)
    except HTTPException as e:
        # If primary service fails, try secondary service (Pandoc)
        if "LibreOffice" in str(e.detail) or "unoconvert" in str(e.detail):
            logger.warning(f"Primary service {primary_service.value} failed for HTML->DOCX, trying fallback")
            # Reset file pointer for the fallback attempt
            await file.seek(0)
            secondary_service = ConversionService.PANDOC
            return await _convert_file(request, file=file, input_format="html", output_format="docx", service=secondary_service)
        else:
            # Re-raise if it's not a LibreOffice-specific error
            raise


@router.post("/html-json")
async def convert_html_to_json(request: Request, file: UploadFile = File(...)):
    """Convert HTML to JSON structure (Web content analysis)"""
    service, description = get_primary_conversion("html", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="json", service=service)


@router.post("/html-md")
async def convert_html_to_md(request: Request, file: UploadFile = File(...)):
    """Convert HTML to Markdown (Content extraction)"""
    service, description = get_primary_conversion("html", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="md", service=service)


@router.post("/html-pdf")
async def convert_html_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert HTML to PDF (Web content priority - high fidelity via Gotenberg)"""
    service, description = get_primary_conversion("html", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="pdf", service=service)


# latex conversions
@router.post("/latex-docx")
async def convert_latex_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to DOCX (Academic content to Word - alias for tex-docx)"""
    service, description = get_primary_conversion("tex", "docx") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="docx", service=service)


@router.post("/latex-html")
async def convert_latex_to_html(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to HTML (Academic content to web format - alias for tex-html)"""
    service, description = get_primary_conversion("tex", "html") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="html", service=service)


@router.post("/latex-json")
async def convert_latex_to_json(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to JSON (chained conversion: LaTeX → DOCX → JSON - alias for tex-json)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="tex",
                output_format="docx",
                extra_params={"extra_args": "--from=latex"},
                description="Convert LaTeX to DOCX using Pandoc"
            ),
            ConversionStep(
                service=ConversionService.UNSTRUCTURED_IO,
                input_format="docx",
                output_format="json",
                description="Convert DOCX to JSON using Unstructured IO"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="json",
            final_content_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in latex_to_json conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/latex-md")
async def convert_latex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority - alias for tex-md)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="md", service=service)


@router.post("/latex-txt")
async def convert_latex_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Text (Academic content to plain text - alias for tex-txt)"""
    service, description = get_primary_conversion("tex", "txt") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="txt", service=service)


# md conversions
@router.post("/md-docx")
async def convert_md_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to DOCX (Document creation)"""
    service, description = get_primary_conversion("md", "docx") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="md", output_format="docx", service=service)


@router.post("/md-json")
async def convert_md_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to JSON structure (Markdown analysis)"""
    service, description = get_primary_conversion("md", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="md", output_format="json", service=service)


@router.post("/md-pdf")
async def convert_md_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to PDF (Text content priority)"""
    service, description = get_primary_conversion("md", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="md", output_format="pdf", service=service)


# numbers conversions
@router.post("/numbers-html")
async def convert_numbers_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to HTML (Numbers spreadsheet to HTML)"""
    service, description = get_primary_conversion("numbers", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="numbers", output_format="html", service=service)


@router.post("/numbers-json")
async def convert_numbers_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to JSON structure (chained conversion: Numbers → XLSX → JSON)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="numbers",
                output_format="xlsx",
                description="Convert Apple Numbers to XLSX using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.UNSTRUCTURED_IO,
                input_format="xlsx",
                output_format="json",
                description="Convert XLSX to JSON using unstructured-io"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="json",
            final_content_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in numbers_to_json conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/numbers-md")
async def convert_numbers_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to Markdown (chained conversion: Numbers → XLSX → Markdown)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="numbers",
                output_format="xlsx",
                description="Convert Apple Numbers to XLSX using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.UNSTRUCTURED_IO,
                input_format="xlsx",
                output_format="md",
                description="Convert XLSX to Markdown using unstructured-io"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="md",
            final_content_type="text/markdown"
        )

    except Exception as e:
        logger.error(f"Error in numbers_to_md conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/numbers-txt")
async def convert_numbers_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to Text (Numbers spreadsheet to Text)"""
    service, description = get_primary_conversion("numbers", "txt") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="numbers", output_format="txt", service=service)


@router.post("/numbers-xlsx")
async def convert_numbers_to_xlsx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Numbers to XLSX (Numbers to Excel)"""
    service, description = get_primary_conversion("numbers", "xlsx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="numbers", output_format="xlsx", service=service)


# ods conversions
@router.post("/ods-html")
async def convert_ods_to_html(request: Request, file: UploadFile = File(...)):
    """Convert ODS to HTML (OpenDocument spreadsheet to HTML)"""
    service, description = get_primary_conversion("ods", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="ods", output_format="html", service=service)


@router.post("/ods-md")
async def convert_ods_to_md(request: Request, file: UploadFile = File(...)):
    """Convert ODS to Markdown (OpenDocument spreadsheet to Markdown)"""
    service, description = get_primary_conversion("ods", "md") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="ods", output_format="md", service=service)


@router.post("/ods-pdf")
async def convert_ods_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODS to PDF (OpenDocument spreadsheet to PDF)"""
    service, description = get_primary_conversion("ods", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="ods", output_format="pdf", service=service)


@router.post("/ods-txt")
async def convert_ods_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert ODS to Text (OpenDocument spreadsheet to Text)"""
    service, description = get_primary_conversion("ods", "txt") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="ods", output_format="txt", service=service)


# odt conversions
@router.post("/odt-docx")
async def convert_odt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert ODT to DOCX (OpenDocument to Word)"""
    service, description = get_primary_conversion("odt", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="docx", service=service)


@router.post("/odt-html")
async def convert_odt_to_html(request: Request, file: UploadFile = File(...)):
    """Convert ODT to HTML (OpenDocument to HTML)"""
    service, description = get_primary_conversion("odt", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="html", service=service)


@router.post("/odt-json")
async def convert_odt_to_json(request: Request, file: UploadFile = File(...)):
    """Convert ODT to JSON structure (OpenDocument analysis)"""
    service, description = get_primary_conversion("odt", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="json", service=service)


@router.post("/odt-md")
async def convert_odt_to_md(request: Request, file: UploadFile = File(...)):
    """Convert ODT to Markdown (OpenDocument to Markdown)"""
    service, description = get_primary_conversion("odt", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="md", service=service)


@router.post("/odt-pdf")
async def convert_odt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODT to PDF (Open document priority)"""
    service, description = get_primary_conversion("odt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="pdf", service=service)


@router.post("/odt-txt")
async def convert_odt_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert ODT to Text (OpenDocument to Text)"""
    service, description = get_primary_conversion("odt", "txt") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="txt", service=service)


# pages conversions
@router.post("/pages-docx")
async def convert_pages_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to DOCX"""
    service, description = get_primary_conversion("pages", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pages", output_format="docx", service=service)


@router.post("/pages-html")
async def convert_pages_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to HTML"""
    service, description = get_primary_conversion("pages", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pages", output_format="html", service=service)


@router.post("/pages-json")
async def convert_pages_to_json(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to JSON (chained conversion: Pages → DOCX → JSON)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="pages",
                output_format="docx",
                description="Convert Apple Pages to DOCX using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.UNSTRUCTURED_IO,
                input_format="docx",
                output_format="json",
                description="Convert DOCX to JSON using Unstructured IO"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="json",
            final_content_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in pages_to_json conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/pages-md")
async def convert_pages_to_md(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to Markdown (chained conversion: Pages → DOCX → Markdown)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="pages",
                output_format="docx",
                description="Convert Apple Pages to DOCX using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="docx",
                output_format="md",
                extra_params={"extra_args": "--from=docx"},
                description="Convert DOCX to Markdown using Pandoc"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="md",
            final_content_type="text/markdown"
        )

    except Exception as e:
        logger.error(f"Error in pages_to_md conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/pages-pdf")
async def convert_pages_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to PDF"""
    service, description = get_primary_conversion("pages", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pages", output_format="pdf", service=service)


@router.post("/pages-txt")
async def convert_pages_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to TXT (chained conversion: Pages → docx → TXT)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.LIBREOFFICE,
                input_format="pages",
                output_format="docx",
                description="Convert Apple Pages to docx using LibreOffice"
            ),
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="docx",
                output_format="txt",
                description="Convert docx to TXT using Pandoc"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="txt",
            final_content_type="text/plain"
        )

    except Exception as e:
        logger.error(f"Error in pages_to_txt conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


# pdf conversions
@router.post("/pdf-json") 
async def convert_pdf_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PDF to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("pdf", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pdf", output_format="json", service=service)


@router.post("/pdf-md")
async def convert_pdf_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PDF to Markdown (Content extraction)"""
    service, description = get_primary_conversion("pdf", "md") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pdf", output_format="md", service=service)


@router.post("/pdf-txt")
async def convert_pdf_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert PDF to plain text (Content extraction)"""
    service, description = get_primary_conversion("pdf", "txt") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pdf", output_format="txt", service=service)


# ppt conversions
@router.post("/ppt-pdf")
async def convert_ppt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPT to PDF (Legacy presentation priority)"""
    service, description = get_primary_conversion("ppt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="ppt", output_format="pdf", service=service)


# pptx conversions
@router.post("/pptx-json")
async def convert_pptx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to JSON structure (Presentation analysis)"""
    service, description = get_primary_conversion("pptx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pptx", output_format="json", service=service)


@router.post("/pptx-pdf")
async def convert_pptx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to PDF (Presentation priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("pptx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pptx", output_format="pdf", service=service)


# rtf conversions
@router.post("/rtf-docx")
async def convert_rtf_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert RTF to DOCX (Format upgrade)"""
    service, description = get_primary_conversion("rtf", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="rtf", output_format="docx", service=service)


@router.post("/rtf-pdf")
async def convert_rtf_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert RTF to PDF (Legacy text format priority)"""
    service, description = get_primary_conversion("rtf", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="rtf", output_format="pdf", service=service)


# tex conversions
@router.post("/tex-docx")
async def convert_tex_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to DOCX (Academic content to Word)"""
    service, description = get_primary_conversion("tex", "docx") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="docx", service=service)


@router.post("/tex-html")
async def convert_tex_to_html(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to HTML (Academic content to web format)"""
    service, description = get_primary_conversion("tex", "html") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="html", service=service)


@router.post("/tex-json")
async def convert_tex_to_json(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to JSON (chained conversion: LaTeX → DOCX → JSON)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="tex",
                output_format="docx",
                extra_params={"extra_args": "--from=latex"},
                description="Convert LaTeX to DOCX using Pandoc"
            ),
            ConversionStep(
                service=ConversionService.UNSTRUCTURED_IO,
                input_format="docx",
                output_format="json",
                description="Convert DOCX to JSON using Unstructured IO"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="json",
            final_content_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in tex_to_json conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/tex-md")
async def convert_tex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="md", service=service)


@router.post("/tex-pdf")
async def convert_tex_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to PDF (chained conversion: LaTeX → DOCX → PDF)"""
    try:
        # Read the uploaded file
        file_content = await file.read()

        # Define the conversion chain
        from .utils.conversion_chaining import chain_conversions, ConversionStep

        conversion_steps = [
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="tex",
                output_format="docx",
                description="Convert LaTeX to DOCX using Pandoc"
            ),
            ConversionStep(
                service=ConversionService.PANDOC,
                input_format="docx",
                output_format="pdf",
                description="Convert DOCX to PDF using Pandoc"
            )
        ]

        # Execute the chained conversion
        return await chain_conversions(
            request=request,
            initial_file_content=file_content,
            initial_filename=file.filename,
            conversion_steps=conversion_steps,
            final_output_format="pdf",
            final_content_type="application/pdf"
        )

    except Exception as e:
        logger.error(f"Error in tex_to_pdf conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")


@router.post("/tex-txt")
async def convert_tex_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Text (Academic content to plain text)"""
    service, description = get_primary_conversion("tex", "txt") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="txt", service=service)


# txt conversions
@router.post("/txt-docx")
async def convert_txt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Text to DOCX (Document creation)"""
    service, description = get_primary_conversion("txt", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="txt", output_format="docx", service=service)


@router.post("/txt-pdf")
async def convert_txt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Text to PDF (Simple content priority)"""
    service, description = get_primary_conversion("txt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="txt", output_format="pdf", service=service)


# url conversions
@router.post("/url-html")
async def convert_url_to_html(request: Request, url: str = Form(...)):
    """Convert URL to HTML (Local - raw HTML content fetching)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "html") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="html", service=service)


@router.post("/url-json")
async def convert_url_to_json(request: Request, url: str = Form(...)):
    """Convert URL to JSON structure (Unstructured-IO - web content analysis)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="json", service=service)


@router.post("/url-md")
async def convert_url_to_md(request: Request, url: str = Form(...)):
    """Convert URL to Markdown (Unstructured-IO - content extraction)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "md") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="md", service=service)


@router.post("/url-pdf")
async def convert_url_to_pdf(request: Request, url: str = Form(...)):
    """Convert URL to PDF (Gotenberg - high-fidelity web to PDF)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "pdf") or (ConversionService.GOTENBERG, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="pdf", service=service)


@router.post("/url-txt")
async def convert_url_to_txt(request: Request, url: str = Form(...)):
    """Convert URL to plain text (Unstructured-IO - text extraction)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "txt") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="txt", service=service)


# xls conversions
@router.post("/xls-html")
async def convert_xls_to_html(request: Request, file: UploadFile = File(...)):
    """Convert XLS to HTML (Legacy spreadsheet to HTML)"""
    service, description = get_primary_conversion("xls", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="html", service=service)


@router.post("/xls-json")
async def convert_xls_to_json(request: Request, file: UploadFile = File(...)):
    """Convert XLS to JSON structure (Legacy Excel analysis)"""
    service, description = get_primary_conversion("xls", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="json", service=service)


@router.post("/xls-md")
async def convert_xls_to_md(request: Request, file: UploadFile = File(...)):
    """Convert XLS to Markdown (Legacy spreadsheet to Markdown)"""
    service, description = get_primary_conversion("xls", "md") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="md", service=service)


@router.post("/xls-pdf")
async def convert_xls_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLS to PDF (Legacy spreadsheet to PDF)"""
    service, description = get_primary_conversion("xls", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="pdf", service=service)


@router.post("/xls-txt")
async def convert_xls_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert XLS to Text (Legacy spreadsheet to Text)"""
    service, description = get_primary_conversion("xls", "txt") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="txt", service=service)


# xlsx conversions
@router.post("/xlsx-html")
async def convert_xlsx_to_html(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to HTML (Spreadsheet to HTML)"""
    service, description = get_primary_conversion("xlsx", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="html", service=service)


@router.post("/xlsx-json")
async def convert_xlsx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to JSON structure (Spreadsheet analysis)"""
    service, description = get_primary_conversion("xlsx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="json", service=service)


@router.post("/xlsx-md")
async def convert_xlsx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to Markdown (Spreadsheet to Markdown)"""
    service, description = get_primary_conversion("xlsx", "md") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="md", service=service)


@router.post("/xlsx-pdf")
async def convert_xlsx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to PDF (Spreadsheet to PDF)"""
    service, description = get_primary_conversion("xlsx", "pdf") or (ConversionService.GOTENBERG, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="pdf", service=service)


@router.post("/xlsx-txt")
async def convert_xlsx_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to Text (Spreadsheet to Text)"""
    service, description = get_primary_conversion("xlsx", "txt") or (ConversionService.LOCAL, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="txt", service=service)


# Utility endpoints
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
        url_info = get_url_conversion_info(url, service.value, input_format)
        info["url_analysis"] = url_info

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
        # Use the validation function to check URL and content
        file_wrapper, metadata = await validate_url_conversion_request(
            url, "unstructured-io", "auto"  # Use a service that fetches content
        )

        # Clean up the temp file since we're not using it
        if file_wrapper and 'temp_file_path' in metadata:
            cleanup_conversion_temp_files(metadata)

        return JSONResponse(content={
            "valid": True,
            "url": url,
            "detected_format": metadata.get('detected_format'),
            "validated_format": metadata.get('validated_format'),
            "content_type": metadata.get('content_type'),
            "message": f"URL content format '{metadata.get('validated_format')}' is supported for conversion"
        })

    except HTTPException as e:
        return JSONResponse(content={
            "valid": False,
            "url": url,
            "error": e.detail,
            "supported_formats": list(get_supported_input_formats())
        }, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={
            "valid": False,
            "url": url,
            "error": f"Validation failed: {str(e)}",
            "supported_formats": list(get_supported_input_formats())
        }, status_code=500)

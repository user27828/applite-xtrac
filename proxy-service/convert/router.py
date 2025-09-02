"""
Conversion router for the /convert endpoints.

This module provides high-level conversion aliases that automatically route
to the most reliable service for each conversion type.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
from typing import Optional
from io import BytesIO

from .config import (
    get_primary_conversion,
    ConversionService,
    get_supported_conversions
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/convert", tags=["conversions"])

# Service URL mappings (should match main app)
SERVICE_URLS = {
    ConversionService.UNSTRUCTURED_IO: "http://unstructured-io:8000",
    ConversionService.LIBREOFFICE: "http://libreoffice:2004",
    ConversionService.PANDOC: "http://pandoc:3000",
    ConversionService.GOTENBERG: "http://gotenberg:3000"
}


async def _get_service_client(service: ConversionService, request: Request) -> httpx.AsyncClient:
    """Get the appropriate HTTP client for a service."""
    if service == ConversionService.LIBREOFFICE:
        return request.app.state.libreoffice_client
    elif service == ConversionService.GOTENBERG:
        return request.app.state.gotenberg_client
    else:
        return request.app.state.client


async def _convert_file(
    request: Request,
    file: UploadFile,
    input_format: str,
    output_format: str,
    service: ConversionService,
    extra_params: Optional[dict] = None
) -> StreamingResponse:
    """
    Generic file conversion function that routes to the appropriate service.

    Args:
        request: FastAPI request object
        file: Uploaded file
        input_format: Input file format
        output_format: Desired output format
        service: Conversion service to use
        extra_params: Additional parameters for the service

    Returns:
        StreamingResponse with converted file
    """
    try:
        # Read file content
        file_content = await file.read()

        # Get service client
        client = await _get_service_client(service, request)

        # Prepare request based on service
        service_url = SERVICE_URLS[service]

        if service == ConversionService.UNSTRUCTURED_IO:
            # Unstructured IO expects multipart/form-data
            files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
            data = {"output_format": output_format}

            response = await client.post(
                f"{service_url}/general/v0/general",
                files=files,
                data=data
            )

        elif service == ConversionService.LIBREOFFICE:
            # LibreOffice expects multipart/form-data with convert-to parameter
            files = {"file": (file.filename, BytesIO(file_content), f"application/{input_format}")}
            data = {"convert-to": output_format}

            response = await client.post(
                f"{service_url}/request",
                files=files,
                data=data
            )

        elif service == ConversionService.PANDOC:
            # Pandoc expects multipart/form-data with specific parameter names
            files = {"file": (file.filename, BytesIO(file_content), f"application/{input_format}")}
            data = {"output_format": output_format}

            # Add input format as extra arg if needed
            if input_format != "md":  # pandoc defaults to markdown
                # Map tex/latex to latex for Pandoc
                pandoc_input_format = "latex" if input_format in ["tex", "latex"] else input_format
                data["extra_args"] = f"--from={pandoc_input_format}"

            response = await client.post(
                f"{service_url}/convert",
                files=files,
                data=data
            )

        elif service == ConversionService.GOTENBERG:
            # Gotenberg expects multipart/form-data with specific structure
            files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
            data = {}

            if extra_params:
                data.update(extra_params)

            # Use the correct endpoint based on file type
            if input_format in ['docx', 'pptx', 'xlsx', 'xls', 'ppt', 'odt', 'ods', 'odp', 'pages']:
                endpoint = "forms/libreoffice/convert"
            else:
                endpoint = "forms/chromium/convert/html"

            response = await client.post(
                f"{service_url}/{endpoint}",
                files=files,
                data=data
            )

        else:
            raise HTTPException(status_code=500, detail=f"Unsupported service: {service}")

        # Check response
        if response.status_code != 200:
            logger.error(f"Service {service} returned {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Conversion failed: {response.text}"
            )

        # Determine content type based on output format
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "html": "text/html",
            "md": "text/markdown",
            "txt": "text/plain",
            "tex": "application/x-tex",
            "json": "application/json"
        }

        content_type = content_types.get(output_format, "application/octet-stream")

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.{output_format}"

        return StreamingResponse(
            BytesIO(response.content),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except httpx.RequestError as e:
        logger.error(f"Request error for {service}: {e}")
        raise HTTPException(status_code=503, detail=f"Service {service} unavailable")
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


# Resume/CV/Cover Letter Priority Conversions
@router.post("/docx-pdf")
async def convert_docx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to PDF (Resume/CV priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("docx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "docx", "pdf", service)


@router.post("/pptx-pdf")
async def convert_pptx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to PDF (Presentation priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("pptx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "pptx", "pdf", service)


@router.post("/ppt-pdf")
async def convert_ppt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPT to PDF (Legacy presentation priority)"""
    service, description = get_primary_conversion("ppt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "ppt", "pdf", service)


@router.post("/html-pdf")
async def convert_html_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert HTML to PDF (Web content priority - high fidelity via Gotenberg)"""
    service, description = get_primary_conversion("html", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "html", "pdf", service)


@router.post("/md-pdf")
async def convert_md_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to PDF (Text content priority)"""
    service, description = get_primary_conversion("md", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "md", "pdf", service)


@router.post("/tex-pdf")
async def convert_tex_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to PDF (Academic content priority)"""
    service, description = get_primary_conversion("tex", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "tex", "pdf", service)


@router.post("/txt-pdf")
async def convert_txt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Text to PDF (Simple content priority)"""
    service, description = get_primary_conversion("txt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "txt", "pdf", service)


@router.post("/rtf-pdf")
async def convert_rtf_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert RTF to PDF (Legacy text format priority)"""
    service, description = get_primary_conversion("rtf", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "rtf", "pdf", service)


@router.post("/odt-pdf")
async def convert_odt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODT to PDF (Open document priority)"""
    service, description = get_primary_conversion("odt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "odt", "pdf", service)


# JSON Structure Extraction (Unstructured IO priority)
@router.post("/docx-json")
async def convert_docx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("docx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file, "docx", "json", service)


@router.post("/pdf-json")
async def convert_pdf_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PDF to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("pdf", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file, "pdf", "json", service)


@router.post("/pptx-json")
async def convert_pptx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to JSON structure (Presentation analysis)"""
    service, description = get_primary_conversion("pptx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file, "pptx", "json", service)


@router.post("/html-json")
async def convert_html_to_json(request: Request, file: UploadFile = File(...)):
    """Convert HTML to JSON structure (Web content analysis)"""
    service, description = get_primary_conversion("html", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file, "html", "json", service)


# Markdown Conversions (Pandoc priority)
@router.post("/docx-md")
async def convert_docx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to Markdown (Content extraction)"""
    service, description = get_primary_conversion("docx", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "docx", "md", service)


@router.post("/html-md")
async def convert_html_to_md(request: Request, file: UploadFile = File(...)):
    """Convert HTML to Markdown (Content extraction)"""
    service, description = get_primary_conversion("html", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "html", "md", service)


@router.post("/pdf-md")
async def convert_pdf_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PDF to Markdown (Content extraction)"""
    service, description = get_primary_conversion("pdf", "md") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file, "pdf", "md", service)


@router.post("/tex-md")
async def convert_tex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "tex", "md", service)


@router.post("/latex-md")
async def convert_latex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority - alias for tex-md)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "tex", "md", service)


# DOCX Conversions
@router.post("/md-docx")
async def convert_md_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to DOCX (Document creation)"""
    service, description = get_primary_conversion("md", "docx") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file, "md", "docx", service)


@router.post("/html-docx")
async def convert_html_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert HTML to DOCX (Document creation)"""
    service, description = get_primary_conversion("html", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "html", "docx", service)


@router.post("/rtf-docx")
async def convert_rtf_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert RTF to DOCX (Format upgrade)"""
    service, description = get_primary_conversion("rtf", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "rtf", "docx", service)


@router.post("/txt-docx")
async def convert_txt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Text to DOCX (Document creation)"""
    service, description = get_primary_conversion("txt", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "txt", "docx", service)


# Additional Conversions
@router.post("/xlsx-pdf")
async def convert_xlsx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to PDF (Spreadsheet to PDF)"""
    service, description = get_primary_conversion("xlsx", "pdf") or (ConversionService.GOTENBERG, "Fallback")
    return await _convert_file(request, file, "xlsx", "pdf", service)


@router.post("/xls-pdf")
async def convert_xls_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLS to PDF (Legacy spreadsheet to PDF)"""
    service, description = get_primary_conversion("xls", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "xls", "pdf", service)


@router.post("/epub-pdf")
async def convert_epub_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert EPUB to PDF (E-book to PDF)"""
    service, description = get_primary_conversion("epub", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "epub", "pdf", service)


@router.post("/ods-pdf")
async def convert_ods_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODS to PDF (OpenDocument spreadsheet to PDF)"""
    service, description = get_primary_conversion("ods", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "ods", "pdf", service)


@router.post("/odp-pdf")
async def convert_odp_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODP to PDF (OpenDocument presentation to PDF)"""
    service, description = get_primary_conversion("odp", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "odp", "pdf", service)


# Apple Pages Conversions
@router.post("/pages-pdf")
async def convert_pages_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to PDF"""
    service, description = get_primary_conversion("pages", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "pages", "pdf", service)


@router.post("/pages-docx")
async def convert_pages_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to DOCX"""
    service, description = get_primary_conversion("pages", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "pages", "docx", service)


@router.post("/pages-html")
async def convert_pages_to_html(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to HTML"""
    service, description = get_primary_conversion("pages", "html") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "pages", "html", service)


@router.post("/pages-txt")
async def convert_pages_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to TXT"""
    service, description = get_primary_conversion("pages", "txt") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file, "pages", "txt", service)


# Utility endpoints
@router.get("/supported")
async def get_supported_conversions_endpoint():
    """Get all supported conversion format pairs"""
    return JSONResponse(content={
        "supported_conversions": get_supported_conversions()
    })


@router.get("/info/{input_format}-{output_format}")
async def get_conversion_info(input_format: str, output_format: str):
    """Get information about a specific conversion pair"""
    methods = get_primary_conversion(input_format, output_format)
    if not methods:
        raise HTTPException(status_code=404, detail=f"Conversion {input_format} to {output_format} not supported")

    service, description = methods
    return JSONResponse(content={
        "input_format": input_format,
        "output_format": output_format,
        "primary_service": service.value,
        "description": description
    })

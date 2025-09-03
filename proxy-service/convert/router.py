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
    get_supported_conversions
)
from .url_helpers import (
    handle_url_conversion_request,
    cleanup_conversion_temp_files,
    get_url_conversion_info,
    validate_url_conversion_request,
    get_supported_input_formats
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


def validate_url(url: str) -> bool:
    """Validate that the URL is properly formatted and uses http/https."""
    if not url or not isinstance(url, str):
        return False
    
    # Basic URL validation
    try:
        parsed = urlparse(url)
        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        # Only allow http and https
        if parsed.scheme not in ['http', 'https']:
            return False
        # Basic sanity check for netloc
        if not re.match(r'^[a-zA-Z0-9.-]+$', parsed.netloc.replace(':', '').replace('.', '')):
            return False
        return True
    except Exception:
        return False


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
    file: Optional[UploadFile] = None,
    url: Optional[str] = None,
    input_format: str = "",
    output_format: str = "",
    service: ConversionService = None,
    extra_params: Optional[dict] = None
) -> StreamingResponse:
    """
    Generic file conversion function that routes to the appropriate service.
    Supports both file upload and URL input.

    Args:
        request: FastAPI request object
        file: Uploaded file (optional if url is provided)
        url: URL to convert (optional if file is provided)
        input_format: Input file format (required)
        output_format: Desired output format (required)
        service: Conversion service to use (required)
        extra_params: Additional parameters for the service

    Returns:
        StreamingResponse with converted file
    """
    if not file and not url:
        raise HTTPException(status_code=400, detail="Either file or url must be provided")
    if file and url:
        raise HTTPException(status_code=400, detail="Cannot provide both file and url")
    
    # Handle URL inputs by fetching content first
    temp_file_wrapper = None
    conversion_metadata = {}
    
    try:
        if url:
            try:
                # Use URL conversion manager to fetch content if needed
                temp_file_wrapper, conversion_metadata = await handle_url_conversion_request(
                    url, service.value, input_format
                )
                
                # If we got a temp file, use it as the file input
                if temp_file_wrapper:
                    file = temp_file_wrapper
                    # Update input format if it was auto-detected
                    if conversion_metadata.get('detected_format'):
                        input_format = conversion_metadata['detected_format']
                        
            except Exception as e:
                # Clean up any temp files if something went wrong
                if conversion_metadata.get('temp_file_path'):
                    cleanup_conversion_temp_files(conversion_metadata)
                raise

        # Get service client
        client = await _get_service_client(service, request)

        # Prepare request based on service
        service_url = SERVICE_URLS[service]

        if service == ConversionService.UNSTRUCTURED_IO:
            # Unstructured IO now supports URLs through fetching
            if file:
                # Read file content
                file_content = await file.read()
                files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
                # Map output_format to MIME types for Unstructured-IO
                mime_mapping = {
                    "json": "application/json",
                    "md": "text/markdown", 
                    "txt": "text/plain"
                }
                unstructured_output_format = mime_mapping.get(output_format, output_format)
                data = {"output_format": unstructured_output_format}
            else:
                # This should not happen anymore since we fetch URLs above
                raise HTTPException(
                    status_code=500,
                    detail="URL input should have been converted to file input"
                )

            # For markdown and text outputs, we need to get JSON and convert locally
            if output_format in ["md", "txt"]:
                # Always get JSON from Unstructured-IO
                request_data = data.copy()
                if "output_format" in request_data:
                    del request_data["output_format"]  # Remove output_format to get JSON

                if files:
                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        files=files,
                        data=request_data
                    )
                else:
                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        json=request_data
                    )

                if response.status_code != 200:
                    logger.error(f"Service {service} returned {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Conversion failed: {response.text}"
                    )

                # Parse JSON response and convert locally
                if not UNSTRUCTURED_AVAILABLE or not dict_to_elements or not elements_to_md:
                    raise HTTPException(status_code=503, detail="Unstructured library not available for local conversion")

                json_data = response.json()
                elements = []
                for item in json_data:
                    elements.extend(dict_to_elements([item]))

                if output_format == "md":
                    content = elements_to_md(elements)
                    media_type = "text/markdown"
                else:  # txt
                    content = "\n".join([elem.text for elem in elements if elem.text])
                    media_type = "text/plain"

                # Generate output filename
                if file:
                    base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
                else:
                    parsed_url = urlparse(url)
                    base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
                    if not base_name:
                        base_name = "url_content"

                output_filename = f"{base_name}.{output_format}"

                return StreamingResponse(
                    BytesIO(content.encode('utf-8')),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={output_filename}"}
                )
            else:
                # For JSON output or other formats, use the service directly
                if files:
                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        files=files,
                        data=data
                    )
                else:
                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        json=data
                    )

        elif service == ConversionService.LIBREOFFICE:
            # LibreOffice expects multipart/form-data with convert-to parameter
            if not file:
                raise HTTPException(status_code=400, detail="LibreOffice only supports file input")
            
            file_content = await file.read()
            files = {"file": (file.filename, BytesIO(file_content), f"application/{input_format}")}
            data = {"convert-to": output_format}

            response = await client.post(
                f"{service_url}/request",
                files=files,
                data=data
            )

        elif service == ConversionService.PANDOC:
            if not file:
                raise HTTPException(status_code=400, detail="Pandoc only supports file input")
                
            file_content = await file.read()
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
            # Gotenberg supports both files and URLs
            if file:
                file_content = await file.read()
                files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
                data = {}
            else:
                # URL input for Gotenberg - prepare multipart form-data fields
                # Use the `files` parameter so httpx builds multipart/form-data.
                files = {"url": (None, url)}

            if extra_params:
                # Place extra params into the multipart payload as form fields
                for k, v in extra_params.items():
                    files[k] = (None, str(v))

            # Use the correct endpoint based on input type
            if file:
                if input_format in ['docx', 'pptx', 'xlsx', 'xls', 'ppt', 'odt', 'ods', 'odp', 'pages']:
                    endpoint = "forms/libreoffice/convert"
                else:
                    endpoint = "forms/chromium/convert/html"
            else:
                # URL conversion always uses chromium
                endpoint = "forms/chromium/convert/url"

            # Send request with proper content type for URL inputs
            if file:
                response = await client.post(
                    f"{service_url}/{endpoint}",
                    files=files,
                    data=data
                )
            else:
                # For URL inputs, send as multipart/form-data using `files` form fields
                response = await client.post(
                    f"{service_url}/{endpoint}",
                    files=files
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
        if file:
            base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        else:
            # For URLs, use a generic name based on the URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "url_content"
        
        output_filename = f"{base_name}.{output_format}"

        return StreamingResponse(
            BytesIO(response.content),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except httpx.RequestError as e:
        logger.error(f"Request error for {service}: {e}")
        # Clean up temp files on error
        if conversion_metadata.get('temp_file_path'):
            cleanup_conversion_temp_files(conversion_metadata)
        raise HTTPException(status_code=503, detail=f"Service {service} unavailable")
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        # Clean up temp files on error
        if conversion_metadata.get('temp_file_path'):
            cleanup_conversion_temp_files(conversion_metadata)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
    finally:
        # Clean up temp file wrapper if it exists
        if temp_file_wrapper:
            await temp_file_wrapper.close()


# Resume/CV/Cover Letter Priority Conversions
@router.post("/docx-pdf")
async def convert_docx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to PDF (Resume/CV priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("docx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="pdf", service=service)


@router.post("/pptx-pdf")
async def convert_pptx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to PDF (Presentation priority - high quality via Gotenberg)"""
    service, description = get_primary_conversion("pptx", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pptx", output_format="pdf", service=service)


@router.post("/ppt-pdf")
async def convert_ppt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert PPT to PDF (Legacy presentation priority)"""
    service, description = get_primary_conversion("ppt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="ppt", output_format="pdf", service=service)


@router.post("/html-pdf")
async def convert_html_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert HTML to PDF (Web content priority - high fidelity via Gotenberg)"""
    service, description = get_primary_conversion("html", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="pdf", service=service)


@router.post("/md-pdf")
async def convert_md_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to PDF (Text content priority)"""
    service, description = get_primary_conversion("md", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="md", output_format="pdf", service=service)


@router.post("/tex-pdf")
async def convert_tex_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to PDF (Academic content priority)"""
    service, description = get_primary_conversion("tex", "pdf") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="pdf", service=service)


@router.post("/txt-pdf")
async def convert_txt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Text to PDF (Simple content priority)"""
    service, description = get_primary_conversion("txt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="txt", output_format="pdf", service=service)


@router.post("/rtf-pdf")
async def convert_rtf_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert RTF to PDF (Legacy text format priority)"""
    service, description = get_primary_conversion("rtf", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="rtf", output_format="pdf", service=service)


@router.post("/odt-pdf")
async def convert_odt_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODT to PDF (Open document priority)"""
    service, description = get_primary_conversion("odt", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odt", output_format="pdf", service=service)


# JSON Structure Extraction (Unstructured IO priority)
@router.post("/docx-json")
async def convert_docx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("docx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="json", service=service)


@router.post("/pdf-json")
async def convert_pdf_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PDF to JSON structure (Document analysis)"""
    service, description = get_primary_conversion("pdf", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pdf", output_format="json", service=service)


@router.post("/pptx-json")
async def convert_pptx_to_json(request: Request, file: UploadFile = File(...)):
    """Convert PPTX to JSON structure (Presentation analysis)"""
    service, description = get_primary_conversion("pptx", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pptx", output_format="json", service=service)


@router.post("/html-json")
async def convert_html_to_json(request: Request, file: UploadFile = File(...)):
    """Convert HTML to JSON structure (Web content analysis)"""
    service, description = get_primary_conversion("html", "json") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="json", service=service)


# Markdown Conversions (Pandoc priority)
@router.post("/docx-md")
async def convert_docx_to_md(request: Request, file: UploadFile = File(...)):
    """Convert DOCX to Markdown (Content extraction)"""
    service, description = get_primary_conversion("docx", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="docx", output_format="md", service=service)


@router.post("/html-md")
async def convert_html_to_md(request: Request, file: UploadFile = File(...)):
    """Convert HTML to Markdown (Content extraction)"""
    service, description = get_primary_conversion("html", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="md", service=service)


@router.post("/pdf-md")
async def convert_pdf_to_md(request: Request, file: UploadFile = File(...)):
    """Convert PDF to Markdown (Content extraction)"""
    service, description = get_primary_conversion("pdf", "md") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, file=file, input_format="pdf", output_format="md", service=service)


@router.post("/tex-md")
async def convert_tex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="md", service=service)


@router.post("/latex-md")
async def convert_latex_to_md(request: Request, file: UploadFile = File(...)):
    """Convert LaTeX to Markdown (Academic content priority - alias for tex-md)"""
    service, description = get_primary_conversion("tex", "md") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="tex", output_format="md", service=service)


# DOCX Conversions
@router.post("/md-docx")
async def convert_md_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Markdown to DOCX (Document creation)"""
    service, description = get_primary_conversion("md", "docx") or (ConversionService.PANDOC, "Fallback")
    return await _convert_file(request, file=file, input_format="md", output_format="docx", service=service)


@router.post("/html-docx")
async def convert_html_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert HTML to DOCX (Document creation)"""
    service, description = get_primary_conversion("html", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="html", output_format="docx", service=service)


@router.post("/rtf-docx")
async def convert_rtf_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert RTF to DOCX (Format upgrade)"""
    service, description = get_primary_conversion("rtf", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="rtf", output_format="docx", service=service)


@router.post("/txt-docx")
async def convert_txt_to_docx(request: Request, file: UploadFile = File(...)):
    """Convert Text to DOCX (Document creation)"""
    service, description = get_primary_conversion("txt", "docx") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="txt", output_format="docx", service=service)


# Additional Conversions
@router.post("/xlsx-pdf")
async def convert_xlsx_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLSX to PDF (Spreadsheet to PDF)"""
    service, description = get_primary_conversion("xlsx", "pdf") or (ConversionService.GOTENBERG, "Fallback")
    return await _convert_file(request, file=file, input_format="xlsx", output_format="pdf", service=service)


@router.post("/xls-pdf")
async def convert_xls_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert XLS to PDF (Legacy spreadsheet to PDF)"""
    service, description = get_primary_conversion("xls", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="xls", output_format="pdf", service=service)


@router.post("/epub-pdf")
async def convert_epub_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert EPUB to PDF (E-book to PDF)"""
    service, description = get_primary_conversion("epub", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="epub", output_format="pdf", service=service)


@router.post("/ods-pdf")
async def convert_ods_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODS to PDF (OpenDocument spreadsheet to PDF)"""
    service, description = get_primary_conversion("ods", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="ods", output_format="pdf", service=service)


@router.post("/odp-pdf")
async def convert_odp_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert ODP to PDF (OpenDocument presentation to PDF)"""
    service, description = get_primary_conversion("odp", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="odp", output_format="pdf", service=service)


# Apple Pages Conversions
@router.post("/pages-pdf")
async def convert_pages_to_pdf(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to PDF"""
    service, description = get_primary_conversion("pages", "pdf") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pages", output_format="pdf", service=service)


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


@router.post("/pages-txt")
async def convert_pages_to_txt(request: Request, file: UploadFile = File(...)):
    """Convert Apple Pages to TXT"""
    service, description = get_primary_conversion("pages", "txt") or (ConversionService.LIBREOFFICE, "Fallback")
    return await _convert_file(request, file=file, input_format="pages", output_format="txt", service=service)


# URL-based conversion endpoints
@router.post("/url-pdf")
async def convert_url_to_pdf(request: Request, url: str = Form(...)):
    """Convert URL to PDF (Gotenberg - high-fidelity web to PDF)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "pdf") or (ConversionService.GOTENBERG, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="pdf", service=service)


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


@router.post("/url-txt")
async def convert_url_to_txt(request: Request, url: str = Form(...)):
    """Convert URL to plain text (Unstructured-IO - text extraction)"""
    # Validate URL
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format. URL must be a valid HTTP or HTTPS URL.")
    
    service, description = get_primary_conversion("url", "txt") or (ConversionService.UNSTRUCTURED_IO, "Fallback")
    return await _convert_file(request, url=url, input_format="auto", output_format="txt", service=service)


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

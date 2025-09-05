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

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/convert", tags=["conversions"])

# Service URL mappings (should match main app)
SERVICE_URLS = {
    ConversionService.UNSTRUCTURED_IO: "http://unstructured-io:8000",
    ConversionService.LIBREOFFICE: "http://libreoffice:2004",
    ConversionService.PANDOC: "http://pandoc:3000",
    ConversionService.GOTENBERG: "http://gotenberg:3000",
    ConversionService.LOCAL: None  # Local processing, no URL needed
}

# Get dynamic service URLs that match the main app configuration
def get_dynamic_service_urls():
    """Get service URLs with the same logic as the main app"""
    urls = get_service_urls()
    return {
        ConversionService.UNSTRUCTURED_IO: urls.get("unstructured-io"),
        ConversionService.LIBREOFFICE: urls.get("libreoffice"),
        ConversionService.PANDOC: urls.get("pandoc"),
        ConversionService.GOTENBERG: urls.get("gotenberg"),
        ConversionService.LOCAL: None
    }

# Use dynamic URLs
DYNAMIC_SERVICE_URLS = get_dynamic_service_urls()


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
        service_url = DYNAMIC_SERVICE_URLS[service]

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
                if input_format in ["tex", "latex"]:
                    pandoc_input_format = "latex"
                elif input_format in ["xls", "xlsx"]:
                    pandoc_input_format = "xlsx"
                elif input_format == "ods":
                    pandoc_input_format = "opendocument"
                else:
                    pandoc_input_format = input_format
                data["extra_args"] = f"--from={pandoc_input_format}"
            
            # Ensure HTML input format is explicitly specified
            if input_format == "html":
                if "extra_args" in data:
                    data["extra_args"] += " --from=html"
                else:
                    data["extra_args"] = "--from=html"

            # Add output format specific arguments
            if output_format == "txt":
                # For plain text output, use 'plain' writer to avoid markdown-like formatting
                # and include standalone to preserve title information
                if "extra_args" in data:
                    data["extra_args"] += " --to=plain --standalone"
                else:
                    data["extra_args"] = "--to=plain --standalone"
            elif output_format == "html":
                # For HTML output, use standalone to include title information
                if "extra_args" in data:
                    data["extra_args"] += " --standalone"
                else:
                    data["extra_args"] = "--standalone"
            elif output_format == "md":
                # For Markdown output, use standalone to include title information
                if "extra_args" in data:
                    data["extra_args"] += " --standalone"
                else:
                    data["extra_args"] = "--standalone"

            response = await client.post(
                f"{service_url}/convert",
                files=files,
                data=data
            )

        elif service == ConversionService.GOTENBERG:
            # Gotenberg supports both files and URLs
            if file:
                file_content = await file.read()
                # For HTML files, use the correct endpoint and filename
                if input_format == 'html':
                    files = {"index.html": ("index.html", BytesIO(file_content), f"application/{input_format}")}
                    endpoint = "forms/chromium/convert/html"
                elif input_format in ['docx', 'pptx', 'xlsx', 'xls', 'ppt', 'odt', 'ods', 'odp', 'pages', 'numbers']:
                    files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
                    endpoint = "forms/libreoffice/convert"
                else:
                    files = {"files": (file.filename, BytesIO(file_content), f"application/{input_format}")}
                    endpoint = "forms/chromium/convert/html"
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
            if not file:
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

        elif service == ConversionService.LOCAL:
            # Local processing - handle files or URLs
            if output_format == "html" and url:
                # Special case: URL to HTML - fetch raw HTML content
                from .utils.url_fetcher import fetch_url_content
                
                try:
                    url_data = await fetch_url_content(url)
                    content = url_data['content']
                    
                    # Ensure content is properly decoded as UTF-8 text
                    if isinstance(content, bytes):
                        content = content.decode('utf-8', errors='replace')
                    
                    # Generate output filename from URL
                    from urllib.parse import urlparse
                    parsed_url = urlparse(url)
                    base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
                    if not base_name or base_name == '_':
                        base_name = "url_content"
                    output_filename = f"{base_name}.html"
                    
                    return StreamingResponse(
                        BytesIO(content.encode('utf-8')),
                        media_type="text/html",
                        headers={"Content-Disposition": f"attachment; filename={output_filename}"}
                    )
                except Exception as e:
                    logger.error(f"URL to HTML conversion failed: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to fetch URL content: {str(e)}")
            elif not file:
                raise HTTPException(status_code=400, detail="Local processing only supports file input for non-HTML formats")
            
            file_content = await file.read()
            
            # Use the local conversion factory
            factory = LocalConversionFactory()
            content, media_type, output_filename = factory.convert(file_content, file.filename, input_format, output_format)
            
            # Return directly as StreamingResponse (skip the normal response handling)
            return StreamingResponse(
                BytesIO(content.encode('utf-8')),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={output_filename}"}
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


# Conversion Routes (sorted alphabetically by input format, then by output format)

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

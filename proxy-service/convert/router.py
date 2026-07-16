"""
Conversion router for the /convert endpoints.

This module provides high-level conversion aliases that automatically route
to the most reliable service for each conversion type.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
from typing import BinaryIO, Optional

# Import local conversion factory

from .config import ConversionService
from .utils.conversion_lookup import (
    get_primary_conversion,
    get_supported_conversions,
    get_conversion_methods,
    DYNAMIC_SERVICE_URLS
)
from .utils.conversion_core import (
    _convert_file
)

# Import URL processing module
from .utils.url_processor import URLProcessor
from .utils.error_handling import create_http_exception, ErrorCode, validate_format_parameter
from .utils.screenshot_utils import (
    DEFAULT_SCREENSHOT_WIDTH,
    DEFAULT_THUMB_JPEG_QUALITY,
    DEFAULT_THUMB_WIDTH,
    copy_response_to_spooled_pdf,
    get_input_format,
    raise_pyconvert_error,
    validate_render_request,
    validate_upload_size,
)
from .utils.resource_limits import MAX_ERROR_BYTES, bounded_response_stream, read_response_bounded

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/convert", tags=["conversions"])

#-- URL to {format} conversions
#-------------------------------------------------------------------------------
@router.post("/url-{output_format}")
async def convert_url_dynamic(request: Request, output_format: str, url: str = Form(...), user_agent: Optional[str] = Form(None)):
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
        raise create_http_exception(
            ErrorCode.INVALID_FORMAT,
            details=f"Unsupported output format: {output_format}. Supported formats: {sorted(valid_output_formats)}"
        )
    
    # Use dedicated URL manager to determine input format and prepare conversion
    url_manager = URLProcessor()
    conversion_input = await url_manager.process_url_conversion(url, output_format, user_agent=user_agent)
    
    # Get detected input format
    input_format = conversion_input.metadata["detected_format"]
    
    # For non-passthrough conversions, validate that the conversion pair exists
    if input_format != output_format or input_format not in PASSTHROUGH_FORMATS:
        from .utils.conversion_lookup import get_conversion_methods
        conversion_methods = get_conversion_methods(input_format, output_format)
        if not conversion_methods:
            raise create_http_exception(
                ErrorCode.CONVERSION_NOT_SUPPORTED,
                details=f"No conversion available from {input_format} to {output_format}",
                input_format=input_format,
                output_format=output_format
            )
    
    # Pass to standard conversion pipeline (which handles passthrough automatically)
    return await _convert_file(
        request=request,
        file=None,
        url_input=conversion_input,
        input_format=input_format,
        output_format=output_format
    )

#-- Consolidated {input}-{output} format converter
#-------------------------------------------------------------------------------
@router.post("/{input_format}-{output_format}")
async def convert_dynamic(request: Request, input_format: str, output_format: str, file: UploadFile = File(...)):
    """Convert file from input_format to output_format (dynamic endpoint)"""
    
    # Validate format parameters
    validate_format_parameter(input_format, "input_format", 2, 7)
    validate_format_parameter(output_format, "output_format", 2, 7)
    
    # Check if conversion pair exists in config
    conversion_methods = get_conversion_methods(input_format, output_format)
    if not conversion_methods:
        raise create_http_exception(
            ErrorCode.CONVERSION_NOT_SUPPORTED,
            details=f"No conversion available from {input_format} to {output_format}",
            input_format=input_format,
            output_format=output_format
        )
    
    # Extract extra parameters from the request
    form_data = await request.form()
    extra_params = {}
    for key, value in form_data.items():
        # Skip the file parameter
        if key != 'file':
            extra_params[key] = value
    
    # Proceed with conversion
    return await _convert_file(request, file=file, input_format=input_format, output_format=output_format, extra_params=extra_params)


#-- Document screenshot and thumbnail rendering
#-------------------------------------------------------------------------------
_SCREENSHOT_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


async def _stream_rendered_pdf(
    request: Request,
    pdf_file: BinaryIO,
    filename: str,
    page: str,
    width: int,
    image_format: str,
    quality: Optional[int],
) -> StreamingResponse:
    """Upload a file-backed PDF to PyConvert and stream its image response."""
    pyconvert_url = f"{DYNAMIC_SERVICE_URLS[ConversionService.PYMUPDF]}/pymupdf/render-pages"
    data: dict[str, str] = {
        "page": str(page),
        "max_width": str(width),
        "format": image_format,
    }
    if quality is not None:
        data["quality"] = str(quality)

    pdf_file.seek(0)
    client = request.app.state.pyconvert_client
    request_body = client.build_request(
        "POST",
        pyconvert_url,
        data=data,
        files={"file": (filename, pdf_file, "application/pdf")},
    )
    try:
        response = await client.send(request_body, stream=True)
    except httpx.RequestError as exc:
        raise create_http_exception(
            ErrorCode.SERVICE_UNAVAILABLE,
            details=f"PyMuPDF rendering service is unavailable: {exc}",
            service="pymupdf",
        ) from exc

    if response.status_code >= 400:
        try:
            raise_pyconvert_error(
                response.status_code,
                await read_response_bounded(response, MAX_ERROR_BYTES),
            )
        finally:
            if not response.is_closed:
                await response.aclose()

    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in _SCREENSHOT_HOP_BY_HOP_HEADERS
    }

    return StreamingResponse(
        bounded_response_stream(response),
        status_code=response.status_code,
        headers=headers,
    )


async def _render_screenshot(
    request: Request,
    file: UploadFile,
    page: str,
    width: int,
    image_format: str,
    quality: Optional[int],
) -> StreamingResponse:
    """Render an uploaded document directly or through the established PDF route."""
    validate_upload_size(file)
    validate_render_request(page, width, image_format, quality)
    input_format = get_input_format(file.filename or "")

    if input_format == "pdf":
        await file.seek(0)
        return await _stream_rendered_pdf(
            request, file.file, file.filename or "document.pdf", page, width, image_format, quality
        )

    if not get_conversion_methods(input_format, "pdf"):
        raise create_http_exception(
            ErrorCode.CONVERSION_NOT_SUPPORTED,
            details=f"No PDF conversion is available for .{input_format} files",
            input_format=input_format,
            output_format="pdf",
        )

    await file.seek(0)
    conversion_response = await _convert_file(
        request=request,
        file=file,
        input_format=input_format,
        output_format="pdf",
    )
    converted_pdf = await copy_response_to_spooled_pdf(conversion_response)
    try:
        return await _stream_rendered_pdf(
            request,
            converted_pdf,
            f"{file.filename.rsplit('.', 1)[0] if file.filename else 'document'}.pdf",
            page,
            width,
            image_format,
            quality,
        )
    finally:
        # httpx has consumed the entire upload before send() returns response headers.
        converted_pdf.close()


@router.post("/screenshot")
async def screenshot(
    request: Request,
    file: UploadFile = File(...),
    page: str = Form("1"),
    width: int = Form(DEFAULT_SCREENSHOT_WIDTH),
    image_format: str = Form("jpg", alias="format"),
    quality: Optional[int] = Form(None),
):
    """Render page 1, a selected page, or all document pages as PNG/JPG images."""
    return await _render_screenshot(request, file, page, width, image_format, quality)


@router.post("/thumb")
async def thumbnail(
    request: Request,
    file: UploadFile = File(...),
    page: str = Form("1"),
    width: int = Form(DEFAULT_THUMB_WIDTH),
    image_format: str = Form("jpg", alias="format"),
    quality: Optional[int] = Form(None),
):
    """Render a thumbnail; defaults are page 1, 480px maximum width, and JPG."""
    if quality is None and image_format.strip().lower() in {"jpg", "jpeg"}:
        quality = DEFAULT_THUMB_JPEG_QUALITY
    return await _render_screenshot(request, file, page, width, image_format, quality)


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
        raise create_http_exception(
            ErrorCode.CONVERSION_NOT_SUPPORTED,
            details=f"Conversion {input_format} to {output_format} not supported",
            input_format=input_format,
            output_format=output_format
        )

    service, description = methods

    info = {
        "input_format": input_format,
        "output_format": output_format,
        "primary_service": service.value,
        "description": description,
        "url_support": {
            "direct_url": service.value in ["gotenberg"],  # Services that support direct URL input
            "fetch_required": service.value in ["unstructured-io", "libreoffice", "pyconvert"],
            "supported": True
        }
    }

    if url:
        # Add URL-specific information if URL is provided
        try:
            url_manager = URLProcessor()
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
        url_manager = URLProcessor()
        
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

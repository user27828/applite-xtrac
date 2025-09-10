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
    get_service_urls,
    get_conversion_methods
)
from .utils.conversion_chaining import (
    get_conversion_steps,
    is_chained_conversion
)
from .utils.conversion_core import (
    _convert_file,
    _get_service_client,
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
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported output format: {output_format}. Supported formats: {sorted(valid_output_formats)}"
        )
    
    # Use dedicated URL manager to determine input format and prepare conversion
    url_manager = URLConversionManager()
    conversion_input = await url_manager.process_url_conversion(url, output_format, user_agent=user_agent)
    
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

#-- Consolidated {input}-{output} format converter
#-------------------------------------------------------------------------------
@router.post("/{input_format}-{output_format}")
async def convert_dynamic(request: Request, input_format: str, output_format: str, file: UploadFile = File(...)):
    """Convert file from input_format to output_format (dynamic endpoint)"""
    
    # Validate format lengths (2-7 characters to support all format names)
    if not (2 <= len(input_format) <= 7):
        raise HTTPException(status_code=400, detail=f"Input format must be 2-7 characters, got {len(input_format)}")
    if not (2 <= len(output_format) <= 7):
        raise HTTPException(status_code=400, detail=f"Output format must be 2-7 characters, got {len(output_format)}")
    
    # Check if conversion pair exists in config
    conversion_methods = get_conversion_methods(input_format, output_format)
    if not conversion_methods:
        raise HTTPException(
            status_code=400, 
            detail=f"No conversion available from {input_format} to {output_format}"
        )
    
    # Proceed with conversion
    return await _convert_file(request, file=file, input_format=input_format, output_format=output_format)


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


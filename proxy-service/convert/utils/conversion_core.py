"""
Core conversion utilities for the /convert endpoints.

This module contains the main conversion logic, service client management,
and utility functions that were moved from router.py to keep the router clean.
"""

import logging
import httpx
import re
import mimetypes
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from fastapi import HTTPException, Request, UploadFile, Form
from fastapi.responses import StreamingResponse
from io import BytesIO
import asyncio

# Import local conversion factory
from .._local_ import LocalConversionFactory

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

from ..config import (
    ConversionService,
    PANDOC_FORMAT_MAP,
    UNSTRUCTURED_IO_MIME_MAPPING,
    SPECIAL_HANDLERS
)
from .conversion_lookup import (
    get_primary_conversion,
    get_supported_conversions,
    get_service_urls,
    get_all_conversions
)
from .url_conversion_manager import ConversionInput
from .url_fetcher import fetch_url_content

# Set up logging
logger = logging.getLogger(__name__)

def get_mime_type(extension: str) -> str:
    """
    Get MIME type for a file extension using Python's mimetypes module.
    
    Args:
        extension: File extension without the dot (e.g., 'pdf', 'docx')
        
    Returns:
        MIME type string, or default fallback if not found
    """
    if not extension:
        return "application/octet-stream"
    
    # Use mimetypes.guess_type for standard MIME type detection
    mime_type, _ = mimetypes.guess_type(f"file.{extension}")
    
    if mime_type:
        # Handle special case for tex files - mimetypes returns text/x-tex
        # but we want application/x-tex for consistency
        if extension == "tex" and mime_type == "text/x-tex":
            return "application/x-tex"
        return mime_type
    
    # Fallback for unknown extensions
    return f"application/{extension}"

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
    url_input: Optional['ConversionInput'] = None,
    input_format: str = "",
    output_format: str = "",
    service: Optional[ConversionService] = None,
    extra_params: Optional[dict] = None
) -> StreamingResponse:
    """
    Generic file conversion function that routes to the appropriate service.
    Supports both file upload, URL input, and unified ConversionInput, and handles both simple and chained conversions.
    Automatically tries fallback services if the primary service fails.

    Args:
        request: FastAPI request object
        file: Uploaded file (optional if url or url_input is provided)
        url: URL to convert (optional if file or url_input is provided) - legacy support
        url_input: Unified ConversionInput object (optional if file or url is not provided)
        input_format: Input file format (required)
        output_format: Desired output format (required)
        service: Conversion service to use (optional - auto-determined if not provided)
        extra_params: Additional parameters for the service

    Returns:
        StreamingResponse with converted file
    """
    # Validate input parameters
    input_count = sum([file is not None, url is not None, url_input is not None])
    if input_count == 0:
        raise HTTPException(status_code=400, detail="Either file, url, or url_input must be provided")
    if input_count > 1:
        raise HTTPException(status_code=400, detail="Cannot provide multiple input types (file, url, url_input)")
    
    # Handle legacy URL input by converting to new format
    if url and not url_input:
        from .url_conversion_manager import URLConversionManager
        url_manager = URLConversionManager()
        url_input = await url_manager.process_url_conversion(url, output_format)
    
    # Handle same-format conversions specially
    print(f"DEBUG: Checking for passthrough - url_input: {url_input is not None}, has_metadata: {url_input and hasattr(url_input, 'metadata')}")
    if url_input and hasattr(url_input, 'metadata'):
        print(f"DEBUG: url_input metadata: {url_input.metadata}")
        print(f"DEBUG: passthrough_conversion flag: {url_input.metadata.get('passthrough_conversion', False)}")
    
    if url_input and hasattr(url_input, 'metadata') and url_input.metadata.get('passthrough_conversion'):
        print(f"DEBUG: Passthrough conversion detected for {input_format} to {output_format}")
        # For passthrough conversions, fetch the URL content and return it directly
        from .url_fetcher import fetch_url_content
        
        try:
            print(f"DEBUG: Fetching URL content from {url_input.url}")
            # Fetch the URL content
            fetch_result = await fetch_url_content(url_input.url)
            print(f"DEBUG: Fetched content length: {len(fetch_result['content'])}")
            
            # Determine content type
            content_type_map = {
                "html": "text/html",
                "json": "application/json", 
                "txt": "text/plain",
                "md": "text/markdown",
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
            content_type = content_type_map.get(output_format, "application/octet-stream")
            print(f"DEBUG: Content type: {content_type}")
            
            # Return the content directly as a streaming response
            content_bytes = fetch_result['content']
            print(f"DEBUG: Returning streaming response with {len(content_bytes)} bytes")
            return StreamingResponse(
                BytesIO(content_bytes),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=converted.{output_format}",
                    "Content-Length": str(len(content_bytes))
                }
            )
            
        except Exception as e:
            print(f"DEBUG: Error in passthrough conversion: {e}")
            logger.error(f"Failed to fetch URL content for passthrough conversion: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL content: {str(e)}")
    
    # Check if this is a chained conversion
    from .conversion_chaining import is_chained_conversion
    if is_chained_conversion(input_format, output_format):
        # Import required functions for chaining
        from .conversion_chaining import get_conversion_steps, chain_conversions, ConversionStep
        from .special_handlers import process_presentation_to_html
        from ..config import SPECIAL_HANDLERS
        
        # Handle chained conversion - only file input supported for now
        # TODO: Add support for ConversionInput in chained conversions
        if not file and not url_input:
            raise HTTPException(status_code=400, detail="Chained conversions currently only support file input")
        
        # Get input content
        if file:
            file_content = await file.read()
            input_filename = file.filename
        elif url_input:
            # For URL inputs in chained conversions, we need to read from the temp file
            if hasattr(url_input, 'temp_file_wrapper'):
                await url_input.temp_file_wrapper.seek(0)
                file_content = await url_input.temp_file_wrapper.read()
                input_filename = url_input.temp_file_wrapper.filename
            else:
                raise HTTPException(status_code=400, detail="URL input not supported for chained conversions yet")
        else:
            raise HTTPException(status_code=400, detail="No valid input for chained conversion")
        
        try:
            # Get conversion steps from config
            steps_data = get_conversion_steps(input_format, output_format)
            
            # Convert to ConversionStep objects
            conversion_steps = []
            for step_data in steps_data:
                if len(step_data) == 4:
                    step_service, step_input, step_output, description = step_data
                    # Handle extra params for specific cases
                    step_extra_params = {}
                    if step_service == ConversionService.PANDOC and step_input in ["tex", "latex"]:
                        step_extra_params = {"extra_args": "--from=latex"}
                    elif step_service == ConversionService.PANDOC and step_input == "docx" and step_output == "md":
                        step_extra_params = {"extra_args": "--from=docx"}
                    
                    conversion_steps.append(ConversionStep(
                        service=step_service,
                        input_format=step_input,
                        output_format=step_output,
                        extra_params=step_extra_params,
                        description=description
                    ))
                elif len(step_data) == 5:
                    # Special case with additional configuration
                    step_service, step_input, step_output, description, special_config = step_data
                    
                    # Check if this step has a special handler
                    if special_config.get("special_handler"):
                        # Handle special case
                        handler_name = special_config["special_handler"]
                        
                        if handler_name in SPECIAL_HANDLERS:
                            # Import and call the special handler
                            if handler_name == "presentation_to_html":
                                # For special handlers, we need to execute the chain up to this point
                                # and then call the special handler
                                if len(conversion_steps) > 0:
                                    # Execute the chain up to the special step
                                    intermediate_result = await chain_conversions(
                                        request=request,
                                        initial_file_content=file_content,
                                        initial_filename=file.filename,
                                        conversion_steps=conversion_steps,
                                        final_output_format=step_input,  # Intermediate format
                                        final_content_type="application/octet-stream"
                                    )
                                    
                                    # Extract content from intermediate result
                                    intermediate_content = b""
                                    async for chunk in intermediate_result.body_iterator:
                                        intermediate_content += chunk
                                    
                                    # Call special handler with intermediate content
                                    return await process_presentation_to_html(
                                        request, intermediate_content, step_input, step_output, special_config
                                    )
                                else:
                                    # First step is special - call handler directly
                                    return await process_presentation_to_html(
                                        request, file_content, input_format, output_format, special_config
                                    )
                        else:
                            logger.error(f"Unknown special handler: {handler_name}")
                            raise HTTPException(status_code=500, detail=f"Unknown special handler: {handler_name}")
                    else:
                        # Regular step with extra config but no special handler
                        conversion_steps.append(ConversionStep(
                            service=step_service,
                            input_format=step_input,
                            output_format=step_output,
                            extra_params=special_config,
                            description=description
                        ))
            
            # Determine content type
            content_type_map = {
                "md": "text/markdown",
                "html": "text/html",
                "json": "application/json",
                "txt": "text/plain",
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
            final_content_type = content_type_map.get(output_format, "application/octet-stream")
            
            # Execute chained conversion
            return await chain_conversions(
                request=request,
                initial_file_content=file_content,
                initial_filename=file.filename,
                conversion_steps=conversion_steps,
                final_output_format=output_format,
                final_content_type=final_content_type
            )
            
        except Exception as e:
            logger.error(f"Error in chained conversion {input_format}→{output_format}: {e}")
            raise HTTPException(status_code=500, detail=f"Chained conversion failed: {str(e)}")
    
    # For simple conversions, try services in order until one succeeds
    if service is None:
        # Get all available services for this conversion
        from .conversion_lookup import get_all_conversions
        available_services = get_all_conversions(input_format, output_format)
        if not available_services:
            raise HTTPException(status_code=400, detail=f"No conversion available for {input_format} to {output_format}")
    else:
        # If a specific service was requested, only try that one
        available_services = [(service, "Specified service")]
    
    # Try each service in order
    last_error = None
    for service_to_try, service_desc in available_services:
        try:
            logger.info(f"Trying service {service_to_try.value} for {input_format}→{output_format}")
            
            # Get input for this service
            current_file = file
            current_url = None
            
            if url_input:
                # Use the new ConversionInput system
                try:
                    print(f"DEBUG: Getting input for service {service_to_try}")
                    input_for_service = await url_input.get_for_service(service_to_try)
                    print(f"DEBUG: Input type: {type(input_for_service)}")
                    
                    if isinstance(input_for_service, str):
                        # Direct URL input
                        current_url = input_for_service
                        current_file = None
                        print(f"DEBUG: Using direct URL: {current_url}")
                    else:
                        # File input (UploadFile or wrapper)
                        current_file = input_for_service
                        current_url = None
                        print(f"DEBUG: Using file input: {current_file.filename if hasattr(current_file, 'filename') else 'unknown'}")
                        if hasattr(current_file, 'file_path'):
                            print(f"DEBUG: File path: {current_file.file_path}")
                            import os
                            print(f"DEBUG: File exists: {os.path.exists(current_file.file_path)}")
                        
                except Exception as e:
                    print(f"DEBUG: Error getting input for service: {e}")
                    logger.error(f"Failed to get input for service {service_to_try}: {e}")
                    raise
            elif url:
                # Legacy URL handling - should have been converted to url_input above
                raise HTTPException(status_code=500, detail="Legacy URL input should have been converted")

            # Get service client
            client = await _get_service_client(service_to_try, request)

            # Prepare request based on service
            service_url = DYNAMIC_SERVICE_URLS[service_to_try]

            if service_to_try == ConversionService.UNSTRUCTURED_IO:
                # Unstructured IO supports both files and URLs through the new system
                if current_file:
                    # Read file content
                    await current_file.seek(0)  # Reset file pointer
                    file_content = await current_file.read()
                    
                    # Get MIME type for input file using standard library
                    mime_type = get_mime_type(input_format)
                    files = {"files": (current_file.filename, BytesIO(file_content), mime_type)}
                    # Map output_format to MIME types for Unstructured-IO
                    unstructured_output_format = UNSTRUCTURED_IO_MIME_MAPPING.get(output_format, output_format)
                    
                    # Extract all user-provided parameters from the request
                    if extra_params is None:
                        extra_params = await extract_request_params(request)
                    
                    # Default to 'auto' strategy, but allow override from extra_params
                    strategy = extra_params.get("strategy", "auto") if extra_params else "auto"
                    data = {"output_format": unstructured_output_format, "strategy": strategy}
                    
                    # Add any additional parameters from extra_params to the request data
                    if extra_params:
                        for key, value in extra_params.items():
                            if key not in data:  # Don't override existing parameters
                                data[key] = value

                elif current_url:
                    # Direct URL input for Unstructured-IO (if supported)
                    data = {"url": current_url, "output_format": output_format}
                    files = None
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="No valid input for Unstructured-IO conversion"
                    )

                # For markdown, text, and HTML outputs, we need to get JSON and convert locally
                if output_format in ["md", "txt", "html"]:
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
                        logger.error(f"Service {service_to_try} returned {response.status_code}: {response.text}")
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Conversion failed: {response.text}"
                        )

                    # Parse JSON response and convert locally
                    if not UNSTRUCTURED_AVAILABLE or not dict_to_elements or not elements_to_md:
                        raise HTTPException(status_code=503, detail="Unstructured library not available for local conversion")

                    json_data = response.json()
                    
                    # Use consolidated unstructured processing utility
                    from .unstructured_utils import process_unstructured_json_to_content
                    content = process_unstructured_json_to_content(json_data, output_format, fix_tables=True)
                    media_type = "text/markdown" if output_format == "md" else "text/html" if output_format == "html" else "text/plain"

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

            elif service_to_try == ConversionService.LIBREOFFICE:
                # LibreOffice expects multipart/form-data with convert-to parameter
                if not current_file:
                    raise HTTPException(status_code=400, detail="LibreOffice only supports file input")
                
                await current_file.seek(0)  # Reset file pointer
                file_content = await current_file.read()
                # Get MIME type for input file using standard library
                mime_type = get_mime_type(input_format)
                files = {"file": (current_file.filename, BytesIO(file_content), mime_type)}
                data = {"convert-to": output_format}

                response = await client.post(
                    f"{service_url}/request",
                    files=files,
                    data=data
                )

            elif service_to_try == ConversionService.PANDOC:
                if not current_file:
                    raise HTTPException(status_code=400, detail="Pandoc only supports file input")
                    
                await current_file.seek(0)  # Reset file pointer
                file_content = await current_file.read()
                files = {"file": (current_file.filename, BytesIO(file_content), f"application/{input_format}")}
                data = {"output_format": output_format}

                # Map input format to pandoc format name and add as extra arg
                pandoc_input_format = PANDOC_FORMAT_MAP.get(input_format, input_format)
                
                # Special handling for LaTeX to PDF: don't specify --from=latex to avoid parsing issues
                if input_format in ["latex", "tex"] and output_format == "pdf":
                    # For LaTeX to PDF, let pandoc auto-detect and use pdflatex directly
                    data["extra_args"] = "--pdf-engine=pdflatex"
                elif pandoc_input_format != "markdown":  # Default is markdown
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
                elif output_format == "pdf" and input_format in ["latex", "tex"]:
                    # For LaTeX to PDF, specify the PDF engine explicitly to ensure proper compilation
                    if "extra_args" in data:
                        data["extra_args"] += " --pdf-engine=pdflatex --standalone"
                    else:
                        data["extra_args"] = "--pdf-engine=pdflatex --standalone"

                response = await client.post(
                    f"{service_url}/convert",
                    files=files,
                    data=data
                )

            elif service_to_try == ConversionService.GOTENBERG:
                # Gotenberg supports both files and URLs
                if current_file:
                    await current_file.seek(0)  # Reset file pointer
                    file_content = await current_file.read()
                    # For HTML files, use the correct endpoint and filename
                    if input_format == 'html':
                        files = {"index.html": ("index.html", BytesIO(file_content), f"application/{input_format}")}
                        endpoint = "forms/chromium/convert/html"
                    elif input_format in ['docx', 'pptx', 'xlsx', 'xls', 'ppt', 'odt', 'ods', 'odp', 'pages', 'numbers']:
                        files = {"files": (current_file.filename, BytesIO(file_content), f"application/{input_format}")}
                        endpoint = "forms/libreoffice/convert"
                    else:
                        files = {"files": (current_file.filename, BytesIO(file_content), f"application/{input_format}")}
                        endpoint = "forms/chromium/convert/html"
                    data = {}
                elif current_url:
                    # URL input for Gotenberg - prepare multipart form-data fields
                    # Use the `files` parameter so httpx builds multipart/form-data.
                    print(f"DEBUG: Preparing Gotenberg URL request for: {current_url}")
                    files = {"url": (None, current_url)}
                    data = {}
                    endpoint = "forms/chromium/convert/url"
                    print(f"DEBUG: Gotenberg endpoint: {endpoint}")
                    print(f"DEBUG: Gotenberg files: {files}")
                else:
                    raise HTTPException(status_code=400, detail="No valid input for Gotenberg conversion")

                if extra_params:
                    # Place extra params into the multipart payload as form fields
                    for k, v in extra_params.items():
                        files[k] = (None, str(v))

                # Use the correct endpoint based on input type
                if not current_file:
                    # URL conversion always uses chromium
                    endpoint = "forms/chromium/convert/url"

                # Send request with proper content type for URL inputs
                if current_file:
                    response = await client.post(
                        f"{service_url}/{endpoint}",
                        files=files,
                        data=data
                    )
                else:
                    # For URL inputs, send as multipart/form-data using `files` form fields
                    print(f"DEBUG: Sending Gotenberg URL request to: {service_url}/{endpoint}")
                    response = await client.post(
                        f"{service_url}/{endpoint}",
                        files=files
                    )
                    print(f"DEBUG: Gotenberg response status: {response.status_code}")
                    print(f"DEBUG: Gotenberg response headers: {dict(response.headers)}")
                    print(f"DEBUG: Gotenberg response content length: {len(response.content)}")
                    print(f"DEBUG: Gotenberg response content type: {response.headers.get('content-type', 'unknown')}")

            elif service_to_try == ConversionService.LOCAL:
                # Local processing - handle files or URLs
                if output_format == "html" and current_url:
                    # Special case: URL to HTML - fetch raw HTML content
                    try:
                        url_data = await fetch_url_content(current_url)
                        content = url_data['content']
                        
                        # Ensure content is properly decoded as UTF-8 text
                        if isinstance(content, bytes):
                            content = content.decode('utf-8', errors='replace')
                        
                        # Generate output filename from URL
                        parsed_url = urlparse(current_url)
                        base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
                        if not base_name:
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
                elif not current_file:
                    raise HTTPException(status_code=400, detail="Local processing only supports file input for non-HTML formats")
                
                await current_file.seek(0)  # Reset file pointer
                file_content = await current_file.read()
                
                # Use the local conversion factory
                factory = LocalConversionFactory()
                content, media_type, output_filename = factory.convert(file_content, current_file.filename, input_format, output_format)
                
                # Return directly as StreamingResponse (skip the normal response handling)
                return StreamingResponse(
                    BytesIO(content.encode('utf-8')),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={output_filename}"}
                )

            else:
                raise HTTPException(status_code=500, detail=f"Unsupported service: {service_to_try}")
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Service {service_to_try} returned {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Conversion failed: {response.text}"
                )

            print(f"DEBUG: Response check passed for {service_to_try}, status: {response.status_code}")
            print(f"DEBUG: Response content length: {len(response.content)}")
            print(f"DEBUG: Response content type: {response.headers.get('content-type', 'unknown')}")

            # Determine content type based on output format
            content_type = get_mime_type(output_format)

            # Generate output filename
            if current_file:
                base_name = current_file.filename.rsplit(".", 1)[0] if "." in current_file.filename else current_file.filename
            elif current_url:
                # For URLs, use a generic name based on the URL
                parsed_url = urlparse(current_url)
                base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
                if not base_name:
                    base_name = "url_content"
            else:
                base_name = "converted_content"
            
            output_filename = f"{base_name}.{output_format}"

            print(f"DEBUG: About to create StreamingResponse for {service_to_try}")
            print(f"DEBUG: Content type: {content_type}")
            print(f"DEBUG: Output filename: {output_filename}")
            print(f"DEBUG: Response content length: {len(response.content)}")

            return StreamingResponse(
                BytesIO(response.content),
                media_type=content_type,
                headers={"Content-Disposition": f"attachment; filename={output_filename}"}
            )

        except httpx.RequestError as e:
            logger.error(f"Request error for {service_to_try}: {e}")
            print(f"DEBUG: RequestError caught for {service_to_try}: {e}")
            # Don't clean up resources here - keep them for other services to try
            # if url_input:
            #     await url_input.cleanup()
            last_error = HTTPException(status_code=503, detail=f"Service {service_to_try} unavailable")
            continue  # Try next service
        except Exception as e:
            logger.error(f"Conversion error with {service_to_try}: {e}")
            print(f"DEBUG: General exception caught for {service_to_try}: {e}")
            print(f"DEBUG: Exception type: {type(e)}")
            import traceback
            print(f"DEBUG: Exception traceback: {traceback.format_exc()}")
            # Don't clean up resources here - keep them for other services to try
            # if url_input:
            #     await url_input.cleanup()
            last_error = HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
            continue  # Try next service
        finally:
            # Only clean up on successful conversion - resources will be cleaned up by the response handler
            pass
    
    # If we get here without success, all services failed
    if last_error:
        # Clean up resources since no service succeeded
        if url_input:
            await url_input.cleanup()
        raise last_error
    else:
        # Clean up resources since no service succeeded
        if url_input:
            await url_input.cleanup()
        raise HTTPException(status_code=500, detail="All conversion services failed")


async def extract_request_params(request: Request) -> Dict[str, Any]:
    """
    Extract all form parameters from a multipart/form-data request.
    
    This function automatically extracts all user-provided parameters from the request
    and returns them as a dictionary that can be passed to the underlying service.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary of parameter names and values
    """
    params = {}
    
    # Parse the multipart form data
    try:
        form_data = await request.form()
        
        # Extract all form fields except 'file' and 'url' which are handled separately
        for field_name, field_value in form_data.items():
            if field_name not in ['file', 'url'] and field_value is not None:
                # Convert field value to appropriate type
                if isinstance(field_value, str):
                    # Try to convert to appropriate type
                    if field_value.lower() in ('true', 'false'):
                        params[field_name] = field_value.lower() == 'true'
                    elif field_value.isdigit():
                        params[field_name] = int(field_value)
                    elif field_value.replace('.', '').isdigit():
                        params[field_name] = float(field_value)
                    else:
                        params[field_name] = field_value
                else:
                    params[field_name] = field_value
                    
    except Exception as e:
        logger.warning(f"Failed to extract form parameters: {e}")
        # If form parsing fails, try to get query parameters as fallback
        params.update(dict(request.query_params))
    
    return params


def fix_table_text_as_html(json_data: list) -> list:
    """
    Fix table elements where text_as_html is missing content compared to text.
    
    This addresses the known issue in unstructured-io where table detection
    fails to properly populate text_as_html, particularly for header rows.
    
    Args:
        json_data: List of element dictionaries from unstructured-io
        
    Returns:
        Modified json_data with fixed table text_as_html fields
    """
    for item in json_data:
        if item.get('type') == 'Table':
            text = item.get('text', '').strip()
            text_as_html = item.get('metadata', {}).get('text_as_html', '').strip()
            
            # Skip if text_as_html already looks complete or text is empty
            if not text or (text_as_html and '<td>' in text_as_html and '</td>' in text_as_html and text_as_html.count('<td>') > text_as_html.count('<td></td>')):
                continue
                
            # Try to reconstruct HTML table from text
            reconstructed_html = _reconstruct_table_html(text)
            if reconstructed_html:
                # Ensure metadata dict exists
                if 'metadata' not in item:
                    item['metadata'] = {}
                item['metadata']['text_as_html'] = reconstructed_html
    
    return json_data


def _reconstruct_table_html(text: str) -> str:
    """
    Reconstruct HTML table markup from plain text table content.
    
    Handles various table formats:
    - Tab-separated values
    - Space-separated with consistent column structure
    - Multi-line table data
    
    Args:
        text: Plain text containing table data
        
    Returns:
        HTML table markup string, or empty string if reconstruction fails
    """
    if not text or not text.strip():
        return ""
        
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return ""
    
    # Try different parsing strategies
    table_data = []
    
    # Strategy 1: Tab-separated values
    if '\t' in text:
        for line in lines:
            if '\t' in line:
                cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
                if cells:
                    table_data.append(cells)
    
    # Strategy 2: Space-separated with consistent column count
    if not table_data:
        # Analyze all lines to find consistent column structure
        parsed_lines = []
        for line in lines:
            # First try splitting by multiple spaces
            cells = re.split(r'\s{2,}', line)
            cells = [cell.strip() for cell in cells if cell.strip()]
            
            # If that didn't split anything (single spaces), try single space split
            if len(cells) == 1 and ' ' in line:
                cells = line.split()
                
            if cells:
                parsed_lines.append(cells)
        
        # Find the most common column count (likely the table structure)
        if parsed_lines:
            col_counts = [len(line) for line in parsed_lines]
            most_common_cols = max(set(col_counts), key=col_counts.count)
            
            # Keep only lines with the most common column count
            table_data = [line for line in parsed_lines if len(line) == most_common_cols]
            
            # Special case: if we have one line with even number of cells, try 2xN layout
            if len(table_data) == 1 and len(table_data[0]) >= 4 and len(table_data[0]) % 2 == 0:
                cells = table_data[0]
                mid = len(cells) // 2
                table_data = [
                    cells[:mid],
                    cells[mid:]
                ]
    
    # Strategy 3: Single line with alternating pattern (headers + data)
    if not table_data and len(lines) == 1:
        # Try to detect header-data pattern like "Header1 Data1 Data2 Header2 Data3 Data4"
        words = re.findall(r'\S+', text)
        if len(words) >= 4:  # Need at least 4 values for a 2x2 table
            # For simple cases like "1 3 2 4", assume 2x2 table
            if len(words) == 4:
                table_data = [
                    [words[0], words[1]],
                    [words[2], words[3]]
                ]
            elif len(words) >= 6:  # Need at least 2 headers + 4 data points for a meaningful table
                # Look for pattern where some words might be headers
                # This is heuristic - assume first half could be headers, second half data
                mid_point = len(words) // 2
                headers = words[:mid_point]
                data = words[mid_point:]
                
                # Try to create a square-ish table
                cols = int(len(data) ** 0.5)  # Square root for column count
                if cols > 1 and len(data) % cols == 0:
                    rows = len(data) // cols
                    table_data = []
                    for i in range(rows):
                        row = data[i*cols:(i+1)*cols]
                        table_data.append(row)
                    
                    # Add headers as first row if they match column count
                    if len(headers) == cols:
                        table_data.insert(0, headers)
    
    # Generate HTML if we have table data
    if table_data and len(table_data) > 1:  # Need at least header + 1 data row
        html_parts = ['<table><tbody>']
        
        for row in table_data:
            html_parts.append('<tr>')
            for cell in row:
                # Escape HTML entities
                cell = cell.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html_parts.append(f'<td>{cell}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</tbody></table>')
        return ''.join(html_parts)
    
    return ""

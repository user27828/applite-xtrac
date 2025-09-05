"""
Core conversion utilities for the /convert endpoints.

This module contains the main conversion logic, service client management,
and utility functions that were moved from router.py to keep the router clean.
"""

import logging
import httpx
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO

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
    get_primary_conversion,
    ConversionService,
    get_supported_conversions,
    get_service_urls
)
from .url_helpers import (
    handle_url_conversion_request,
    cleanup_conversion_temp_files,
    get_url_conversion_info,
    validate_url_conversion_request,
    get_supported_input_formats
)
from .url_fetcher import fetch_url_content

# Set up logging
logger = logging.getLogger(__name__)

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

# Pandoc format mappings for extensions to pandoc format names
PANDOC_FORMAT_MAP = {
    # Input formats
    "md": "markdown",
    "tex": "latex",
    "txt": "plain",
    "html": "html",
    "docx": "docx",
    "odt": "odt",
    "rtf": "rtf",
    "epub": "epub",
    "json": "json",
    "biblatex": "biblatex",
    "bibtex": "bibtex",
    "commonmark": "commonmark",
    "gfm": "gfm",
    "org": "org",
    "rst": "rst",
    "textile": "textile",
    "vimwiki": "vimwiki",
    "mediawiki": "mediawiki",
    "dokuwiki": "dokuwiki",
    "tikiwiki": "tikiwiki",
    "twiki": "twiki",
    "creole": "creole",
    "jira": "jira",
    "muse": "muse",
    "t2t": "t2t",
    "ipynb": "ipynb",
    "csv": "csv",
    "tsv": "tsv",
    "docbook": "docbook",
    "jats": "jats",
    "man": "man",
    "fb2": "fb2",
    "opml": "opml",
    "ris": "ris",
    "endnotexml": "endnotexml",
    "csljson": "csljson",
    "native": "native",
    # Output formats
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "markdown": "markdown",
    "latex": "latex",
    "plain": "plain",
    "asciidoc": "asciidoc",
    "beamer": "beamer",
    "context": "context",
    "docbook4": "docbook4",
    "docbook5": "docbook5",
    "dzslides": "dzslides",
    "epub2": "epub2",
    "epub3": "epub3",
    "haddock": "haddock",
    "icml": "icml",
    "jats_archiving": "jats_archiving",
    "jats_articleauthoring": "jats_articleauthoring",
    "jats_publishing": "jats_publishing",
    "markua": "markua",
    "ms": "ms",
    "opendocument": "opendocument",
    "pptx": "pptx",
    "revealjs": "revealjs",
    "s5": "s5",
    "slideous": "slideous",
    "slidy": "slidy",
    "tei": "tei",
    "texinfo": "texinfo",
    "xwiki": "xwiki",
    "zimwiki": "zimwiki",
    "typst": "typst",
    "chunkedhtml": "chunkedhtml",
    "commonmark_x": "commonmark_x",
    "markdown_github": "markdown_github",
    "markdown_mmd": "markdown_mmd",
    "markdown_phpextra": "markdown_phpextra",
    "markdown_strict": "markdown_strict",
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

            # Map input format to pandoc format name and add as extra arg
            pandoc_input_format = PANDOC_FORMAT_MAP.get(input_format, input_format)
            if pandoc_input_format != "markdown":  # Default is markdown
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
                try:
                    url_data = await fetch_url_content(url)
                    content = url_data['content']
                    
                    # Ensure content is properly decoded as UTF-8 text
                    if isinstance(content, bytes):
                        content = content.decode('utf-8', errors='replace')
                    
                    # Generate output filename from URL
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

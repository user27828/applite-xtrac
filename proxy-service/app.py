from fastapi import FastAPI, Request, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from contextlib import asynccontextmanager
import json
from io import BytesIO
import logging
import asyncio
from urllib.parse import urlparse
import re
import os
from datetime import datetime
from typing import Optional, List

# Import unstructured libraries for JSON to markdown/text conversion
try:
    from unstructured.partition.auto import partition
    from unstructured.staging.base import elements_to_md
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

# Import the conversion router
from convert.router import router as convert_router

# Import service URL configuration
from convert.utils.conversion_lookup import get_service_urls

# Import centralized error handling
from convert.utils.error_handling import create_error_response, ErrorCode, handle_service_error

# Import centralized HTTP client factory
from convert.utils.http_client import (
    get_http_client_factory,
    ServiceType,
    lifespan_http_clients
)

# Import centralized logging configuration
from convert.utils.logging_config import get_logger


# Set up logging
logger = get_logger()

# Hop-by-hop headers that shouldn't be forwarded
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


async def check_unstructured_io_health(client: httpx.AsyncClient, service_url: str) -> tuple[bool, int]:
    """Centralized health check for unstructured-io service.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Try the main processing endpoint which should always be available
        response = await client.get(f"{service_url}/general/v0/general")
    except httpx.RequestError:
        # If main endpoint fails, try root as fallback
        try:
            response = await client.get(f"{service_url}/")
        except httpx.RequestError:
            # Service is unreachable
            return False, 0
    
    # For unstructured-io, accept specific status codes as healthy
    # 405=method not allowed (expected for GET on POST endpoint)
    # 404=not found (endpoint exists but method not allowed)
    # 422=unprocessable entity (service is up but request invalid)
    # 200=ok (if somehow it works)
    if response.status_code in [200, 404, 405, 422]:
        return True, response.status_code
    else:
        return False, response.status_code


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with centralized HTTP client setup."""
    # Get the HTTP client factory
    factory = get_http_client_factory()

    # Create service-specific clients using the centralized factory
    app.state.client = factory.create_client(ServiceType.UNSTRUCTURED_IO)
    app.state.libreoffice_client = factory.create_client(ServiceType.LIBREOFFICE)
    app.state.gotenberg_client = factory.create_client(ServiceType.GOTENBERG)

    # Use the centralized lifespan context manager for proper cleanup
    async with lifespan_http_clients():
        yield


app = FastAPI(lifespan=lifespan)

# Include the conversion router
app.include_router(convert_router)

# Serve favicon.ico
from fastapi.responses import FileResponse
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mount static files directory
static_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/favicon.ico")
@app.get("/favicon.ico/", response_class=FileResponse)
async def favicon():
    """Serve favicon.ico file."""
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/x-icon")
    else:
        # Return 404 if favicon doesn't exist
        raise HTTPException(status_code=404, detail="Favicon not found")

# Service URLs - with fallback mechanism for different environments
SERVICES = get_service_urls()

@app.get("/ping")
async def general_ping():
    return {"success": True, "data": "PONG!"}

@app.get("/ping-all")
async def ping_all():
    """Check health of all services"""
    results = {}
    services = ["unstructured-io", "libreoffice", "pyconvert", "gotenberg"]
    
    client: httpx.AsyncClient = app.state.client
    for service in services:
        try:
            service_url = SERVICES[service]

            # Select appropriate client for each service
            if service == "libreoffice":
                service_client = app.state.libreoffice_client
            elif service == "gotenberg":
                service_client = app.state.gotenberg_client
            else:
                service_client = client

            if service == "unstructured-io":
                # Use centralized health check function
                is_healthy, status_code = await check_unstructured_io_health(service_client, service_url)
                results[service] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "response_code": status_code
                }
                continue
            elif service == "libreoffice":
                # Attempt GET to root; 404 is expected and indicates the service is running
                response = await service_client.get(f"{service_url}/")
                # For libreoffice, 404 is actually healthy
                if response.status_code == 404:
                    results[service] = {"status": "healthy", "response_code": 404}
                    continue
            elif service == "pyconvert":
                response = await service_client.get(f"{service_url}/ping")
            elif service == "gotenberg":
                # Gotenberg should respond with 200 OK to a GET request to /
                response = await service_client.get(f"{service_url}/")

            results[service] = {
                "status": "healthy" if response.status_code < 400 else "unhealthy",
                "response_code": response.status_code
            }

        except httpx.RequestError as e:
            results[service] = {"status": "unreachable", "error": str(e)}
    
    # Determine overall status
    all_healthy = all(result["status"] == "healthy" for result in results.values())
    
    return {
        "success": all_healthy,
        "data": "ALL_SERVICES_HEALTHY" if all_healthy else "SOME_SERVICES_UNHEALTHY",
        "services": results
    }

@app.get("/docs")
async def docs():
    """Proxy the upstream docs and inject dark mode CSS into HTML responses."""
    # Choose which service docs to show — proxy the proxy's own docs if present or unstructured-io docs
    # Here we proxy the unstructured-io docs page as a representative API docs page
    upstream = SERVICES.get("unstructured-io")
    client: httpx.AsyncClient = app.state.client
    try:
        resp = await client.get(f"{upstream}/docs")

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            content = resp.text
            # Inject dark CSS into head
            dark_css = """
            <style>body { background-color: #1a1a1a !important; color: #ffffff !important; }</style>
            """
            if "</head>" in content:
                content = content.replace("</head>", f"{dark_css}</head>")
            return Response(content=content, status_code=resp.status_code, headers={"content-type": "text/html"})

        # For non-HTML responses, stream back to client and ensure response is closed
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}

        async def _stream_and_close(r):
            try:
                async for chunk in r.aiter_bytes():
                    yield chunk
            finally:
                await r.aclose()

        return StreamingResponse(_stream_and_close(resp), status_code=resp.status_code, headers=headers)

    except httpx.RequestError as e:
        return JSONResponse(status_code=502, content={"error": f"Docs proxy error: {str(e)}"})

@app.api_route("/{service}/ping", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def service_ping(service: str, request: Request):
    if service not in SERVICES:
        return JSONResponse(status_code=404, content={"error": "Service not found"})
    
    # Use the same logic as ping-all: ping the internal service directly
    service_url = SERVICES[service]
    
    try:
        # Select appropriate client for the service (same as ping-all)
        if service == "libreoffice":
            ping_client = app.state.libreoffice_client
        elif service == "gotenberg":
            ping_client = app.state.gotenberg_client
        else:
            ping_client = request.app.state.client
        
        if service == "unstructured-io":
            # Use centralized health check function
            is_healthy, status_code = await check_unstructured_io_health(ping_client, service_url)
            if is_healthy:
                return {"success": True, "data": "PONG!", "service": service}
            else:
                return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy (status: {status_code})"})
        elif service == "libreoffice":
            # Attempt GET to root; 404 is expected and indicates the service is running
            response = await ping_client.get(f"{service_url}/")
            # For libreoffice, 404 is actually healthy
            if response.status_code == 404:
                return {"success": True, "data": "PONG!", "service": service}
            else:
                # For any other status code, treat as unhealthy
                return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy (status: {response.status_code})"})
        elif service == "pyconvert":
            response = await ping_client.get(f"http://pyconvert:3000/ping")
        elif service == "gotenberg":
            # Gotenberg should respond with 200 OK to a GET request to /
            response = await ping_client.get(f"{service_url}/")
        
        # Check response status (same logic as ping-all)
        if response.status_code < 400 or (service == "unstructured-io" and response.status_code == 405):
            return {"success": True, "data": "PONG!", "service": service}
        else:
            return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy (status: {response.status_code})"})
    
    except httpx.RequestError as e:
        return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unreachable"})

@app.post("/unstructured-io-md")
async def unstructured_to_markdown(request: Request, file: UploadFile = File(...)):
    """Convert document to markdown using Unstructured-IO service and local JSON parsing."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Use centralized unstructured conversion function
        from convert.utils.unstructured_utils import convert_file_with_unstructured_io
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]
        
        markdown_content = await convert_file_with_unstructured_io(
            client=client,
            service_url=service_url,
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            output_format="md",
            fix_tables=True
        )

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.md"

        return StreamingResponse(
            BytesIO(markdown_content.encode('utf-8')),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        logger.exception("Error in unstructured_to_markdown")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})

@app.post("/unstructured-io-txt")
async def unstructured_to_text(request: Request, file: UploadFile = File(...)):
    """Convert document to plain text using Unstructured-IO service and local JSON parsing."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Use centralized unstructured conversion function
        from convert.utils.unstructured_utils import convert_file_with_unstructured_io
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]
        
        text_content = await convert_file_with_unstructured_io(
            client=client,
            service_url=service_url,
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            output_format="txt",
            fix_tables=False
        )

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.txt"

        return StreamingResponse(
            BytesIO(text_content.encode('utf-8')),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        logger.exception("Error in unstructured_to_text")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})


@app.post("/unstructured-io-html")
async def unstructured_to_html(request: Request, file: UploadFile = File(...)):
    """Convert document to HTML using Unstructured-IO service and local JSON parsing."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Use centralized unstructured conversion function
        from convert.utils.unstructured_utils import convert_file_with_unstructured_io
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]
        
        html_content = await convert_file_with_unstructured_io(
            client=client,
            service_url=service_url,
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            output_format="html",
            fix_tables=True
        )

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.html"

        return StreamingResponse(
            BytesIO(html_content.encode('utf-8')),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        logger.exception("Error in unstructured_to_html")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})


@app.post("/libreoffice-md")
async def libreoffice_to_markdown(request: Request, file: UploadFile = File(...)):
    """Convert document to PDF using LibreOffice, then to markdown using Unstructured-IO."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Step 1: Convert document to PDF using LibreOffice
        libreoffice_client = request.app.state.libreoffice_client
        service_url = SERVICES["libreoffice"]

        # Prepare LibreOffice request
        files = {"file": (file.filename, BytesIO(file_content), file.content_type or "application/octet-stream")}
        data = {"convert-to": "pdf"}

        libreoffice_response = await libreoffice_client.post(
            f"{service_url}/request",
            files=files,
            data=data
        )

        if libreoffice_response.status_code != 200:
            return JSONResponse(status_code=libreoffice_response.status_code,
                              content={"error": f"LibreOffice conversion failed: {libreoffice_response.text}"})

        # Get the PDF content from LibreOffice response
        pdf_content = libreoffice_response.content

        # Step 2: Convert PDF to markdown using centralized unstructured function
        from convert.utils.unstructured_utils import convert_file_with_unstructured_io
        client = request.app.state.client
        unstructured_url = SERVICES["unstructured-io"]
        
        markdown_content = await convert_file_with_unstructured_io(
            client=client,
            service_url=unstructured_url,
            file_content=pdf_content,
            filename="converted.pdf",
            content_type="application/pdf",
            output_format="md",
            fix_tables=True
        )

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.md"

        return StreamingResponse(
            BytesIO(markdown_content.encode('utf-8')),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        logger.exception("Error in libreoffice_to_markdown")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})

@app.post("/weasyprint/html-pdf")
async def weasyprint_html_to_pdf(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """
    Convert HTML to PDF using WeasyPrint with full parameter control.

    This endpoint provides direct access to WeasyPrint's capabilities without fallbacks.
    Accepts either a file upload or URL input, plus any WeasyPrint write_pdf() parameters.

    The endpoint automatically handles data transformations:
    - Uploaded CSS files are saved to temporary files
    - Stylesheet URLs are validated and passed through directly
    - CSS strings are passed through as-is
    - Page configuration CSS is automatically added if no stylesheets provided

    WeasyPrint Parameters (all write_pdf() parameters are supported):
    - stylesheets: List of CSS objects, URLs, file paths, CSS strings, or UploadFile objects
    - font_config: Font configuration object (auto-created if not provided)
    - zoom: Zoom factor for scaling content
    - presentational_hints: Enable CSS presentational hints
    - optimize_images: Optimize images for smaller PDF size
    - jpeg_quality: JPEG compression quality (1-100)
    - image_quality: General image quality (1-100)
    - disable_smart_shrinking: Disable smart shrinking
    - enable_hinting: Enable font hinting
    - user_agent: User agent for URL fetching (extracted from kwargs)
    - page_size, orientation, margin_*: Auto-converted to @page CSS if no stylesheets
    - Any other write_pdf() parameter...

    Examples:
    - stylesheets=["https://example.com/style.css", ".body { color: red; }"]
    - stylesheets=[uploaded_file_object]
    - zoom=1.5, presentational_hints=True
    """
    # Import WeasyPrint classes
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
        WEASYPRINT_AVAILABLE = True
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"error": "WeasyPrint library not available. Please install with: pip install weasyprint"}
        )

    # Validate input
    if not file and not url:
        return JSONResponse(
            status_code=400,
            content={"error": "Either 'file' or 'url' parameter must be provided"}
        )

    if file and url:
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot provide both 'file' and 'url' parameters"}
        )

    try:
        # Import httpx at the top to avoid UnboundLocalError
        import httpx
        
        # Extract all form parameters
        form_data = await request.form()
        weasyprint_params = {}
        
        # Convert form data to appropriate types
        for key, value in form_data.items():
            if key in ['file', 'url']:  # Skip file inputs
                continue
                
            # Handle different parameter types
            if isinstance(value, str):
                # Try to parse as boolean
                if value.lower() in ('true', 'false'):
                    weasyprint_params[key] = value.lower() == 'true'
                # Try to parse as number
                elif value.replace('.', '').isdigit():
                    weasyprint_params[key] = float(value) if '.' in value else int(value)
                else:
                    weasyprint_params[key] = value
            else:
                weasyprint_params[key] = value

        html_content = None
        base_url = None

        if file:
            # Read uploaded file
            file_content = await file.read()
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}
            
            # Extract user_agent from params if provided
            user_agent = weasyprint_params.pop('user_agent', None)
            if user_agent:
                headers["User-Agent"] = user_agent

            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text
                base_url = url

            # Generate base name from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "webpage"

        # Handle data transformations for WeasyPrint parameters
        weasyprint_kwargs = {}
        
        # Process stylesheets parameter if provided
        if 'stylesheets' in weasyprint_params:
            stylesheets = weasyprint_params.pop('stylesheets')
            processed_stylesheets = []
            
            # Handle different stylesheet types
            if isinstance(stylesheets, (list, tuple)):
                for stylesheet in stylesheets:
                    if hasattr(stylesheet, 'filename'):  # UploadFile
                        # Handle uploaded CSS file
                        if not stylesheet.filename.lower().endswith('.css'):
                            return JSONResponse(
                                status_code=400,
                                content={"error": f"Invalid stylesheet file: {stylesheet.filename}. Only .css files are allowed."}
                            )
                        
                        from convert.utils.temp_file_manager import get_temp_manager
                        temp_manager = get_temp_manager(service="weasyprint")
                        
                        file_content = await stylesheet.read()
                        temp_file = temp_manager.create_temp_file(
                            content=file_content,
                            filename=stylesheet.filename,
                            extension=".css",
                            prefix="stylesheet"
                        )
                        processed_stylesheets.append(temp_file.path)
                        
                    elif isinstance(stylesheet, str):
                        if stylesheet.startswith(('http://', 'https://')):
                            # URL - validate and pass through
                            processed_stylesheets.append(stylesheet)
                        else:
                            # CSS string - wrap in CSS object
                            processed_stylesheets.append(CSS(string=stylesheet))
                    else:
                        # Assume it's already a CSS object or file path
                        processed_stylesheets.append(stylesheet)
            else:
                # Single stylesheet - handle as list
                if hasattr(stylesheets, 'filename'):  # UploadFile
                    # Handle uploaded CSS file
                    if not stylesheets.filename.lower().endswith('.css'):
                        return JSONResponse(
                            status_code=400,
                            content={"error": f"Invalid stylesheet file: {stylesheets.filename}. Only .css files are allowed."}
                        )
                    
                    from convert.utils.temp_file_manager import get_temp_manager
                    temp_manager = get_temp_manager(service="weasyprint")
                    
                    file_content = await stylesheets.read()
                    temp_file = temp_manager.create_temp_file(
                        content=file_content,
                        filename=stylesheets.filename,
                        extension=".css",
                        prefix="stylesheet"
                    )
                    processed_stylesheets = [temp_file.path]
                    
                elif isinstance(stylesheets, str):
                    if stylesheets.startswith(('http://', 'https://')):
                        # URL - validate and pass through
                        processed_stylesheets = [stylesheets]
                    else:
                        # CSS string - wrap in CSS object
                        processed_stylesheets = [CSS(string=stylesheets)]
                else:
                    # Assume it's already a CSS object or file path
                    processed_stylesheets = [stylesheets]
            
            weasyprint_kwargs['stylesheets'] = processed_stylesheets

        # Add default page CSS if no stylesheets provided
        if 'stylesheets' not in weasyprint_kwargs:
            # Extract page configuration from params
            page_size = weasyprint_params.pop('page_size', 'A4')
            orientation = weasyprint_params.pop('orientation', 'portrait')
            margin_top = weasyprint_params.pop('margin_top', '1in')
            margin_right = weasyprint_params.pop('margin_right', '1in')
            margin_bottom = weasyprint_params.pop('margin_bottom', '1in')
            margin_left = weasyprint_params.pop('margin_left', '1in')
            
            css_content = f"""
            @page {{
                size: {page_size} {orientation};
                margin-top: {margin_top};
                margin-right: {margin_right};
                margin-bottom: {margin_bottom};
                margin-left: {margin_left};
            }}
            """
            weasyprint_kwargs['stylesheets'] = [css_content]

        # Add default font configuration if not provided
        if 'font_config' not in weasyprint_params:
            weasyprint_kwargs['font_config'] = FontConfiguration()

        # Pass through all remaining params to WeasyPrint
        weasyprint_kwargs.update(weasyprint_params)

        # Create HTML document
        html_doc = HTML(string=html_content, base_url=base_url)

        # Generate PDF with all processed parameters
        pdf_bytes = html_doc.write_pdf(**weasyprint_kwargs)

        # Generate output filename
        output_filename = f"{base_name}.pdf"

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "WEASYPRINT_DIRECT"
            }
        )

    except httpx.RequestError as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to fetch URL: {str(e)}"}
        )
    except Exception as e:
        logger.exception("Error in weasyprint_html_to_pdf")
        return JSONResponse(
            status_code=500,
            content={"error": f"WeasyPrint conversion failed: {str(e)}"}
        )

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(service: str, path: str, request: Request):
    """
    Generic proxy endpoint that forwards requests to backend services.

    This endpoint acts as a reverse proxy, routing requests to the appropriate backend service
    (unstructured-io, libreoffice, pyconvert, gotenberg) based on the {service} path parameter.

    Features:
    - Service validation and URL construction
    - Request body/header forwarding with hop-by-hop header filtering
    - Special handling for docs requests (adds dark mode parameter)
    - Form parameter extraction for POST/PUT/PATCH requests
    - Service-specific HTTP client selection (different timeouts/clients per service)
    - Retry logic with exponential backoff for transient failures
    - Comprehensive error handling with different responses for file downloads vs API calls
    - Content-type validation for conversion endpoints
    - Dark mode CSS injection for docs HTML responses
    - Streaming responses to prevent memory issues with large files

    Path: /{service}/{path:path}
    Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD

    Args:
        service: Backend service name (unstructured-io, libreoffice, pyconvert, gotenberg)
        path: Path to forward to the backend service
        request: FastAPI request object

    Returns:
        StreamingResponse or JSONResponse depending on the backend response
    """
    logger.info(f"Proxy request: service={service}, path={path}")
    if service not in SERVICES:
        return JSONResponse(status_code=404, content={"error": "Service not found"})

    service_url = SERVICES[service]
    target_url = f"{service_url}/{path}"

    # Get request data
    body = await request.body()
    headers = dict(request.headers)
    # Remove host header
    headers.pop("host", None)

    # Handle docs requests with dark mode
    query_params = dict(request.query_params)
    if path == "docs":
        query_params["dark"] = "true"

    # Extract form data parameters for POST/PUT/PATCH requests
    form_params = {}
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Check if this is multipart form data
            content_type = headers.get("content-type", "").lower()
            if "multipart/form-data" in content_type:
                form_data = await request.form()
                for field_name, field_value in form_data.items():
                    if field_name not in ['file', 'files']:  # Skip file fields
                        form_params[field_name] = field_value

                # If we have form data, we need to rebuild the body without the parameter fields
                # For now, we'll pass parameters as query params to maintain compatibility
                query_params.update(form_params)
        except Exception as e:
            logger.warning(f"Failed to extract form parameters in proxy: {e}")

    client: httpx.AsyncClient = app.state.client
    # Use longer timeout client for LibreOffice conversions
    if service == "libreoffice":
        client = app.state.libreoffice_client
    # Use Gotenberg client for Gotenberg requests
    elif service == "gotenberg":
        client = app.state.gotenberg_client

    try:
        # Retry logic for transient failures
        max_retries = 2
        retry_delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                # Use streaming to avoid buffering large responses in memory
                req = client.build_request(method=request.method, url=target_url, headers=headers, content=body, params=query_params)
                resp = await client.send(req, stream=True)

                # If we get here, the request succeeded (even if the service returned an error)
                break

            except httpx.RequestError as e:
                if attempt < max_retries:
                    logger.warning(f"Request attempt {attempt + 1} failed for {service}/{path}: {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # All retries exhausted
                    logger.error(f"All retry attempts failed for {service}/{path}: {e}")
                    return create_error_response(
                        status_code=502,
                        error_type="Service unavailable after retries",
                        service=service,
                        details=f"Failed after {max_retries + 1} attempts: {str(e)}",
                        retry_attempts=max_retries + 1
                    )

        # CRITICAL: Check if the response indicates an error before streaming
        if resp.status_code >= 400:
            # Read the error response body
            error_content = await resp.aread()
            error_text = error_content.decode(resp.encoding or "utf-8", errors="replace")
            await resp.aclose()

            # Log the error for debugging
            logger.error(f"Service {service} returned error {resp.status_code}: {error_text[:500]}...")

            # For file download endpoints, return empty body to prevent error content from being saved as files
            # Detect file download requests by checking for conversion-related paths
            is_file_download = (
                path in ["convert", "request"] or
                "convert" in path or
                any(keyword in path for keyword in ["pdf", "docx", "html", "txt", "md", "tex"])
            )

            logger.info(f"Error handling: service={service}, path={path}, is_file_download={is_file_download}")

            if is_file_download:
                # Return empty body with error status - prevents clients from saving error content as files
                logger.info(f"Returning empty body for file download error on {service}/{path}")
                # Sanitize error text for headers (remove non-ASCII characters)
                safe_error_text = error_text[:200].encode('ascii', 'ignore').decode('ascii')
                return Response(
                    content="",
                    status_code=resp.status_code,
                    headers={"X-Error-Message": f"Service {service} error", "X-Error-Details": safe_error_text}
                )
            else:
                # For API endpoints, return detailed JSON error
                return create_error_response(
                    status_code=resp.status_code,
                    error_type=f"Service {service} error",
                    service=service,
                    details=error_text
                )

        # Additional validation: Check content-type for document conversion endpoints
        content_type = resp.headers.get("content-type", "")
        expected_content_types = {
            "pyconvert": ["application/pdf", "application/vnd.openxmlformats", "text/html", "text/plain", "text/markdown", "application/x-tex"],
            "libreoffice": ["application/pdf", "application/vnd.openxmlformats", "application/vnd.openxmlformats-officedocument", "text/plain", "application/octet-stream"],
            "gotenberg": ["application/pdf"],
            "unstructured-io": ["application/json", "text/plain", "text/markdown"]
        }
        
        # For conversion-related paths, validate content type
        if path in ["convert", "request"] or "convert" in path:
            service_expected_types = expected_content_types.get(service, [])
            if service_expected_types and not any(expected in content_type for expected in service_expected_types):
                # This might be an error response disguised as a document
                error_content = await resp.aread()
                error_text = error_content.decode(resp.encoding or "utf-8", errors="replace")
                await resp.aclose()
                
                logger.warning(f"Unexpected content-type '{content_type}' for {service}/{path}, possible error: {error_text[:200]}...")
                
                # For file download endpoints, return empty body to prevent error content from being saved as files
                is_file_download = (
                    path in ["convert", "request"] or 
                    "convert" in path or
                    any(keyword in path for keyword in ["pdf", "docx", "html", "txt", "md", "tex"])
                )
                
                if is_file_download:
                    return Response(
                        content="",
                        status_code=502,
                        headers={"X-Error-Message": "Invalid response format", "X-Error-Details": f"Expected {service_expected_types}, got {content_type}"}
                    )
                else:
                    return create_error_response(
                        status_code=502,
                        error_type="Invalid response format",
                        service=service,
                        details=f"Expected content types: {service_expected_types}, got: {content_type}. Response: {error_text[:500]}",
                        expected_content_types=service_expected_types,
                        received_content_type=content_type
                    )

        content_type = resp.headers.get("content-type", "")

        # If docs HTML, collect and inject CSS
        if path == "docs" and "text/html" in content_type:
            text = await resp.aread()
            content = text.decode(resp.encoding or "utf-8", errors="replace")
            if "swagger-ui" in content or "redoc" in content:
                dark_css = """
                <style>body { background-color: #1a1a1a !important; color: #ffffff !important; }</style>
                """
                if "</head>" in content:
                    content = content.replace("</head>", f"{dark_css}</head>")
            await resp.aclose()
            return Response(content=content, status_code=resp.status_code, headers={"content-type": "text/html"})

        # Stream other responses directly and ensure response is closed afterwards
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}

        async def _stream_and_close(r):
            try:
                async for chunk in r.aiter_bytes():
                    yield chunk
            finally:
                await r.aclose()

        return StreamingResponse(_stream_and_close(resp), status_code=resp.status_code, headers=headers)

    except httpx.RequestError as e:
        return JSONResponse(status_code=502, content={"error": f"Proxy error: {str(e)}"})
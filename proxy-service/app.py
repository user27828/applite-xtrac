from fastapi import FastAPI, Request, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from contextlib import asynccontextmanager
from io import BytesIO
import os
from typing import Optional

from convert.utils.unstructured_utils import is_unstructured_available

# Import the conversion router
from convert.router import router as convert_router

# Import service URL configuration
from convert.utils.conversion_lookup import get_service_urls

# Import centralized error handling
from convert.utils.error_handling import sanitize_filename

# Import centralized HTTP client factory
from convert.utils.http_client import (
    get_http_client_factory,
    ServiceType,
    lifespan_http_clients
)

# Import centralized logging configuration
from convert.utils.logging_config import get_logger
from convert.utils.resource_limits import (
    ContentLengthLimitMiddleware,
    MAX_ERROR_BYTES,
    bounded_request_stream,
    bounded_response_stream,
    read_response_bounded,
    validate_request_content_length,
    validate_upload_size,
)


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
    app.state.pyconvert_client = factory.create_client(ServiceType.PANDOC)

    # Use the centralized lifespan context manager for proper cleanup
    async with lifespan_http_clients():
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(ContentLengthLimitMiddleware)

# Include the conversion router
app.include_router(convert_router)

# Serve favicon.ico
from fastapi.responses import FileResponse
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mount static files directory (dedicated subdirectory, not the app root)
static_dir = Path(__file__).parent / "static"
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

async def ping_pyconvert_service(service_name: str) -> JSONResponse:
    """
    Utility function to ping individual pyconvert services.
    
    Args:
        service_name: Name of the service to ping (mammoth, weasyprint, html4docx, pandoc)
    
    Returns:
        JSONResponse with ping result
    """
    client: httpx.AsyncClient = app.state.client
    try:
        response = await client.get(f"{SERVICES['pyconvert']}/{service_name}/ping")
        if response.status_code == 200:
            return response.json()
        else:
            return JSONResponse(
                status_code=503, 
                content={
                    "success": False, 
                    "error": f"{service_name.title()} service unhealthy (status: {response.status_code})"
                }
            )
    except httpx.RequestError:
        return JSONResponse(
            status_code=503, 
            content={
                "success": False, 
                "error": f"{service_name.title()} service unreachable"
            }
        )

@app.get("/ping")
async def general_ping():
    return {"success": True, "data": "PONG!"}

@app.get("/mammoth/ping")
async def ping_mammoth():
    """Check Mammoth service health."""
    return await ping_pyconvert_service("mammoth")

@app.get("/weasyprint/ping")
async def ping_weasyprint():
    """Check WeasyPrint service health."""
    return await ping_pyconvert_service("weasyprint")

@app.get("/html4docx/ping")
async def ping_html4docx():
    """Check html4docx service health."""
    return await ping_pyconvert_service("html4docx")

@app.get("/beautifulsoup/ping")
async def ping_beautifulsoup():
    """Check BeautifulSoup service health."""
    return await ping_pyconvert_service("beautifulsoup")

@app.get("/pymupdf/ping")
async def ping_pymupdf():
    """Check PyMuPDF service health."""
    return await ping_pyconvert_service("pymupdf")

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
                # Check pyconvert service health and parse detailed health information
                response = await service_client.get(f"{service_url}/ping")
                pyconvert_healthy = response.status_code < 400
                
                # Parse the enhanced ping response that includes pandoc and weasyprint information
                if response.status_code == 200:
                    try:
                        ping_data = response.json()
                        # Extract pandoc, weasyprint, mammoth, html4docx, and pymupdf health from the ping response
                        pandoc_info = ping_data.get("pandoc", {"status": "unknown", "response_code": 0})
                        weasyprint_info = ping_data.get("weasyprint", {"status": "unknown", "response_code": 0})
                        mammoth_info = ping_data.get("mammoth", {"status": "unknown", "response_code": 0})
                        html4docx_info = ping_data.get("html4docx", {"status": "unknown", "response_code": 0})
                        pymupdf_info = ping_data.get("pymupdf", {"status": "unknown", "response_code": 0})
                        
                        results[service] = {
                            "status": "healthy" if pyconvert_healthy else "unhealthy",
                            "response_code": response.status_code,
                            "pandoc": pandoc_info,
                            "weasyprint": weasyprint_info,
                            "mammoth": mammoth_info,
                            "html4docx": html4docx_info,
                            "pymupdf": pymupdf_info
                        }
                    except (ValueError, KeyError):
                        # Fallback if JSON parsing fails
                        results[service] = {
                            "status": "healthy" if pyconvert_healthy else "unhealthy",
                            "response_code": response.status_code
                        }
                else:
                    # If ping fails, return basic health info
                    results[service] = {
                        "status": "healthy" if pyconvert_healthy else "unhealthy",
                        "response_code": response.status_code
                    }
            elif service == "gotenberg":
                # Gotenberg should respond with 200 OK to a GET request to /
                response = await service_client.get(f"{service_url}/")
                
                results[service] = {
                    "status": "healthy" if response.status_code < 400 else "unhealthy",
                    "response_code": response.status_code
                }
            else:
                # Default handling for any other services
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
            # Parse the enhanced ping response that includes pandoc information
            if response.status_code == 200:
                try:
                    ping_data = response.json()
                    # Return the enhanced response with pandoc information
                    return {
                        "success": True,
                        "data": "PONG!",
                        "service": service,
                        "pandoc": ping_data.get("pandoc", {"status": "unknown", "response_code": 0}),
                        "weasyprint": ping_data.get("weasyprint", {"status": "unknown", "response_code": 0}),
                        "mammoth": ping_data.get("mammoth", {"status": "unknown", "response_code": 0}),
                        "html4docx": ping_data.get("html4docx", {"status": "unknown", "response_code": 0}),
                        "pymupdf": ping_data.get("pymupdf", {"status": "unknown", "response_code": 0})
                    }
                except (ValueError, KeyError):
                    # Fallback if JSON parsing fails
                    return {"success": True, "data": "PONG!", "service": service}
            else:
                return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy (status: {response.status_code})"})
        elif service == "gotenberg":
            # Gotenberg should respond with 200 OK to a GET request to /
            response = await ping_client.get(f"{service_url}/")
        
        # Check response status (same logic as ping-all)
        if response.status_code < 400 or (service == "unstructured-io" and response.status_code == 405):
            return {"success": True, "data": "PONG!", "service": service}
        else:
            return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy (status: {response.status_code})"})
    
    except httpx.RequestError:
        return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unreachable"})

@app.post("/unstructured-io-md")
async def unstructured_to_markdown(request: Request, file: UploadFile = File(...)):
    """Convert document to markdown using Unstructured-IO service and local JSON parsing."""
    return await _unstructured_convert(request, file, output_format="md", media_type="text/markdown", fix_tables=True)

@app.post("/unstructured-io-txt")
async def unstructured_to_text(request: Request, file: UploadFile = File(...)):
    """Convert document to plain text using Unstructured-IO service and local JSON parsing."""
    return await _unstructured_convert(request, file, output_format="txt", media_type="text/plain", fix_tables=False)

@app.post("/unstructured-io-html")
async def unstructured_to_html(request: Request, file: UploadFile = File(...)):
    """Convert document to HTML using Unstructured-IO service and local JSON parsing."""
    return await _unstructured_convert(request, file, output_format="html", media_type="text/html", fix_tables=True)


async def _unstructured_convert(
    request: Request, file: UploadFile, *, output_format: str, media_type: str, fix_tables: bool
):
    """Shared implementation for the Unstructured-IO conversion endpoints."""
    if not is_unstructured_available():
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        validate_upload_size(file)
        await file.seek(0)

        from convert.utils.unstructured_utils import convert_file_with_unstructured_io
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]

        converted = await convert_file_with_unstructured_io(
            client=client,
            service_url=service_url,
            file_content=file.file,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            output_format=output_format,
            fix_tables=fix_tables,
        )

        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = sanitize_filename(f"{base_name}.{output_format}")

        return StreamingResponse(
            BytesIO(converted.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"},
        )

    except Exception as e:
        logger.exception(f"Error in unstructured_to_{output_format}")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})


@app.post("/libreoffice-md")
async def libreoffice_to_markdown(request: Request, file: UploadFile = File(...)):
    """Convert document to PDF using LibreOffice, then to markdown using Unstructured-IO."""
    if not is_unstructured_available():
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        validate_upload_size(file)
        await file.seek(0)

        # Step 1: Convert document to PDF using LibreOffice
        libreoffice_client = request.app.state.libreoffice_client
        service_url = SERVICES["libreoffice"]

        # Prepare LibreOffice request
        files = {"file": (file.filename, file.file, file.content_type or "application/octet-stream")}
        data = {"convert-to": "pdf"}

        libreoffice_request = libreoffice_client.build_request(
            "POST",
            f"{service_url}/request",
            files=files,
            data=data
        )
        libreoffice_response = await libreoffice_client.send(libreoffice_request, stream=True)

        if libreoffice_response.status_code != 200:
            error_content = await read_response_bounded(libreoffice_response, MAX_ERROR_BYTES)
            return JSONResponse(
                status_code=libreoffice_response.status_code,
                content={"error": f"LibreOffice conversion failed: {error_content.decode('utf-8', errors='replace')}"},
            )

        # Get the PDF content from LibreOffice response
        pdf_content = await read_response_bounded(libreoffice_response)

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
        output_filename = sanitize_filename(f"{base_name}.md")

        return StreamingResponse(
            BytesIO(markdown_content.encode('utf-8')),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        logger.exception("Error in libreoffice_to_markdown")
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})

# --- Generic pyconvert proxy helper ---

async def _proxy_to_pyconvert(request: Request, path: str, service_label: str):
    """
    Proxy a request to the pyconvert-service.

    This shared helper eliminates duplication across the WeasyPrint, Mammoth,
    html4docx, BeautifulSoup, and PyMuPDF proxy endpoints.

    Args:
        request: The incoming FastAPI request.
        path: The pyconvert sub-path (e.g. "weasyprint", "pymupdf/pdf-html").
        service_label: Human-readable name for error/log messages.
    """
    target_url = f"{SERVICES['pyconvert']}/{path}"
    validate_request_content_length(request)

    headers = dict(request.headers)
    headers.pop("host", None)

    query_params = dict(request.query_params)
    form_data = None

    try:
        content_type = headers.get("content-type", "").lower()
        if "multipart/form-data" in content_type:
            form_data = await request.form()
    except Exception as e:
        logger.warning(f"Failed to extract form parameters in {service_label} proxy: {e}")

    client: httpx.AsyncClient = app.state.pyconvert_client

    try:
        if form_data is not None:
            files = {}
            data = {}
            for field_name, field_value in form_data.items():
                if hasattr(field_value, 'filename'):
                    validate_upload_size(field_value)
                    await field_value.seek(0)
                    files[field_name] = (field_value.filename, field_value.file, field_value.content_type)
                else:
                    data[field_name] = field_value
            downstream_request = client.build_request(
                method=request.method,
                url=target_url,
                files=files,
                data=data,
                params=query_params,
            )
            resp = await client.send(downstream_request, stream=True)
        else:
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=bounded_request_stream(request),
                params=query_params,
            )
            resp = await client.send(req, stream=True)

        if resp.status_code >= 400:
            error_content = await read_response_bounded(resp, MAX_ERROR_BYTES)
            error_text = error_content.decode(resp.encoding or "utf-8", errors="replace")

            logger.error(f"{service_label} service returned error {resp.status_code}: {error_text[:500]}...")
            return JSONResponse(
                status_code=resp.status_code,
                content={"error": f"{service_label} conversion failed: {error_text}"}
            )

        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}

        return StreamingResponse(
            bounded_response_stream(resp),
            status_code=resp.status_code,
            headers=resp_headers,
        )

    except httpx.RequestError as e:
        return JSONResponse(status_code=502, content={"error": f"{service_label} service unavailable: {str(e)}"})
    except Exception as e:
        logger.exception(f"Error proxying to {service_label} service")
        return JSONResponse(status_code=500, content={"error": f"Proxy error: {str(e)}"})


# --- Pyconvert proxy endpoints ---

@app.post("/weasyprint/html-pdf")
async def weasyprint_html_to_pdf(request: Request, file: Optional[UploadFile] = File(None), url: Optional[str] = Form(None)):
    """Convert HTML to PDF using WeasyPrint via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "weasyprint", "WeasyPrint")


@app.post("/mammoth/docx-html")
async def mammoth_docx_to_html(
    request: Request,
    file: UploadFile = File(...),
    style_map: Optional[str] = Form(None),
    include_default_style_map: Optional[bool] = Form(True),
    include_embedded_style_map: Optional[bool] = Form(True),
    ignore_empty_paragraphs: Optional[bool] = Form(True),
    id_prefix: Optional[str] = Form(None),
):
    """Convert DOCX to HTML using Mammoth via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "mammoth", "Mammoth")


@app.post("/html4docx/html-docx")
async def html4docx_html_to_docx(request: Request, file: UploadFile = File(...), url: Optional[str] = Form(None)):
    """Convert HTML to DOCX using html4docx via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "html4docx", "html4docx")


@app.post("/beautifulsoup/html-html")
async def beautifulsoup_html_to_html(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    parser: Optional[str] = Form("html.parser"),
    prettify: Optional[bool] = Form(True),
    remove_scripts: Optional[bool] = Form(True),
    remove_styles: Optional[bool] = Form(False),
    remove_comments: Optional[bool] = Form(True),
    extract_title: Optional[bool] = Form(False),
    extract_text: Optional[bool] = Form(False),
):
    """Clean HTML using BeautifulSoup via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "beautifulsoup", "BeautifulSoup")


@app.post("/pymupdf/pdf-html")
async def pymupdf_pdf_to_html_proxy(request: Request, file: UploadFile = File(...)):
    """Convert PDF to HTML using PyMuPDF via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "pymupdf/pdf-html", "PyMuPDF")


@app.post("/pymupdf/pdf-txt")
async def pymupdf_pdf_to_txt_proxy(request: Request, file: UploadFile = File(...)):
    """Convert PDF to plain text using PyMuPDF via pyconvert-service."""
    return await _proxy_to_pyconvert(request, "pymupdf/pdf-txt", "PyMuPDF")


if __name__ == "__main__":
    import random
    import uvicorn

    max_requests = int(os.getenv("APPLITEXTRAC_MAX_REQUESTS", "2000"))
    max_requests_jitter = int(os.getenv("APPLITEXTRAC_MAX_REQUESTS_JITTER", "200"))
    if max_requests < 1 or max_requests_jitter < 0:
        raise RuntimeError("Request recycling limits must be positive (jitter may be zero)")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8369,
        limit_concurrency=int(os.getenv("APPLITEXTRAC_LIMIT_CONCURRENCY", "64")),
        limit_max_requests=max_requests + random.SystemRandom().randint(0, max_requests_jitter),
    )

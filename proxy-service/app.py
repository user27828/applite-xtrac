from fastapi import FastAPI, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from contextlib import asynccontextmanager
import json
from io import BytesIO

# Import unstructured libraries for JSON to markdown/text conversion
try:
    from unstructured.documents.elements.json import json_to_elements
    from unstructured.staging.markdown.markdown import elements_to_markdown
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

# Import the conversion router
from convert.router import router as convert_router


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create shared AsyncClients with different timeouts for different services
    app.state.client = httpx.AsyncClient(timeout=30.0)  # General client with 30s timeout
    app.state.libreoffice_client = httpx.AsyncClient(timeout=120.0)  # LibreOffice needs longer timeout
    app.state.gotenberg_client = httpx.AsyncClient(timeout=60.0, 
                                                     transport=httpx.AsyncHTTPTransport(retries=1))  # Gotenberg client
    try:
        yield
    finally:
        await app.state.client.aclose()
        await app.state.libreoffice_client.aclose()
        await app.state.gotenberg_client.aclose()


app = FastAPI(lifespan=lifespan)

# Include the conversion router
app.include_router(convert_router)

# Service URLs - using localhost since all services run on host network
SERVICES = {
    # Use service DNS names available on the compose network
    "unstructured-io": "http://unstructured-io:8000",
    "libreoffice": "http://libreoffice:2004",
    "pandoc": "http://pandoc:3000",
    "gotenberg": "http://gotenberg:3000"
}

@app.get("/ping")
async def general_ping():
    return {"success": True, "data": "PONG!"}

@app.get("/ping-all")
async def ping_all():
    """Check health of all services"""
    results = {}
    services = ["unstructured-io", "libreoffice", "pandoc", "gotenberg"]
    
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
                # Try the main processing endpoint which should always be available
                try:
                    response = await service_client.get(f"{service_url}/general/v0/general")
                except:
                    # If main endpoint fails, try root as fallback
                    response = await service_client.get(f"{service_url}/")
                # For unstructured-io, accept any response as healthy since 404/405/422 might be expected
                if response.status_code in [200, 404, 405, 422]:  # 405=method not allowed, still means service is up
                    results[service] = {"status": "healthy", "response_code": response.status_code}
                    continue
            elif service == "libreoffice":
                # Attempt GET to root; 404 is expected and indicates the service is running
                response = await service_client.get(f"{service_url}/")
                # For libreoffice, 404 is actually healthy
                if response.status_code == 404:
                    results[service] = {"status": "healthy", "response_code": 404}
                    continue
            elif service == "pandoc":
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
    
    service_url = SERVICES[service]
    
    try:
        # Select appropriate client for the service
        if service == "libreoffice":
            ping_client = app.state.libreoffice_client
        elif service == "gotenberg":
            ping_client = app.state.gotenberg_client
        else:
            ping_client = httpx.AsyncClient(timeout=5.0)
        
        if service == "unstructured-io":
            # Use POST request to general endpoint for health check
            response = await ping_client.post(f"{service_url}/general/v0/general", 
                                           json={"dummy": "data"})
        elif service == "libreoffice":
            # Use GET request to root endpoint for LibreOffice REST API health check
            response = await ping_client.get(f"{service_url}/")
        elif service == "pandoc":
            # Use our custom ping endpoint
            response = await ping_client.get(f"{service_url}/ping")
        elif service == "gotenberg":
            # Gotenberg should respond with 200 OK to a GET request to /
            # Use a fresh client for Gotenberg to avoid any context issues
            async with httpx.AsyncClient(timeout=10.0) as fresh_client:
                response = await fresh_client.get(f"{service_url}/")
        
        if response.status_code < 400:
            return {"success": True, "data": "PONG!", "service": service}
        else:
            return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unhealthy"})
    
    except httpx.RequestError as e:
        return JSONResponse(status_code=503, content={"success": False, "error": f"Service {service} unreachable"})
    finally:
        # Close the client if it was created locally (not from app.state)
        if 'ping_client' in locals() and ping_client not in [app.state.libreoffice_client, app.state.gotenberg_client]:
            await ping_client.aclose()

@app.post("/unstructured-io-md")
async def unstructured_to_markdown(request: Request, file: UploadFile = File(...)):
    """Convert document to markdown using Unstructured-IO and JSON parsing."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Call Unstructured-IO service to get JSON
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]

        files = {"files": (file.filename, BytesIO(file_content), file.content_type or "application/octet-stream")}
        data = {"output_format": "json"}

        response = await client.post(
            f"{service_url}/general/v0/general",
            files=files,
            data=data
        )

        if response.status_code != 200:
            return JSONResponse(status_code=response.status_code, content={"error": f"Unstructured-IO error: {response.text}"})

        # Parse JSON response into elements
        json_data = response.json()
        elements = json_to_elements(json.dumps(json_data))

        # Convert elements to markdown
        markdown_content = elements_to_markdown(elements)

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.md"

        return StreamingResponse(
            BytesIO(markdown_content.encode('utf-8')),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})

@app.post("/unstructured-io-txt")
async def unstructured_to_text(request: Request, file: UploadFile = File(...)):
    """Convert document to plain text using Unstructured-IO and JSON parsing."""
    if not UNSTRUCTURED_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "Unstructured library not available"})

    try:
        # Read the uploaded file
        file_content = await file.read()

        # Call Unstructured-IO service to get JSON
        client: httpx.AsyncClient = request.app.state.client
        service_url = SERVICES["unstructured-io"]

        files = {"files": (file.filename, BytesIO(file_content), file.content_type or "application/octet-stream")}
        data = {"output_format": "json"}

        response = await client.post(
            f"{service_url}/general/v0/general",
            files=files,
            data=data
        )

        if response.status_code != 200:
            return JSONResponse(status_code=response.status_code, content={"error": f"Unstructured-IO error: {response.text}"})

        # Parse JSON response into elements
        json_data = response.json()
        elements = json_to_elements(json.dumps(json_data))

        # Convert elements to plain text
        text_content = "\n\n".join(e.text for e in elements if hasattr(e, 'text') and e.text)

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.txt"

        return StreamingResponse(
            BytesIO(text_content.encode('utf-8')),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Conversion failed: {str(e)}"})

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(service: str, path: str, request: Request):
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
    
    client: httpx.AsyncClient = app.state.client
    # Use longer timeout client for LibreOffice conversions
    if service == "libreoffice":
        client = app.state.libreoffice_client
    # Use Gotenberg client for Gotenberg requests
    elif service == "gotenberg":
        client = app.state.gotenberg_client
    try:
        # Use streaming to avoid buffering large responses in memory
        req = client.build_request(method=request.method, url=target_url, headers=headers, content=body, params=query_params)
        resp = await client.send(req, stream=True)

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
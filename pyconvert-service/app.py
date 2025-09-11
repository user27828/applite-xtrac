from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import httpx
from contextlib import asynccontextmanager
import json
from io import BytesIO
import logging
import asyncio
from urllib.parse import urlparse
import re
import os
import subprocess
import shutil
from datetime import datetime
from typing import Optional, List

# Try to import python-magic for comprehensive MIME type detection
try:
    import magic
    USE_MAGIC = True
    print("python-magic loaded successfully")
except ImportError:
    USE_MAGIC = False
    print("python-magic not available, using fallback methods")

# Import unified MIME detector
from utils.mime_detector import get_mime_type as get_unified_mime_type

# Import centralized temp file manager
from utils.temp_file_manager import (
    get_temp_manager,
    TempFileManager,
    TempFileInfo,
    cleanup_temp_files
)

app = FastAPI()

@app.get("/ping")
async def ping():
    """Enhanced ping endpoint that includes pandoc and weasyprint health information."""
    # Get pandoc health
    pandoc_healthy, pandoc_status = await check_pandoc_health()
    
    # Get weasyprint health
    weasyprint_healthy, weasyprint_status = await check_weasyprint_health()
    
    return {
        "success": True,
        "data": "PONG!",
        "pandoc": {
            "status": "healthy" if pandoc_healthy else "unhealthy",
            "response_code": pandoc_status
        },
        "weasyprint": {
            "status": "healthy" if weasyprint_healthy else "unhealthy",
            "response_code": weasyprint_status
        }
    }

async def check_pandoc_health() -> tuple[bool, int]:
    """
    Check pandoc service health by testing the pandoc endpoint.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Test pandoc by making a simple request to check if it's responsive
        # We'll use a minimal test that doesn't require actual file processing
        # For now, we'll just check if the endpoint exists and responds
        # In a real scenario, you might want to test with a small sample file
        
        # Since pandoc requires file input, we'll just check if the endpoint is accessible
        # by attempting a request that will fail due to missing parameters but confirm the service is up
        import httpx
        async with httpx.AsyncClient() as client:
            # Try to access the pandoc endpoint - it should return 422 for missing required fields
            # but this confirms the service is running
            response = await client.post(
                "http://localhost:3000/pandoc",  # Use localhost since we're in the same container
                data={},  # Empty data to trigger validation error
                timeout=5.0
            )
            # 422 is expected (validation error), which means the service is healthy
            if response.status_code == 422:
                return True, response.status_code
            elif response.status_code < 500:
                return True, response.status_code
            else:
                return False, response.status_code
                
    except httpx.RequestError:
        return False, 0
    except Exception:
        return False, 0

async def check_weasyprint_health() -> tuple[bool, int]:
    """
    Check WeasyPrint service health by testing the weasyprint endpoint.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Test WeasyPrint by making a simple request to check if it's responsive
        # Since WeasyPrint requires either file or url input, we'll check if the endpoint is accessible
        # by attempting a request that will fail due to missing parameters but confirm the service is up
        import httpx
        async with httpx.AsyncClient() as client:
            # Try to access the weasyprint endpoint - it should return 400 for missing required fields
            # but this confirms the service is running
            response = await client.post(
                "http://localhost:3000/weasyprint",  # Use localhost since we're in the same container
                data={},  # Empty data to trigger validation error
                timeout=5.0
            )
            # 400 is expected (validation error for missing file/url), which means the service is healthy
            if response.status_code == 400:
                return True, response.status_code
            elif response.status_code < 500:
                return True, response.status_code
            else:
                return False, response.status_code
                
    except httpx.RequestError:
        return False, 0
    except Exception:
        return False, 0

def get_mime_type(file_path: str, output_format: str) -> str:
    """
    Get MIME type using unified detection methods with fallbacks.

    Uses the centralized MIME detector which handles:
    1. Content-based detection (python-magic)
    2. Extension-based detection (mimetypes)
    3. Custom mappings and overrides
    4. Consistent fallbacks
    """

    # Use unified MIME detector
    return get_unified_mime_type(filename=file_path, expected_format=output_format)

@app.post("/pandoc")
async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    output_format: str = Form(...),
    extra_args: str = Form("")
):
    # Validate output format
    allowed_formats = ["pdf", "docx", "html", "txt", "md", "tex"]
    if output_format not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported output format: {output_format}")

    # Create temp files using centralized manager
    manager = get_temp_manager()

    # Read file content
    file_content = await file.read()

    # Create input temp file
    input_temp = manager.create_temp_file(
        content=file_content,
        extension=os.path.splitext(file.filename)[1],
        prefix="pyconvert_input"
    )
    input_path = input_temp.path

    # Create output temp file path
    output_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
    output_temp = manager.create_temp_file(
        filename=output_filename,
        prefix="pyconvert_output"
    )
    output_path = output_temp.path

    try:
        # Special handling for LaTeX to PDF conversion
        if output_format == "pdf" and (input_path.endswith('.tex') or input_path.endswith('.latex')):
            # Use pdflatex directly for LaTeX to PDF conversion
            # Extract base name without extension for jobname
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(output_path)
            
            cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", output_dir, "-jobname", base_name, input_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # For LaTeX, return code 1 often just means warnings, not fatal errors
            # Check if PDF was actually created despite warnings
            latex_output_path = os.path.join(output_dir, base_name + ".pdf")
            
            if result.returncode != 0 and not os.path.exists(latex_output_path):
                # Only fail if PDF wasn't created
                error_msg = f"pdflatex failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f". stderr: {result.stderr}"
                if result.stdout:
                    error_msg += f". stdout: {result.stdout}"
                if not result.stderr and not result.stdout:
                    error_msg += ". No error output captured"
                raise HTTPException(status_code=500, detail=error_msg)
            elif result.returncode != 0 and os.path.exists(latex_output_path):
                # PDF was created despite warnings - log the warnings but continue
                print(f"pdflatex completed with warnings (return code {result.returncode}) but PDF was created successfully")
                if result.stdout:
                    print(f"pdflatex stdout: {result.stdout}")
                if result.stderr:
                    print(f"pdflatex stderr: {result.stderr}")
            
            # Check if output file exists
            if not os.path.exists(latex_output_path):
                raise HTTPException(status_code=500, detail=f"pdflatex completed but output PDF file was not found at {latex_output_path}")
            
            # Move the output to the expected location if different
            if latex_output_path != output_path:
                shutil.move(latex_output_path, output_path)
                    
            # Clean up auxiliary files created by pdflatex
            aux_extensions = ['.aux', '.log', '.out', '.fls', '.fdb_latexmk', '.synctex.gz']
            for ext in aux_extensions:
                aux_file = os.path.join(output_dir, base_name + ext)
                if os.path.exists(aux_file):
                    os.remove(aux_file)
        else:
            # Build pandoc command for other conversions
            cmd = ["pandoc", input_path, "-o", output_path]
            
            # Special handling for PDF output - need to specify PDF engine
            if output_format == "pdf":
                cmd = ["pandoc", input_path, "-o", output_path, "--pdf-engine=xelatex"]
            
            # Add extra args if provided
            if extra_args:
                cmd.extend(extra_args.split())

            # Run pandoc
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                error_msg = f"Pandoc failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f". stderr: {result.stderr}"
                if result.stdout:
                    error_msg += f". stdout: {result.stdout}"
                if not result.stderr and not result.stdout:
                    error_msg += ". No error output captured"
                print(f"Pandoc command failed: {error_msg}")
                print(f"Command was: {' '.join(cmd)}")
                raise HTTPException(status_code=500, detail=error_msg)

        # Get MIME type using comprehensive detection
        media_type = get_unified_mime_type(filename=output_path, expected_format=output_format)

        # Return the converted file
        # Note: Files will be automatically cleaned up by the temp file manager
        # when the manager goes out of scope or when explicitly cleaned up
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=f"{os.path.splitext(file.filename)[0]}.{output_format}"
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Conversion timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Ensure cleanup happens even if an exception occurs
        # The temp file manager will handle this automatically
        pass


@app.post("/weasyprint")
async def weasyprint_html_to_pdf(
    request: Request,
    file: UploadFile = None,
    url: str = Form(None)
):
    """
    Convert HTML to PDF using WeasyPrint.

    This endpoint provides direct access to WeasyPrint's write_pdf() method.
    Accepts either a file upload or URL input, plus any WeasyPrint write_pdf() parameters.

    All parameters are passed directly to HTML.write_pdf() except for:
    - 'file' and 'url' which are handled internally for input
    - 'user_agent' which is used for URL fetching

    WeasyPrint write_pdf() parameters:
    - target: Not used (handled internally)
    - stylesheets: List of CSS objects, URLs, or strings
    - Any other **kwargs parameters supported by write_pdf()

    Examples:
    - stylesheets=["https://example.com/style.css"]
    - zoom=1.5
    - presentational_hints=True
    """
    # Import WeasyPrint classes
    try:
        from weasyprint import HTML
        WEASYPRINT_AVAILABLE = True
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="WeasyPrint library not available. Please install with: pip install weasyprint"
        )

    # Validate input
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Either 'file' or 'url' parameter must be provided"
        )

    if file and url:
        raise HTTPException(
            status_code=400,
            detail="Cannot provide both 'file' and 'url' parameters"
        )

    try:
        # Extract all form parameters
        form_data = await request.form()
        weasyprint_params = {}

        # Convert form data to appropriate types
        for key, value in form_data.items():
            if key in ['file', 'url']:  # Skip file inputs
                continue
            
            # Skip None or empty values
            if value is None or value == '':
                continue

            # Handle different parameter types
            if isinstance(value, str):
                # Special handling for stylesheets parameter
                if key == 'stylesheets':
                    try:
                        # Try to parse as JSON list
                        import json
                        parsed_value = json.loads(value)
                        if isinstance(parsed_value, list):
                            weasyprint_params[key] = parsed_value
                        else:
                            weasyprint_params[key] = [parsed_value]  # Single item as list
                    except (json.JSONDecodeError, TypeError):
                        # If not valid JSON, treat as single URL/string
                        weasyprint_params[key] = [value]
                # Try to parse as boolean
                elif value.lower() in ('true', 'false'):
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
        # Remove parameters that shouldn't be passed to write_pdf
        weasyprint_params.pop('file', None)
        weasyprint_params.pop('url', None)

        # Create HTML document
        html_doc = HTML(string=html_content, base_url=base_url)

        # Generate PDF - pass all parameters directly to write_pdf
        pdf_bytes = html_doc.write_pdf(**weasyprint_params)

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
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"WeasyPrint conversion failed: {str(e)}"
        )
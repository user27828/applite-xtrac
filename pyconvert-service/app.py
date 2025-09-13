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
    """Enhanced ping endpoint that includes pandoc, weasyprint, and mammoth health information."""
    # Get pandoc health
    pandoc_healthy, pandoc_status = await check_pandoc_health()
    
    # Get weasyprint health  
    weasyprint_healthy, weasyprint_status = await check_weasyprint_health()
    
    # Get mammoth health
    mammoth_healthy, mammoth_status = await check_mammoth_health()
    
    # Get html4docx health
    html4docx_healthy, html4docx_status = await check_html4docx_health()
    
    # Get BeautifulSoup health
    beautifulsoup_healthy, beautifulsoup_status = await check_beautifulsoup_health()
    
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
        },
        "mammoth": {
            "status": "healthy" if mammoth_healthy else "unhealthy",
            "response_code": mammoth_status
        },
        "html4docx": {
            "status": "healthy" if html4docx_healthy else "unhealthy",
            "response_code": html4docx_status
        },
        "beautifulsoup": {
            "status": "healthy" if beautifulsoup_healthy else "unhealthy",
            "response_code": beautifulsoup_status
        }
    }

@app.get("/mammoth/ping")
async def ping_mammoth():
    """Check Mammoth service health."""
    healthy, status = await check_mammoth_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "mammoth"}
    else:
        raise HTTPException(status_code=503, detail=f"Mammoth service unhealthy (status: {status})")

@app.get("/pandoc/ping")
async def ping_pandoc():
    """Check Pandoc service health."""
    healthy, status = await check_pandoc_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "pandoc"}
    else:
        raise HTTPException(status_code=503, detail=f"Pandoc service unhealthy (status: {status})")

@app.get("/weasyprint/ping")
async def ping_weasyprint():
    """Check WeasyPrint service health."""
    healthy, status = await check_weasyprint_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "weasyprint"}
    else:
        raise HTTPException(status_code=503, detail=f"WeasyPrint service unhealthy (status: {status})")

@app.get("/html4docx/ping")
async def ping_html4docx():
    """Check html4docx service health."""
    healthy, status = await check_html4docx_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "html4docx"}
    else:
        raise HTTPException(status_code=503, detail=f"html4docx service unhealthy (status: {status})")

@app.get("/beautifulsoup/ping")
async def ping_beautifulsoup():
    """Check BeautifulSoup service health."""
    healthy, status = await check_beautifulsoup_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "beautifulsoup"}
    else:
        raise HTTPException(status_code=503, detail=f"BeautifulSoup service unhealthy (status: {status})")

async def check_pandoc_health() -> tuple[bool, int]:
    """
    Check pandoc service health by testing if pandoc is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple check - just return healthy for now
        return True, 200
    except Exception:
        return False, 503

async def check_weasyprint_health() -> tuple[bool, int]:
    """
    Check WeasyPrint service health by testing if weasyprint is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple import test
        import weasyprint
        return True, 200
    except ImportError:
        return False, 503
    except Exception:
        return False, 503

async def check_mammoth_health() -> tuple[bool, int]:
    """
    Check Mammoth service health by testing if mammoth is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple import test
        import mammoth
        return True, 200
    except ImportError:
        return False, 503
    except Exception:
        return False, 503

async def check_html4docx_health() -> tuple[bool, int]:
    """
    Check html4docx service health by testing if html4docx is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple import test
        import html4docx
        return True, 200
    except ImportError:
        return False, 503
    except Exception:
        return False, 503

async def check_beautifulsoup_health() -> tuple[bool, int]:
    """
    Check BeautifulSoup service health by testing if beautifulsoup4 is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple import test
        from bs4 import BeautifulSoup
        return True, 200
    except ImportError:
        return False, 503
    except Exception:
        return False, 503

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

@app.post("/mammoth")
async def mammoth_docx_to_html(
    request: Request,
    file: UploadFile = File(...),
    style_map: Optional[str] = Form(None),
    include_default_style_map: Optional[bool] = Form(True),
    include_embedded_style_map: Optional[bool] = Form(True),
    ignore_empty_paragraphs: Optional[bool] = Form(True),
    id_prefix: Optional[str] = Form(None)
):
    """
    Convert DOCX to HTML using Mammoth.

    This endpoint provides direct access to Mammoth's convert_to_html() method.
    Accepts a DOCX file upload and converts it to clean HTML.

    Mammoth Parameters:
    - style_map: Custom style mapping string (optional)
    - include_default_style_map: Whether to include default style mappings (default: True)
    - include_embedded_style_map: Whether to include embedded style maps from the document (default: True)
    - ignore_empty_paragraphs: Whether to ignore empty paragraphs (default: True)
    - id_prefix: Prefix for generated IDs (optional)

    Returns:
        HTML content as plain text response
    """
    # Import Mammoth classes
    try:
        import mammoth
        MAMMOTH_AVAILABLE = True
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Mammoth library not available. Please install with: pip install mammoth"
        )

    # Validate input file
    if not file:
        raise HTTPException(
            status_code=400,
            detail="File parameter is required"
        )

    # Validate file extension
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are supported by Mammoth"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Prepare Mammoth options
        mammoth_options = {}

        if style_map is not None:
            mammoth_options['style_map'] = style_map

        if include_default_style_map is not None:
            mammoth_options['include_default_style_map'] = include_default_style_map

        if include_embedded_style_map is not None:
            mammoth_options['include_embedded_style_map'] = include_embedded_style_map

        if ignore_empty_paragraphs is not None:
            mammoth_options['ignore_empty_paragraphs'] = ignore_empty_paragraphs

        if id_prefix is not None:
            mammoth_options['id_prefix'] = id_prefix

        # Convert DOCX to HTML using Mammoth
        from io import BytesIO
        docx_file = BytesIO(file_content)

        if mammoth_options:
            result = mammoth.convert_to_html(docx_file, **mammoth_options)
        else:
            result = mammoth.convert_to_html(docx_file)

        # Check for conversion messages/warnings
        html_content = result.value
        messages = result.messages

        # Log any warnings or errors
        if messages:
            for message in messages:
                if message.type == "warning":
                    print(f"Mammoth warning: {message.message}")
                elif message.type == "error":
                    print(f"Mammoth error: {message.message}")

        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.html"

        return StreamingResponse(
            BytesIO(html_content.encode('utf-8')),
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "MAMMOTH_DOCX_HTML"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Mammoth conversion failed: {str(e)}"
        )

@app.post("/html4docx")
async def html4docx_html_to_docx(
    request: Request,
    file: UploadFile = File(...),
    url: str = Form(None)
):
    """
    Convert HTML to DOCX using html4docx.

    This endpoint provides direct access to html4docx's conversion functionality.
    Accepts either a file upload or URL input and converts HTML to DOCX format.

    html4docx Parameters (all parameters are passed directly to html4docx):
    - Any form parameters are passed as kwargs to html4docx functions

    Examples:
    - Basic conversion: Upload a .html file
    - URL conversion: url=https://example.com
    """
    # Import html4docx classes
    try:
        from html4docx import HtmlToDocx
        HTML4DOCX_AVAILABLE = True
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="html4docx library not available. Please install with: pip install html4docx"
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
        html4docx_params = {}

        # Convert form data to appropriate types
        for key, value in form_data.items():
            if key in ['file', 'url']:  # Skip file inputs
                continue

            # Skip None or empty values
            if value is None or value == '':
                continue

            # Handle different parameter types
            if isinstance(value, str):
                # Try to parse as boolean
                if value.lower() in ('true', 'false'):
                    html4docx_params[key] = value.lower() == 'true'
                # Try to parse as number
                elif value.replace('.', '').isdigit():
                    html4docx_params[key] = float(value) if '.' in value else int(value)
                else:
                    html4docx_params[key] = value
            else:
                html4docx_params[key] = value

        html_content = None
        base_name = None

        if file:
            # Read uploaded file
            file_content = await file.read()
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}

            # Extract user_agent from params if provided
            user_agent = html4docx_params.pop('user_agent', None)
            if user_agent:
                headers["User-Agent"] = user_agent

            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text

            # Generate base name from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "webpage"

        # Create html4docx converter
        converter = HtmlToDocx()

        # Convert HTML to DOCX using parse_html_string method
        docx_document = converter.parse_html_string(html_content)
        
        # Save to BytesIO to get the bytes
        docx_bytes_io = BytesIO()
        docx_document.save(docx_bytes_io)
        docx_bytes = docx_bytes_io.getvalue()

        # Generate output filename
        output_filename = f"{base_name}.docx"

        return StreamingResponse(
            BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "HTML4DOCX_HTML_DOCX"
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
            detail=f"html4docx conversion failed: {str(e)}"
        )

@app.post("/beautifulsoup")
async def beautifulsoup_html_clean(
    request: Request,
    file: UploadFile = File(...),
    url: str = Form(None),
    parser: str = Form("html.parser"),
    prettify: bool = Form(True),
    remove_scripts: bool = Form(True),
    remove_styles: bool = Form(False),
    remove_comments: bool = Form(True),
    extract_title: bool = Form(False),
    extract_text: bool = Form(False)
):
    """
    Clean and process HTML using BeautifulSoup.

    This endpoint provides HTML cleaning and processing capabilities using BeautifulSoup.
    Accepts either a file upload or URL input and applies various cleaning operations.

    BeautifulSoup Parameters:
    - parser: HTML parser to use (default: "html.parser", options: "html.parser", "lxml", "html5lib")
    - prettify: Whether to format the HTML nicely (default: True)
    - remove_scripts: Whether to remove <script> tags (default: True)
    - remove_styles: Whether to remove <style> tags (default: False)
    - remove_comments: Whether to remove HTML comments (default: True)
    - extract_title: Whether to return only the page title (default: False)
    - extract_text: Whether to return only the text content (default: False)

    Returns:
        Cleaned HTML content or extracted text/title based on parameters
    """
    # Import BeautifulSoup classes
    try:
        from bs4 import BeautifulSoup, Comment
        BEAUTIFULSOUP_AVAILABLE = True
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="BeautifulSoup library not available. Please install with: pip install beautifulsoup4"
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
        html_content = None
        base_name = None

        if file:
            # Read uploaded file
            file_content = await file.read()
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}

            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text

            # Generate base name from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "webpage"

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, parser)

        # Apply cleaning operations
        if remove_scripts:
            # Remove all script tags
            for script in soup.find_all('script'):
                script.decompose()

        if remove_styles:
            # Remove all style tags
            for style in soup.find_all('style'):
                style.decompose()

        if remove_comments:
            # Remove all HTML comments
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

        # Handle special extraction modes
        if extract_title:
            # Extract only the title
            title_tag = soup.find('title')
            if title_tag:
                result_content = title_tag.get_text().strip()
            else:
                result_content = "No title found"
            media_type = "text/plain"
            output_filename = f"{base_name}_title.txt"

        elif extract_text:
            # Extract only the text content
            result_content = soup.get_text(separator='\n', strip=True)
            media_type = "text/plain"
            output_filename = f"{base_name}_text.txt"

        else:
            # Return cleaned HTML
            if prettify:
                result_content = soup.prettify()
            else:
                result_content = str(soup)
            media_type = "text/html"
            output_filename = f"{base_name}_cleaned.html"

        return StreamingResponse(
            BytesIO(result_content.encode('utf-8')),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "BEAUTIFULSOUP_HTML_CLEAN"
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
            detail=f"BeautifulSoup processing failed: {str(e)}"
        )

@app.get("/test-health")
async def test_health():
    """Test individual health checks."""
    results = {}
    
    # Test pandoc
    try:
        pandoc_healthy, pandoc_status = await check_pandoc_health()
        results["pandoc"] = {"healthy": pandoc_healthy, "status": pandoc_status}
    except Exception as e:
        results["pandoc"] = {"error": str(e)}
    
    # Test weasyprint
    try:
        weasyprint_healthy, weasyprint_status = await check_weasyprint_health()
        results["weasyprint"] = {"healthy": weasyprint_healthy, "status": weasyprint_status}
    except Exception as e:
        results["weasyprint"] = {"error": str(e)}
    
    # Test mammoth
    try:
        mammoth_healthy, mammoth_status = await check_mammoth_health()
        results["mammoth"] = {"healthy": mammoth_healthy, "status": mammoth_status}
    except Exception as e:
        results["mammoth"] = {"error": str(e)}
    
    # Test html4docx
    try:
        html4docx_healthy, html4docx_status = await check_html4docx_health()
        results["html4docx"] = {"healthy": html4docx_healthy, "status": html4docx_status}
    except Exception as e:
        results["html4docx"] = {"error": str(e)}
    
    # Test BeautifulSoup
    try:
        beautifulsoup_healthy, beautifulsoup_status = await check_beautifulsoup_health()
        results["beautifulsoup"] = {"healthy": beautifulsoup_healthy, "status": beautifulsoup_status}
    except Exception as e:
        results["beautifulsoup"] = {"error": str(e)}
    
    return {"results": results}
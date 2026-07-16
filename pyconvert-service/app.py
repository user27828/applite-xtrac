from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import httpx
import json
from io import BytesIO
import logging
import asyncio
import os
import shlex
import shutil
import tempfile
from typing import Optional
from starlette.background import BackgroundTask

# Import CSS margin utilities
from utils.css_margin_parser import (
    extract_page_margins_from_html,
    apply_margins_to_docx_sections,
    format_margins_for_pandoc
)
from utils.html4docx_utils import (
    HTML4DOCX_DEFAULT_PARAGRAPH_STYLE,
    apply_html4docx_font_tuning,
    normalize_docx_numbering_for_pandoc,
    prune_html4docx_styles,
    sync_docx_styles_with_effects,
)
from utils.html_utils import normalize_html_for_pandoc_docx
from utils.pdf_rendering import (
    DEFAULT_SCREENSHOT_WIDTH,
    MAX_INPUT_BYTES,
    build_download_filename,
    delete_rendered_archive,
    extract_pdf_content,
    render_pdf_pages as render_pdf_document_pages,
    validate_render_options,
)
from utils.resource_control import (
    ContentLengthLimitMiddleware,
    MAX_INPUT_BYTES as MAX_CONVERSION_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    copy_upload_to_path,
    ensure_output_size,
    read_upload_bounded,
    run_blocking,
    run_render_blocking,
    run_subprocess,
)

# Try to import python-magic for comprehensive MIME type detection
try:
    import magic  # noqa: F401
    USE_MAGIC = True
    print("python-magic loaded successfully")
except ImportError:
    USE_MAGIC = False
    print("python-magic not available, using fallback methods")

# Import unified MIME detector
from utils.mime_detector import get_mime_type as get_unified_mime_type

# Import centralized temp file manager
from utils.temp_file_manager import (
    TempFileManager
)

app = FastAPI()
app.add_middleware(ContentLengthLimitMiddleware)

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
    
    # Get PyMuPDF health
    pymupdf_healthy, pymupdf_status = await check_pymupdf_health()
    
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
        },
        "pymupdf": {
            "status": "healthy" if pymupdf_healthy else "unhealthy",
            "response_code": pymupdf_status
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

@app.get("/pymupdf/ping")
async def ping_pymupdf():
    """Check PyMuPDF service health."""
    healthy, status = await check_pymupdf_health()
    if healthy:
        return {"success": True, "data": "PONG!", "service": "pymupdf"}
    else:
        raise HTTPException(status_code=503, detail=f"PyMuPDF service unhealthy (status: {status})")

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
        import weasyprint  # noqa: F401
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
        import mammoth  # noqa: F401
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
        import html4docx  # noqa: F401
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
        from bs4 import BeautifulSoup  # noqa: F401
        return True, 200
    except ImportError:
        return False, 503
    except Exception:
        return False, 503

async def check_pymupdf_health() -> tuple[bool, int]:
    """
    Check PyMuPDF service health by testing if PyMuPDF is available.
    
    Returns:
        tuple: (is_healthy: bool, status_code: int)
    """
    try:
        # Simple import test
        import fitz  # noqa: F401
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


async def _fetch_text_bounded(url: str, headers: Optional[dict] = None) -> str:
    """Fetch text without allowing an unbounded HTTP response allocation."""
    chunks = []
    total_bytes = 0
    async with httpx.AsyncClient(timeout=30.0, headers=headers or {}) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_CONVERSION_INPUT_BYTES:
                        raise HTTPException(status_code=413, detail="Remote input exceeds the configured size limit")
                except ValueError:
                    pass
            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_CONVERSION_INPUT_BYTES:
                    raise HTTPException(status_code=413, detail="Remote input exceeds the configured size limit")
                chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _render_weasyprint_pdf(html_content: str, base_url: Optional[str], parameters: dict) -> bytes:
    from weasyprint import HTML

    return ensure_output_size(HTML(string=html_content, base_url=base_url).write_pdf(**parameters))


def _convert_html4docx_bytes(html_content: str) -> bytes:
    from docx import Document
    from html4docx import HtmlToDocx

    converter = HtmlToDocx(default_paragraph_style=HTML4DOCX_DEFAULT_PARAGRAPH_STYLE)
    document = Document()
    apply_html4docx_font_tuning(document)
    try:
        prune_html4docx_styles(document)
        converter.add_html_to_document(html_content, document)
    except KeyError:
        document = Document()
        apply_html4docx_font_tuning(document)
        converter = HtmlToDocx(default_paragraph_style=HTML4DOCX_DEFAULT_PARAGRAPH_STYLE)
        converter.add_html_to_document(html_content, document)

    margins = extract_page_margins_from_html(html_content)
    if margins:
        apply_margins_to_docx_sections(document, margins)

    output = BytesIO()
    document.save(output)
    content = normalize_docx_numbering_for_pandoc(output.getvalue())
    return ensure_output_size(sync_docx_styles_with_effects(content))


def _clean_html_content(
    html_content: str,
    parser: str,
    remove_scripts: bool,
    remove_styles: bool,
    remove_comments: bool,
    extract_title: bool,
    extract_text: bool,
    prettify: bool,
) -> tuple[bytes, str, str]:
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html_content, parser)
    if remove_scripts:
        for script in soup.find_all("script"):
            script.decompose()
    if remove_styles:
        for style in soup.find_all("style"):
            style.decompose()
    if remove_comments:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    if extract_title:
        title_tag = soup.find("title")
        result = title_tag.get_text().strip() if title_tag else "No title found"
        media_type, suffix = "text/plain", "_title.txt"
    elif extract_text:
        result = soup.get_text(separator="\n", strip=True)
        media_type, suffix = "text/plain", "_text.txt"
    else:
        result = soup.prettify() if prettify else str(soup)
        media_type, suffix = "text/html", "_cleaned.html"
    return ensure_output_size(result.encode("utf-8")), media_type, suffix

@app.post("/pandoc")
async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    output_format: str = Form(...),
    extra_args: str = Form("")
):
    # Validate output format
    allowed_formats = ["pdf", "docx", "html", "txt", "md", "tex", "json"]
    if output_format not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported output format: {output_format}")

    is_html_input = (
        (file.filename or "").lower().endswith(('.html', '.htm'))
        or 'text/html' in (file.content_type or '').lower()
        or '--from=html' in extra_args
    )
    manager = TempFileManager(service="pandoc")
    input_temp = manager.create_temp_file(
        extension=os.path.splitext(file.filename or "input")[1],
        prefix="pyconvert_input"
    )
    input_path = input_temp.path
    output_temp = manager.create_temp_file(
        extension=f".{output_format}",
        prefix="pyconvert_output"
    )
    output_path = output_temp.path
    cleanup_deferred = False

    try:
        file_content = None
        if is_html_input:
            file_content = await read_upload_bounded(file)
            if output_format == "docx":
                html_content = file_content.decode('utf-8', errors='replace')
                file_content = normalize_html_for_pandoc_docx(html_content).encode('utf-8')
            with open(input_path, "wb") as input_file:
                input_file.write(file_content)
        else:
            await copy_upload_to_path(file, input_path)

        # Special handling for LaTeX to PDF conversion
        if output_format == "pdf" and (input_path.endswith('.tex') or input_path.endswith('.latex')):
            # Use pdflatex directly for LaTeX to PDF conversion
            # Extract base name without extension for jobname
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(output_path)
            
            cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", output_dir, "-jobname", base_name, input_path]
            return_code, stdout, stderr, stdout_truncated, stderr_truncated = await run_subprocess(cmd)
            
            # For LaTeX, return code 1 often just means warnings, not fatal errors
            # Check if PDF was actually created despite warnings
            latex_output_path = os.path.join(output_dir, base_name + ".pdf")
            
            if return_code != 0 and not os.path.exists(latex_output_path):
                # Only fail if PDF wasn't created
                error_msg = f"pdflatex failed with return code {return_code}"
                if stderr:
                    error_msg += f". stderr: {stderr.decode('utf-8', errors='replace')}"
                if stdout:
                    error_msg += f". stdout: {stdout.decode('utf-8', errors='replace')}"
                if stdout_truncated or stderr_truncated:
                    error_msg += ". Diagnostic output was truncated"
                if not stderr and not stdout:
                    error_msg += ". No error output captured"
                raise HTTPException(status_code=500, detail=error_msg)
            elif return_code != 0 and os.path.exists(latex_output_path):
                # PDF was created despite warnings - log the warnings but continue
                logging.warning("pdflatex produced a PDF with return code %s", return_code)
            
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
            if output_format == "json":
                # For JSON output, extract AST representation
                cmd = ["pandoc", input_path, "-t", "json"]
            else:
                cmd = ["pandoc", input_path, "-o", output_path]
            
            # Special handling for PDF output - need to specify PDF engine
            if output_format == "pdf":
                cmd = ["pandoc", input_path, "-o", output_path, "--pdf-engine=xelatex"]
            
            # Extract and apply CSS @page margins for HTML input to DOCX/PDF output
            if is_html_input:
                try:
                    # Read HTML content to extract margins
                    assert file_content is not None
                    html_content = file_content.decode('utf-8', errors='replace')
                    margins = extract_page_margins_from_html(html_content)
                    
                    if margins and output_format in ['docx', 'pdf']:
                        # Add margin variables to pandoc command
                        pandoc_vars = format_margins_for_pandoc(margins)
                        for var_name, var_value in pandoc_vars.items():
                            cmd.extend(['-V', f'{var_name}={var_value}'])
                        
                        print(f"Applied margins to pandoc {output_format}: {margins}")
                except Exception as margin_error:
                    # Log the error but don't fail the conversion
                    print(f"Warning: Failed to extract margins for pandoc: {margin_error}")
            
            # Add extra args if provided
            if extra_args:
                cmd.extend(shlex.split(extra_args))

            return_code, stdout, stderr, stdout_truncated, stderr_truncated = await run_subprocess(cmd)
            
            if return_code != 0:
                error_msg = f"Pandoc failed with return code {return_code}"
                if stderr:
                    error_msg += f". stderr: {stderr.decode('utf-8', errors='replace')}"
                if stdout:
                    error_msg += f". stdout: {stdout.decode('utf-8', errors='replace')}"
                if stdout_truncated or stderr_truncated:
                    error_msg += ". Diagnostic output was truncated"
                if not stderr and not stdout:
                    error_msg += ". No error output captured"
                raise HTTPException(status_code=500, detail=error_msg)

        # Handle JSON output differently - return JSON content directly
        if output_format == "json":
            if stdout_truncated:
                raise HTTPException(status_code=413, detail="Pandoc JSON output exceeds the configured size limit")
            # Parse and validate the JSON AST
            try:
                ast_data = json.loads(stdout)
                manager.cleanup_all()
                return JSONResponse(
                    content=ast_data,
                    media_type="application/json",
                    headers={
                        "Content-Disposition": f"attachment; filename={os.path.splitext(file.filename)[0]}.json",
                        "X-Conversion-Service": "PANDOC_JSON_AST"
                    }
                )
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse pandoc JSON AST: {str(e)}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) > MAX_OUTPUT_BYTES:
            raise HTTPException(status_code=413, detail="Conversion output exceeds the configured size limit")

        media_type = get_unified_mime_type(filename=output_path, expected_format=output_format)
        manager.cleanup_file(input_path)
        cleanup_deferred = True
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=f"{os.path.splitext(file.filename or 'converted')[0]}.{output_format}",
            background=BackgroundTask(manager.cleanup_all),
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Conversion timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if not cleanup_deferred:
            manager.cleanup_all()


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
    # Fail fast before accepting expensive work if the optional engine is absent.
    try:
        import weasyprint  # noqa: F401
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
            file_content = await read_upload_bounded(file)
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}

            # Extract user_agent from params if provided
            user_agent = weasyprint_params.pop('user_agent', None)
            if user_agent:
                headers["User-Agent"] = user_agent

            html_content = await _fetch_text_bounded(url, headers)
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

        # Extract and log CSS @page margins for validation (WeasyPrint supports them natively)
        try:
            margins = extract_page_margins_from_html(html_content)
            if margins:
                print(f"WeasyPrint detected margins in HTML: {margins}")
                print("Note: WeasyPrint respects CSS @page margins natively")
        except Exception as margin_error:
            # Log the error but don't fail the conversion
            print(f"Warning: Failed to extract margins for WeasyPrint validation: {margin_error}")

        # Generate PDF - pass all parameters directly to write_pdf
        pdf_bytes = await run_blocking(
            _render_weasyprint_pdf,
            html_content,
            base_url,
            weasyprint_params,
        )

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
    except HTTPException:
        raise
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
        file_content = await read_upload_bounded(file)

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
            result = await run_blocking(mammoth.convert_to_html, docx_file, **mammoth_options)
        else:
            result = await run_blocking(mammoth.convert_to_html, docx_file)

        # Check for conversion messages/warnings
        html_content = ensure_output_size(result.value.encode("utf-8"))
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
            BytesIO(html_content),
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "MAMMOTH_DOCX_HTML"
            }
        )

    except HTTPException:
        raise
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
        import docx  # noqa: F401
        import html4docx  # noqa: F401
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
            file_content = await read_upload_bounded(file)
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}

            # Extract user_agent from params if provided
            user_agent = html4docx_params.pop('user_agent', None)
            if user_agent:
                headers["User-Agent"] = user_agent

            html_content = await _fetch_text_bounded(url, headers)

            # Generate base name from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "webpage"

        docx_bytes = await run_blocking(_convert_html4docx_bytes, html_content)

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
    except HTTPException:
        raise
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
        import bs4  # noqa: F401
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
            file_content = await read_upload_bounded(file)
            html_content = file_content.decode('utf-8', errors='replace')
            base_name = file.filename.rsplit(".", 1)[0] if file.filename and "." in file.filename else "document"

        elif url:
            # Fetch HTML from URL
            headers = {}

            html_content = await _fetch_text_bounded(url, headers)

            # Generate base name from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_name = parsed_url.netloc + parsed_url.path.replace('/', '_')
            if not base_name:
                base_name = "webpage"

        result_content, media_type, output_suffix = await run_blocking(
            _clean_html_content,
            html_content,
            parser,
            remove_scripts,
            remove_styles,
            remove_comments,
            extract_title,
            extract_text,
            prettify,
        )
        output_filename = f"{base_name}{output_suffix}"

        return StreamingResponse(
            BytesIO(result_content),
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"BeautifulSoup processing failed: {str(e)}"
        )

async def _copy_pdf_upload_to_temp(file: UploadFile) -> str:
    """Persist an uploaded PDF with a strict size limit for file-backed rendering."""
    declared_size = getattr(file, "size", None)
    if isinstance(declared_size, int) and declared_size > MAX_INPUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Input exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MiB limit",
        )

    temporary_file = tempfile.NamedTemporaryFile(prefix="pdf_render_", suffix=".pdf", delete=False)
    temporary_path = temporary_file.name
    total_bytes = 0

    try:
        await file.seek(0)
        with temporary_file:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_INPUT_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Input exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MiB limit",
                    )
                temporary_file.write(chunk)
        return temporary_path
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


@app.post("/pymupdf/render-pages")
async def pymupdf_render_pages(
    file: UploadFile = File(...),
    page: str = Form("1"),
    max_width: int = Form(DEFAULT_SCREENSHOT_WIDTH),
    image_format: str = Form("jpg", alias="format"),
    quality: Optional[int] = Form(None),
):
    """Render one PDF page or all pages as bounded PNG/JPG image output."""
    options = validate_render_options(page, max_width, image_format, quality)
    temporary_pdf = await _copy_pdf_upload_to_temp(file)

    try:
        result = await run_render_blocking(
            render_pdf_document_pages,
            temporary_pdf,
            file.filename or "document.pdf",
            options,
        )
    finally:
        try:
            os.unlink(temporary_pdf)
        except FileNotFoundError:
            pass

    output_filename = build_download_filename(file.filename or "document.pdf", options.pages, options.image_format)
    if result.archive_path:
        return FileResponse(
            result.archive_path,
            media_type="application/zip",
            filename=output_filename,
            background=BackgroundTask(delete_rendered_archive, result.archive_path),
        )

    media_type = "image/jpeg" if options.image_format == "jpg" else "image/png"
    return StreamingResponse(
        BytesIO(result.image_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{output_filename}"',
            "X-Conversion-Service": "PYMUPDF_RENDER",
        },
    )


@app.post("/pymupdf/pdf-html")
async def pymupdf_pdf_to_html(
    file: UploadFile = File(...)
):
    """
    Convert PDF to HTML using PyMuPDF (fitz).

    This endpoint provides direct access to PyMuPDF's HTML conversion functionality.
    Accepts a PDF file upload and converts it to HTML format.

    PyMuPDF Parameters:
    - File upload only (no URL support for now)

    Returns:
        HTML content as streaming response
    """
    # Validate input file
    if not file:
        raise HTTPException(
            status_code=400,
            detail="File parameter is required"
        )

    # Validate file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only .pdf files are supported by PyMuPDF"
        )

    temporary_pdf = await _copy_pdf_upload_to_temp(file)
    try:
        full_html = await run_blocking(
            extract_pdf_content,
            temporary_pdf,
            file.filename or "document.pdf",
            "html",
        )
    finally:
        try:
            os.unlink(temporary_pdf)
        except FileNotFoundError:
            pass

    try:
        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.html"

        return StreamingResponse(
            BytesIO(full_html),
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "PYMUPDF_PDF_HTML"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PyMuPDF conversion failed: {str(e)}"
        )

@app.post("/pymupdf/pdf-txt")
async def pymupdf_pdf_to_txt(
    file: UploadFile = File(...)
):
    """
    Convert PDF to plain text using PyMuPDF (fitz).

    This endpoint provides direct access to PyMuPDF's text extraction functionality.
    Accepts a PDF file upload and converts it to plain text format.

    PyMuPDF Parameters:
    - File upload only (no URL support for now)

    Returns:
        Plain text content as streaming response
    """
    # Validate input file
    if not file:
        raise HTTPException(
            status_code=400,
            detail="File parameter is required"
        )

    # Validate file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only .pdf files are supported by PyMuPDF"
        )

    temporary_pdf = await _copy_pdf_upload_to_temp(file)
    try:
        text_content = await run_blocking(
            extract_pdf_content,
            temporary_pdf,
            file.filename or "document.pdf",
            "txt",
        )
    finally:
        try:
            os.unlink(temporary_pdf)
        except FileNotFoundError:
            pass

    try:
        # Generate output filename
        base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        output_filename = f"{base_name}.txt"

        return StreamingResponse(
            BytesIO(text_content),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Conversion-Service": "PYMUPDF_PDF_TXT"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PyMuPDF conversion failed: {str(e)}"
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
    
    # Test PyMuPDF
    try:
        pymupdf_healthy, pymupdf_status = await check_pymupdf_health()
        results["pymupdf"] = {"healthy": pymupdf_healthy, "status": pymupdf_status}
    except Exception as e:
        results["pymupdf"] = {"error": str(e)}
    
    return {"results": results}


if __name__ == "__main__":
    import random
    import uvicorn

    max_requests = int(os.getenv("APPLITEXTRAC_MAX_REQUESTS", "1000"))
    max_requests_jitter = int(os.getenv("APPLITEXTRAC_MAX_REQUESTS_JITTER", "100"))
    if max_requests < 1 or max_requests_jitter < 0:
        raise RuntimeError("Request recycling limits must be positive (jitter may be zero)")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=3000,
        limit_concurrency=int(os.getenv("APPLITEXTRAC_LIMIT_CONCURRENCY", "16")),
        limit_max_requests=max_requests + random.SystemRandom().randint(0, max_requests_jitter),
    )

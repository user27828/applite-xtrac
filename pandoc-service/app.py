from fastapi import FastAPI, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
import tempfile
import os
import shutil

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

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"success": True, "data": "PONG!"}

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

@app.post("/convert")
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

    # Create temp files
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as input_file:
        shutil.copyfileobj(file.file, input_file)
        input_path = input_file.name

    output_path = input_path + f".{output_format}"

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
            
            # Add extra args if provided
            if extra_args:
                cmd.extend(extra_args.split())

            # Run pandoc
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Pandoc error: {result.stderr}")

        # Get MIME type using comprehensive detection
        media_type = get_mime_type(output_path, output_format)

        # Return the converted file and schedule cleanup after response
        def _cleanup(paths):
            for p in paths:
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    pass

        background_tasks.add_task(_cleanup, [input_path, output_path])

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
        # If exception occurred before scheduling cleanup, try to remove files here
        try:
            if os.path.exists(input_path):
                os.unlink(input_path)
        except Exception:
            pass
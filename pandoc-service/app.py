from fastapi import FastAPI, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
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

    # Create temp files using centralized manager
    manager = get_temp_manager()

    # Read file content
    file_content = await file.read()

    # Create input temp file
    input_temp = manager.create_temp_file(
        content=file_content,
        extension=os.path.splitext(file.filename)[1],
        prefix="pandoc_input"
    )
    input_path = input_temp.path

    # Create output temp file path
    output_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
    output_temp = manager.create_temp_file(
        filename=output_filename,
        prefix="pandoc_output"
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
            
            # Add extra args if provided
            if extra_args:
                cmd.extend(extra_args.split())

            # Run pandoc
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Pandoc error: {result.stderr}")

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
from fastapi import FastAPI, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
import tempfile
import os
import shutil

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"success": True, "data": "PONG!"}

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
        # Build pandoc command
        cmd = ["pandoc", input_path, "-o", output_path]
        
        # Add extra args if provided
        if extra_args:
            cmd.extend(extra_args.split())

        # Run pandoc
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Pandoc error: {result.stderr}")

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
            media_type="application/octet-stream",
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
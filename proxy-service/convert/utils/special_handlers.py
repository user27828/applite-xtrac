"""
Special conversion handlers for the /convert endpoints.

This module contains custom conversion logic for special cases that don't
follow the standard conversion patterns.
"""

import json
import tempfile
import os
from fastapi import HTTPException, Request
from fastapi.responses import Response
from io import BytesIO

from ..config import ConversionService
from .conversion_core import _convert_file
from .unstructured_utils import process_unstructured_json_to_content


async def process_presentation_to_html(request, file_content, input_format, output_format, step_config):
    """
    Special handler for converting presentation formats (KEY/ODP) to HTML.

    This consolidates the duplicate logic from key-html and odp-html conversions.

    Args:
        request: FastAPI request object
        file_content: The file content as bytes
        input_format: Input format (should be 'pptx' for intermediate step)
        output_format: Output format (should be 'html')
        step_config: Configuration for this step

    Returns:
        Response object with HTML content
    """
    try:
        # Step 1: Convert PPTX to JSON using unstructured-io
        from io import BytesIO

        # Create a temporary file for the PPTX content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Create a new UploadFile-like object for the PPTX content
            class TempUploadFile:
                def __init__(self, content: bytes, filename: str):
                    self.filename = filename
                    self.content = content
                    self._position = 0

                async def read(self):
                    return self.content

                async def seek(self, position: int):
                    self._position = position

            temp_upload = TempUploadFile(file_content, "converted.pptx")

            # Convert PPTX to JSON
            json_response = await _convert_file(
                request=request,
                file=temp_upload,
                input_format="pptx",
                output_format="json",
                service=ConversionService.UNSTRUCTURED_IO
            )

            # Extract JSON content
            json_content = b""
            async for chunk in json_response.body_iterator:
                json_content += chunk

            json_data = json.loads(json_content.decode('utf-8'))

            # Step 2: Convert JSON to HTML locally
            html_content = process_unstructured_json_to_content(json_data, "html")

            # Return HTML response
            return Response(
                content=html_content,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename=converted.html"}
            )

        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Special presentation conversion failed: {str(e)}")

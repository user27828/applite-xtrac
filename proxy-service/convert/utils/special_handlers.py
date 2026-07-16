"""
Special conversion handlers for the /convert endpoints.

This module contains custom conversion logic for special cases that don't
follow the standard conversion patterns.
"""

import json
from fastapi import HTTPException
from fastapi.responses import Response

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

        # Extract JSON content (collect chunks to avoid O(n²) concat)
        chunks = []
        async for chunk in json_response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode('utf-8'))
        json_content = b''.join(chunks)

        json_data = json.loads(json_content.decode('utf-8'))

        # Step 2: Convert JSON to HTML locally
        html_content = process_unstructured_json_to_content(json_data, "html")

        # Return HTML response
        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=converted.html"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Special presentation conversion failed: {str(e)}")

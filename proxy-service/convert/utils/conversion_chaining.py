"""
Utility functions for chained conversion operations.

This module provides generalized functions for chaining multiple conversion
steps together, where the output of one service becomes the input for another.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
from io import BytesIO
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from ..config import ConversionService
from .conversion_core import _get_service_client, DYNAMIC_SERVICE_URLS

# Try to import unstructured functions for local markdown/text conversion
try:
    from unstructured.staging.base import elements_to_md, elements_to_text, dict_to_elements
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    elements_to_md = None
    elements_to_text = None
    dict_to_elements = None

logger = logging.getLogger(__name__)


class ConversionStep:
    """Represents a single step in a chained conversion process."""

    def __init__(
        self,
        service: ConversionService,
        input_format: str,
        output_format: str,
        extra_params: Optional[Dict[str, Any]] = None,
        description: str = ""
    ):
        self.service = service
        self.input_format = input_format
        self.output_format = output_format
        self.extra_params = extra_params or {}
        self.description = description


async def chain_conversions(
    request: Request,
    initial_file_content: bytes,
    initial_filename: str,
    conversion_steps: List[ConversionStep],
    final_output_format: str,
    final_content_type: str = "application/octet-stream"
) -> StreamingResponse:
    """
    Execute a chain of conversion steps where each step's output becomes the next step's input.

    This function provides a generalized way to chain multiple conversion services together,
    where the output of one service automatically becomes the input for the next service in the chain.

    Args:
        request: FastAPI request object (needed for service client access)
        initial_file_content: Raw bytes of the initial file to convert
        initial_filename: Original filename (used for generating output filename)
        conversion_steps: List of ConversionStep objects defining the conversion chain
        final_output_format: Final output format (e.g., 'md', 'pdf', 'html')
        final_content_type: MIME type for the final response (e.g., 'text/markdown')

    Returns:
        StreamingResponse with the final converted content

    Raises:
        HTTPException: If any step in the conversion chain fails

    Example:
        ```python
        from .utils.conversion_chaining import chain_conversions, ConversionStep, ConversionService

        steps = [
            ConversionStep(ConversionService.LIBREOFFICE, "pages", "docx"),
            ConversionStep(ConversionService.PANDOC, "docx", "md", {"extra_args": "--from=docx"})
        ]

        response = await chain_conversions(
            request=request,
            initial_file_content=file_bytes,
            initial_filename="document.pages",
            conversion_steps=steps,
            final_output_format="md",
            final_content_type="text/markdown"
        )
        ```
    """
    if not conversion_steps:
        raise HTTPException(status_code=400, detail="No conversion steps provided")

    current_content = initial_file_content
    current_filename = initial_filename

    logger.info(f"Starting chained conversion with {len(conversion_steps)} steps")

    # Execute each step in the chain
    for step_idx, step in enumerate(conversion_steps):
        logger.info(f"Executing step {step_idx + 1}/{len(conversion_steps)}: {step.service.value} ({step.input_format} → {step.output_format})")

        try:
            # Get the appropriate client for this service
            client = await _get_service_client(step.service, request)
            service_url = DYNAMIC_SERVICE_URLS[step.service]

            # Prepare the request based on service type
            if step.service == ConversionService.LIBREOFFICE:
                # LibreOffice conversion
                files = {"file": (current_filename, BytesIO(current_content), f"application/{step.input_format}")}
                data = {"convert-to": step.output_format}

                response = await client.post(
                    f"{service_url}/request",
                    files=files,
                    data=data
                )

            elif step.service == ConversionService.PANDOC:
                # Pandoc conversion
                files = {"file": (current_filename, BytesIO(current_content), f"application/{step.input_format}")}
                data = {"output_format": step.output_format}

                # Add input format as extra arg if needed
                if step.input_format != "md":  # pandoc defaults to markdown
                    # Map tex/latex to latex for Pandoc
                    pandoc_input_format = "latex" if step.input_format in ["tex", "latex"] else step.input_format
                    data["extra_args"] = f"--from={pandoc_input_format}"

                # Add any additional parameters
                data.update(step.extra_params)

                response = await client.post(
                    f"{service_url}/convert",
                    files=files,
                    data=data
                )

            elif step.service == ConversionService.UNSTRUCTURED_IO:
                # Unstructured IO conversion
                files = {"files": (current_filename, BytesIO(current_content), f"application/{step.input_format}")}
                
                # Special handling for markdown/text outputs from unstructured-io
                if step.output_format in ["md", "txt"]:
                    # For markdown/text, get JSON from unstructured-io and convert locally
                    data = {}  # No output_format specified to get JSON
                    
                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        # Convert JSON response to elements and then to markdown/text
                        json_data = response.json()
                        
                        # Check if unstructured library is available
                        if not UNSTRUCTURED_AVAILABLE:
                            raise HTTPException(
                                status_code=503, 
                                detail="Unstructured library not available for local markdown/text conversion"
                            )
                        
                        # Convert JSON to elements - json_data is already a list of element dicts
                        elements = dict_to_elements(json_data)
                        
                        # Convert to markdown or text
                        if step.output_format == "md":
                            content = elements_to_md(elements)
                            media_type = "text/markdown"
                        else:  # txt
                            content = elements_to_text(elements)
                            media_type = "text/plain"
                        
                        # Generate output filename
                        base_name = current_filename.rsplit(".", 1)[0] if "." in current_filename else current_filename
                        output_filename = f"{base_name}.{step.output_format}"
                        
                        # Return the converted content
                        current_content = content.encode('utf-8')
                        current_filename = output_filename
                        continue  # Skip the rest of the loop and continue to next step
                            
                    else:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Unstructured-IO service error: {response.text}"
                        )
                else:
                    # Regular unstructured-io conversion
                    # Map output_format to MIME types for Unstructured-IO (same as _convert_file)
                    mime_mapping = {
                        "json": "application/json",
                        "md": "text/markdown", 
                        "txt": "text/plain"
                    }
                    unstructured_output_format = mime_mapping.get(step.output_format, step.output_format)
                    data = {"output_format": unstructured_output_format}
                    data.update(step.extra_params)

                    response = await client.post(
                        f"{service_url}/general/v0/general",
                        files=files,
                        data=data
                    )

            elif step.service == ConversionService.GOTENBERG:
                # Gotenberg conversion
                files = {"files": (current_filename, BytesIO(current_content), f"application/{step.input_format}")}
                data = {}

                # Determine endpoint based on input format
                if step.input_format in ['docx', 'pptx', 'xlsx', 'xls', 'ppt', 'odt', 'ods', 'odp', 'pages']:
                    endpoint = "forms/libreoffice/convert"
                else:
                    endpoint = "forms/chromium/convert/html"

                response = await client.post(
                    f"{service_url}/{endpoint}",
                    files=files,
                    data=data
                )

            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Unsupported service in chain: {step.service.value}"
                )

            # Check response
            if response.status_code != 200:
                logger.error(f"Step {step_idx + 1} failed: {step.service.value} returned {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Conversion step {step_idx + 1} failed ({step.service.value}): {response.text}"
                )

            # Update content for next step
            current_content = response.content
            current_filename = f"converted_step_{step_idx + 1}.{step.output_format}"

            logger.info(f"Step {step_idx + 1} completed successfully, output size: {len(current_content)} bytes")

        except Exception as e:
            logger.error(f"Error in conversion step {step_idx + 1} ({step.service.value}): {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Conversion step {step_idx + 1} failed: {str(e)}"
            )

    # Generate final output filename
    base_name = initial_filename.rsplit(".", 1)[0] if "." in initial_filename else initial_filename
    final_filename = f"{base_name}.{final_output_format}"

    logger.info(f"Chained conversion completed successfully, final output: {final_filename}")

    return StreamingResponse(
        BytesIO(current_content),
        media_type=final_content_type,
        headers={"Content-Disposition": f"attachment; filename={final_filename}"}
    )



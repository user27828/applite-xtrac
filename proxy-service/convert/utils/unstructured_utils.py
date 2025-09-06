"""
Consolidated utilities for processing unstructured-io data.

This module provides centralized functions for converting unstructured-io JSON responses
to various output formats, eliminating code duplication across the codebase.
"""

from typing import List, Union, Optional
from fastapi import HTTPException
import logging

# Import unstructured libraries
try:
    from unstructured.staging.base import elements_to_md, elements_to_text, dict_to_elements
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    elements_to_md = None
    elements_to_text = None
    dict_to_elements = None
    UNSTRUCTURED_AVAILABLE = False

logger = logging.getLogger(__name__)


def process_unstructured_json_to_content(
    json_data: List[dict],
    output_format: str,
    fix_tables: bool = True
) -> str:
    """
    Convert unstructured-io JSON response to content (markdown or text).

    This is the centralized function for processing unstructured-io data,
    replacing duplicated code across the codebase.

    Args:
        json_data: List of element dictionaries from unstructured-io
        output_format: Desired output format ("md" or "txt")
        fix_tables: Whether to apply table text_as_html fixes (default: True)

    Returns:
        Content string in the requested format

    Raises:
        HTTPException: If unstructured library is not available or conversion fails
    """
    if not UNSTRUCTURED_AVAILABLE or not dict_to_elements:
        raise HTTPException(
            status_code=503,
            detail="Unstructured library not available for content conversion"
        )

    try:
        # Fix table text_as_html issues if requested
        if fix_tables:
            from .conversion_core import fix_table_text_as_html
            json_data = fix_table_text_as_html(json_data)

        # Convert JSON to elements
        elements = []
        for item in json_data:
            elements.extend(dict_to_elements([item]))

        # Filter out elements with None text to prevent join errors
        filtered_elements = [elem for elem in elements if elem.text is not None]

        # Convert to requested format
        if output_format == "md":
            if not elements_to_md:
                raise HTTPException(
                    status_code=503,
                    detail="Unstructured elements_to_md not available"
                )
            content = elements_to_md(filtered_elements)
        elif output_format == "txt":
            if not elements_to_text:
                raise HTTPException(
                    status_code=503,
                    detail="Unstructured elements_to_text not available"
                )
            content = elements_to_text(filtered_elements)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported output format: {output_format}"
            )

        return content

    except Exception as e:
        logger.exception(f"Error processing unstructured data to {output_format}")
        raise HTTPException(
            status_code=500,
            detail=f"Content conversion failed: {str(e)}"
        )


def json_to_elements(json_data: List[dict], fix_tables: bool = True) -> List:
    """
    Convert unstructured-io JSON response to elements only (without content conversion).

    Args:
        json_data: List of element dictionaries from unstructured-io
        fix_tables: Whether to apply table text_as_html fixes (default: True)

    Returns:
        List of element objects
    """
    if not UNSTRUCTURED_AVAILABLE or not dict_to_elements:
        raise HTTPException(
            status_code=503,
            detail="Unstructured library not available for element conversion"
        )

    try:
        # Fix table text_as_html issues if requested
        if fix_tables:
            from .conversion_core import fix_table_text_as_html
            json_data = fix_table_text_as_html(json_data)

        # Convert JSON to elements
        elements = []
        for item in json_data:
            elements.extend(dict_to_elements([item]))

        return elements

    except Exception as e:
        logger.exception("Error converting JSON to elements")
        raise HTTPException(
            status_code=500,
            detail=f"Element conversion failed: {str(e)}"
        )

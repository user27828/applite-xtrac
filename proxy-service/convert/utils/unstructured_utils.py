"""
Consolidated utilities for processing unstructured-io data.

This module provides centralized functions for converting unstructured-io JSON responses
to various output formats, eliminating code duplication across the codebase.
"""

from html import escape
from typing import Any, List
from fastapi import HTTPException
import json
import logging

# Import httpx for async HTTP requests
import httpx

from .resource_limits import MAX_ERROR_BYTES, read_response_bounded

def is_unstructured_available() -> bool:
    """The proxy's dictionary formatter has no heavyweight optional dependency."""
    return True


logger = logging.getLogger(__name__)


def process_unstructured_json_to_content(
    json_data: List[dict],
    output_format: str,
    fix_tables: bool = True
) -> str:
    """
    Convert unstructured-io JSON response to Markdown, text, or HTML.

    This is the centralized function for processing unstructured-io data,
    replacing duplicated code across the codebase.

    Args:
        json_data: List of element dictionaries from unstructured-io
        output_format: Desired output format ("md", "txt", or "html")
        fix_tables: Whether to apply table text_as_html fixes (default: True)

    Returns:
        Content string in the requested format

    Raises:
        HTTPException: If the requested format is unsupported or conversion fails
    """
    try:
        # Fix table text_as_html issues if requested
        if fix_tables:
            from .conversion_core import fix_table_text_as_html
            json_data = fix_table_text_as_html(json_data)

        filtered_elements = [item for item in json_data if item.get("text") is not None]

        # Convert to requested format
        if output_format == "md":
            content = "\n".join(_element_markdown(item) for item in filtered_elements)
        elif output_format == "txt":
            content = "\n".join(str(item["text"]) for item in filtered_elements if item["text"])
        elif output_format == "html":
            content_parts = []
            for item in filtered_elements:
                table_html = item.get("metadata", {}).get("text_as_html")
                if item.get("type") == "Table" and table_html:
                    content_parts.append(_sanitize_table_html(table_html))
                elif item.get("text"):
                    content_parts.append(f"<p>{escape(str(item['text']))}</p>")
            
            content = "\n".join(content_parts)
            # Wrap in basic HTML structure
            content = f"<!DOCTYPE html>\n<html>\n<head>\n<title>Converted Document</title>\n</head>\n<body>\n{content}\n</body>\n</html>"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported output format: {output_format}"
            )

        return content

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing unstructured data to {output_format}")
        raise HTTPException(
            status_code=500,
            detail=f"Content conversion failed: {str(e)}"
        )


def _element_markdown(item: dict) -> str:
    text = str(item.get("text", ""))
    if item.get("type") == "Title":
        return f"# {text}"
    table_html = item.get("metadata", {}).get("text_as_html")
    if item.get("type") == "Table" and table_html:
        return _sanitize_table_html(table_html)
    return text


def _sanitize_table_html(table_html: str) -> str:
    """Retain table structure while removing executable markup and attributes."""
    from bs4 import BeautifulSoup

    allowed_tags = {"table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption"}
    soup = BeautifulSoup(table_html, "html.parser")
    dangerous_tags = {"script", "style", "template", "iframe", "object", "embed"}
    for tag in list(soup.find_all(True)):
        if tag.name is None:
            continue
        if tag.name in dangerous_tags:
            tag.decompose()
            continue
        if tag.name not in allowed_tags:
            tag.unwrap()
        else:
            safe_attrs = {}
            for name in ("colspan", "rowspan"):
                raw_value = tag.attrs.get(name)
                if raw_value is not None:
                    try:
                        value = int(raw_value)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= value <= 1000:
                        safe_attrs[name] = str(value)
            tag.attrs = safe_attrs
    return str(soup)


def json_to_elements(json_data: List[dict], fix_tables: bool = True) -> List[dict]:
    """
    Convert unstructured-io JSON response to elements only (without content conversion).

    Args:
        json_data: List of element dictionaries from unstructured-io
        fix_tables: Whether to apply table text_as_html fixes (default: True)

    Returns:
        The element dictionaries, with optional table repair applied
    """
    try:
        # Fix table text_as_html issues if requested
        if fix_tables:
            from .conversion_core import fix_table_text_as_html
            json_data = fix_table_text_as_html(json_data)

        return json_data

    except Exception as e:
        logger.exception("Error converting JSON to elements")
        raise HTTPException(
            status_code=500,
            detail=f"Element conversion failed: {str(e)}"
        )


async def convert_file_with_unstructured_io(
    client: "httpx.AsyncClient",
    service_url: str,
    file_content: Any,
    filename: str,
    content_type: str,
    output_format: str,
    fix_tables: bool = True
) -> str:
    """
    Centralized function to convert a file using unstructured-io service.

    This function handles the complete flow:
    1. Call unstructured-io service with the file
    2. Get JSON response
    3. Convert to requested output format

    Args:
        client: HTTP client for making requests
        service_url: URL of the unstructured-io service
        file_content: Raw file content bytes
        filename: Original filename
        content_type: MIME type of the file
        output_format: Desired output format ("md", "txt", "html")
        fix_tables: Whether to apply table fixes (default: True)

    Returns:
        Content string in the requested format

    Raises:
        HTTPException: If conversion fails
    """
    try:
        # Prepare request to unstructured-io service
        files = {"files": (filename, file_content, content_type)}
        data = {}

        request = client.build_request(
            "POST",
            f"{service_url}/general/v0/general",
            files=files,
            data=data
        )
        response = await client.send(request, stream=True)

        if response.status_code != 200:
            error_content = await read_response_bounded(response, MAX_ERROR_BYTES)
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Unstructured-IO service error: {error_content.decode('utf-8', errors='replace')}"
            )

        # Parse JSON response
        json_data = json.loads(await read_response_bounded(response))

        # Convert to requested format
        return process_unstructured_json_to_content(json_data, output_format, fix_tables)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in unstructured-io conversion to {output_format}")
        raise HTTPException(
            status_code=500,
            detail=f"Unstructured-IO conversion failed: {str(e)}"
        )

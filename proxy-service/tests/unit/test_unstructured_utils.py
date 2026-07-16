"""Focused tests for dependency-free Unstructured JSON formatting."""

import pytest
from fastapi import HTTPException

from convert.utils.unstructured_utils import process_unstructured_json_to_content


def test_text_and_markdown_formatting_preserve_element_semantics():
    elements = [
        {"type": "Title", "text": "Heading", "metadata": {}},
        {"type": "NarrativeText", "text": "First paragraph", "metadata": {}},
        {"type": "NarrativeText", "text": "", "metadata": {}},
        {"type": "NarrativeText", "text": None, "metadata": {}},
    ]

    assert process_unstructured_json_to_content(elements, "txt", fix_tables=False) == (
        "Heading\nFirst paragraph"
    )
    assert process_unstructured_json_to_content(elements, "md", fix_tables=False) == (
        "# Heading\nFirst paragraph\n"
    )


def test_html_escapes_text_and_removes_executable_table_markup():
    elements = [
        {"type": "NarrativeText", "text": "<img src=x onerror=alert(1)>", "metadata": {}},
        {
            "type": "Table",
            "text": "safe unsafe",
            "metadata": {
                "text_as_html": (
                    '<table onclick="alert(1)"><tr><td colspan="2">safe'
                    "<script>alert(1)</script></td></tr></table>"
                )
            },
        },
    ]

    result = process_unstructured_json_to_content(elements, "html", fix_tables=False)

    assert "&lt;img src=x onerror=alert(1)&gt;" in result
    assert "<script" not in result
    assert "alert(1)</script>" not in result
    assert "onclick" not in result
    assert 'colspan="2"' in result


def test_markdown_preserves_sanitized_html_table_structure():
    elements = [
        {
            "type": "Table",
            "text": "A B",
            "metadata": {
                "text_as_html": "<table><thead><tr><th>A</th><th>B</th></tr></thead></table>"
            },
        }
    ]

    result = process_unstructured_json_to_content(elements, "md", fix_tables=False)

    assert "<table>" in result
    assert "<thead>" in result
    assert "<th>A</th>" in result


def test_unsupported_format_remains_a_client_error():
    with pytest.raises(HTTPException) as exc_info:
        process_unstructured_json_to_content([], "pdf", fix_tables=False)

    assert exc_info.value.status_code == 400

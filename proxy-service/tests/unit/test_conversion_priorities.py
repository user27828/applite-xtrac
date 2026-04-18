"""Unit tests for conversion priority ordering."""

from convert.config import ConversionService
from convert.utils.conversion_lookup import get_conversion_methods


def test_html_docx_prefers_html4docx_before_other_backends():
    """HTML to DOCX should prefer html4docx to preserve contact/header blocks."""
    methods = get_conversion_methods("html", "docx")

    assert methods[0] == (
        ConversionService.HTML4DOCX,
        "HTML to DOCX using html4docx",
    )
    assert methods[1] == (ConversionService.PANDOC, "HTML to Word")
    assert methods[2] == (ConversionService.LIBREOFFICE, "HTML to Word")
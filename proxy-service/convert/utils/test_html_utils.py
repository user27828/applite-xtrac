"""
Tests for HTML processing utilities.
"""

import pytest
import sys
import os

# Add the convert module to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from convert.utils.html_utils import (
    detect_html_structure,
    is_full_html_document,
    extract_html_body_content,
    wrap_html_content,
    process_html_content,
    normalize_html_content,
    validate_html_content
)


class TestHTMLUtils:
    """Test cases for HTML utility functions."""

    def test_detect_html_structure_full_document(self):
        """Test detection of full HTML document structure."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body><p>Hello world</p></body>
        </html>
        """
        has_html, has_head, has_body = detect_html_structure(html)
        assert has_html is True
        assert has_head is True
        assert has_body is True

    def test_detect_html_structure_partial_document(self):
        """Test detection of partial HTML document structure."""
        html = "<body><p>Hello world</p></body>"
        has_html, has_head, has_body = detect_html_structure(html)
        assert has_html is False
        assert has_head is False
        assert has_body is True

    def test_detect_html_structure_no_structure(self):
        """Test detection of HTML without document structure."""
        html = "<p>Hello world</p><div>Content</div>"
        has_html, has_head, has_body = detect_html_structure(html)
        assert has_html is False
        assert has_head is False
        assert has_body is False

    def test_is_full_html_document_true(self):
        """Test identification of full HTML documents."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body><p>Hello world</p></body>
        </html>
        """
        assert is_full_html_document(html) is True

    def test_is_full_html_document_false(self):
        """Test identification of non-full HTML documents."""
        html = "<p>Hello world</p>"
        assert is_full_html_document(html) is False

    def test_extract_html_body_content_with_body(self):
        """Test extraction of content from body tag."""
        html = """
        <!DOCTYPE html>
        <html>
        <body><p>Hello</p><div>World</div></body>
        </html>
        """
        content = extract_html_body_content(html)
        assert "<p>Hello</p><div>World</div>" in content

    def test_extract_html_body_content_without_body(self):
        """Test extraction when no body tag exists."""
        html = "<p>Hello world</p>"
        content = extract_html_body_content(html)
        assert content == html

    def test_wrap_html_content(self):
        """Test wrapping content in HTML structure."""
        content = "<p>Hello world</p>"
        wrapped = wrap_html_content(content, "Test Page")

        assert "<!DOCTYPE html>" in wrapped
        assert "<html" in wrapped
        assert "<head>" in wrapped
        assert "<body>" in wrapped
        assert "<title>Test Page</title>" in wrapped
        assert content in wrapped

    def test_process_html_content_wrap_true_full_document(self):
        """Test processing with wrap=True on full document."""
        html = """
        <!DOCTYPE html>
        <html>
        <body><p>Hello</p></body>
        </html>
        """
        result = process_html_content(html, html_body_wrap=True)
        assert result == html  # Should return unchanged

    def test_process_html_content_wrap_true_partial_document(self):
        """Test processing with wrap=True on partial document."""
        html = "<p>Hello world</p>"
        result = process_html_content(html, html_body_wrap=True)

        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "<body>" in result
        assert html in result

    def test_process_html_content_wrap_false_full_document(self):
        """Test processing with wrap=False on full document."""
        html = """
        <!DOCTYPE html>
        <html>
        <body><p>Hello</p><div>World</div></body>
        </html>
        """
        result = process_html_content(html, html_body_wrap=False)
        assert "<p>Hello</p><div>World</div>" in result
        assert "<!DOCTYPE html>" not in result
        assert "<html" not in result

    def test_process_html_content_wrap_false_partial_document(self):
        """Test processing with wrap=False on partial document."""
        html = "<p>Hello world</p>"
        result = process_html_content(html, html_body_wrap=False)
        assert result == html  # Should return unchanged

    def test_normalize_html_content(self):
        """Test HTML content normalization."""
        html = "<p>Hello</p><div>World</div>"
        normalized = normalize_html_content(html)
        # Should be properly formatted
        assert normalized is not None
        assert len(normalized) > 0

    def test_validate_html_content_valid(self):
        """Test validation of valid HTML."""
        html = "<p>Hello world</p>"
        is_valid, error = validate_html_content(html)
        assert is_valid is True
        assert error is None

    def test_validate_html_content_invalid(self):
        """Test validation of invalid HTML."""
        html = ""
        is_valid, error = validate_html_content(html)
        assert is_valid is False
        assert error is not None

    def test_process_html_content_empty_input(self):
        """Test processing of empty input."""
        result = process_html_content("", html_body_wrap=True)
        assert "<!DOCTYPE html>" in result

        result = process_html_content("", html_body_wrap=False)
        assert result == ""

    def test_process_html_content_none_input(self):
        """Test processing of None input."""
        result = process_html_content(None, html_body_wrap=True)
        assert "<!DOCTYPE html>" in result

        result = process_html_content(None, html_body_wrap=False)
        assert result == ""

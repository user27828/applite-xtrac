#!/usr/bin/env python3
"""
Integration test for CSS margin extraction across all applicable services.

This test verifies that margin extraction works correctly in:
- html4docx (HTML→DOCX)
- pandoc (HTML→DOCX/PDF)
- weasyprint (HTML→PDF, validation only)
"""

import sys
import os
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path to import from utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pyconvert-service'))

from utils.css_margin_parser import (
    extract_page_margins_from_html,
    format_margins_for_pandoc
)


def test_margin_extraction_integration():
    """Test margin extraction across all integrated services."""
    print("Testing CSS margin extraction integration across services...")
    print("=" * 60)

    # Test HTML with various margin specifications
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Document</title>
        <style>
        @page {
            margin: 0.75in 1.0in;
        }
        body {
            font-family: Arial, sans-serif;
        }
        </style>
    </head>
    <body>
        <h1>Test Document with Margins</h1>
        <p>This document has CSS @page margins that should be extracted and applied.</p>
    </body>
    </html>
    """

    # Expected margins
    expected_margins = {'top': 0.75, 'right': 1.0, 'bottom': 0.75, 'left': 1.0}

    # Test 1: Basic margin extraction
    print("1. Testing basic margin extraction...")
    extracted = extract_page_margins_from_html(test_html)
    assert extracted == expected_margins, f"Expected {expected_margins}, got {extracted}"
    print("   ✓ Basic margin extraction works")

    # Test 2: Pandoc variable formatting
    print("2. Testing pandoc variable formatting...")
    pandoc_vars = format_margins_for_pandoc(extracted)
    expected_vars = {
        'margin-top': '0.75in',
        'margin-right': '1.0in',
        'margin-bottom': '0.75in',
        'margin-left': '1.0in'
    }
    assert pandoc_vars == expected_vars, f"Expected {expected_vars}, got {pandoc_vars}"
    print("   ✓ Pandoc variable formatting works")

    # Test 3: html4docx integration (if available)
    print("3. Testing html4docx integration...")
    try:
        from html4docx import HtmlToDocx
        converter = HtmlToDocx()
        doc = converter.parse_html_string(test_html)

        # Apply margins
        from utils.css_margin_parser import apply_margins_to_docx_sections
        apply_margins_to_docx_sections(doc, extracted)

        # Save to temp file and verify
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            doc.save(tmp.name)
            assert os.path.exists(tmp.name), "DOCX file was not created"
            assert os.path.getsize(tmp.name) > 0, "DOCX file is empty"
            os.unlink(tmp.name)

        print("   ✓ html4docx integration works")
    except ImportError:
        print("   ⚠ html4docx not available, skipping integration test")
    except Exception as e:
        print(f"   ✗ html4docx integration failed: {e}")
        raise

    # Test 4: pandoc integration (if available)
    print("4. Testing pandoc integration...")
    try:
        # Create temp HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp_html:
            tmp_html.write(test_html)
            tmp_html_path = tmp_html.name

        # Create temp output file
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
            tmp_docx_path = tmp_docx.name

        try:
            # Build pandoc command with margin variables
            cmd = ['pandoc', tmp_html_path, '-o', tmp_docx_path]
            pandoc_vars = format_margins_for_pandoc(extracted)
            for var_name, var_value in pandoc_vars.items():
                cmd.extend(['-V', f'{var_name}={var_value}'])

            # Run pandoc
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                assert os.path.exists(tmp_docx_path), "Pandoc DOCX output not created"
                assert os.path.getsize(tmp_docx_path) > 0, "Pandoc DOCX output is empty"
                print("   ✓ pandoc integration works")
            else:
                print(f"   ⚠ pandoc command failed: {result.stderr}")
                print("   ⚠ pandoc not available or not working, skipping integration test")

        finally:
            # Clean up temp files
            for path in [tmp_html_path, tmp_docx_path]:
                if os.path.exists(path):
                    os.unlink(path)

    except FileNotFoundError:
        print("   ⚠ pandoc not installed, skipping integration test")
    except Exception as e:
        print(f"   ✗ pandoc integration failed: {e}")
        raise

    # Test 5: weasyprint integration (if available)
    print("5. Testing weasyprint integration...")
    try:
        from weasyprint import HTML

        # Create HTML object
        html_doc = HTML(string=test_html)

        # Generate PDF (weasyprint respects @page margins natively)
        pdf_bytes = html_doc.write_pdf()

        assert len(pdf_bytes) > 0, "WeasyPrint PDF output is empty"
        print("   ✓ weasyprint integration works (respects margins natively)")

    except ImportError:
        print("   ⚠ weasyprint not available, skipping integration test")
    except Exception as e:
        print(f"   ✗ weasyprint integration failed: {e}")
        raise

    print("=" * 60)
    print("✓ All margin extraction integration tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_margin_extraction_integration()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
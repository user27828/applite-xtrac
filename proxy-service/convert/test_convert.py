#!/usr/bin/env python3
"""
Test script for the /convert endpoints.

This script provides examples of how to test the conversion endpoints
and validates that they are working correctly.
"""

import requests
import os
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8369"
TEST_FILES_DIR = Path(__file__).parent / "test_files"

# Create test files directory if it doesn't exist
TEST_FILES_DIR.mkdir(exist_ok=True)

def create_test_files():
    """Create some basic test files for testing conversions."""

    # Create a simple Markdown test file
    md_content = """# Test Document

This is a test document for conversion testing.

## Features

- Markdown formatting
- Simple text content
- Basic structure

## Usage

Use this file to test markdown to PDF conversion.
"""

    with open(TEST_FILES_DIR / "test.md", "w") as f:
        f.write(md_content)

    # Create a simple HTML test file
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        h2 { color: #666; }
    </style>
</head>
<body>
    <h1>Test HTML Document</h1>
    <p>This is a test HTML document for conversion testing.</p>
    <h2>Features</h2>
    <ul>
        <li>HTML formatting</li>
        <li>CSS styling</li>
        <li>Basic structure</li>
    </ul>
</body>
</html>"""

    with open(TEST_FILES_DIR / "test.html", "w") as f:
        f.write(html_content)

    # Create a simple text file
    txt_content = """Test Text Document

This is a simple text file for testing text to PDF conversion.

Features:
- Plain text format
- Simple content
- No formatting

Use this for basic conversion testing.
"""

    with open(TEST_FILES_DIR / "test.txt", "w") as f:
        f.write(txt_content)

    print(f"Created test files in {TEST_FILES_DIR}")

def test_endpoint(endpoint, input_file, output_file=None, description=""):
    """Test a specific conversion endpoint."""
    if not os.path.exists(input_file):
        print(f"❌ Input file {input_file} does not exist")
        return False

    url = f"{BASE_URL}{endpoint}"
    print(f"\n🔄 Testing {endpoint}")
    if description:
        print(f"   {description}")

    try:
        with open(input_file, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, timeout=60)

        if response.status_code == 200:
            if output_file:
                with open(output_file, "wb") as f:
                    f.write(response.content)
                print(f"✅ Success! Saved to {output_file}")
            else:
                print(f"✅ Success! Response size: {len(response.content)} bytes")
            return True
        else:
            print(f"❌ Failed with status {response.status_code}: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_supported_conversions():
    """Test the supported conversions endpoint."""
    print("\n🔍 Testing /convert/supported")
    try:
        response = requests.get(f"{BASE_URL}/convert/supported")
        if response.status_code == 200:
            data = response.json()
            print("✅ Supported conversions retrieved")
            print(f"   Found {len(data.get('supported_conversions', {}))} input formats")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_tests():
    """Run all conversion tests."""
    print("🚀 Starting conversion endpoint tests")
    print(f"Base URL: {BASE_URL}")

    # Create test files
    create_test_files()

    # Test supported conversions
    test_supported_conversions()

    # Test markdown conversions
    test_endpoint(
        "/convert/md-pdf",
        TEST_FILES_DIR / "test.md",
        TEST_FILES_DIR / "test_output.pdf",
        "Convert Markdown to PDF"
    )

    test_endpoint(
        "/convert/md-docx",
        TEST_FILES_DIR / "test.md",
        TEST_FILES_DIR / "test_output.docx",
        "Convert Markdown to DOCX"
    )

    # Test HTML conversions
    test_endpoint(
        "/convert/html-pdf",
        TEST_FILES_DIR / "test.html",
        TEST_FILES_DIR / "test_html_output.pdf",
        "Convert HTML to PDF"
    )

    test_endpoint(
        "/convert/html-md",
        TEST_FILES_DIR / "test.html",
        TEST_FILES_DIR / "test_html_output.md",
        "Convert HTML to Markdown"
    )

    # Test text conversions
    test_endpoint(
        "/convert/txt-pdf",
        TEST_FILES_DIR / "test.txt",
        TEST_FILES_DIR / "test_txt_output.pdf",
        "Convert Text to PDF"
    )

    test_endpoint(
        "/convert/txt-docx",
        TEST_FILES_DIR / "test.txt",
        TEST_FILES_DIR / "test_txt_output.docx",
        "Convert Text to DOCX"
    )

    print("\n✨ Test run complete!")
    print(f"Check output files in {TEST_FILES_DIR}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python test_convert.py")
        print("This script tests the /convert endpoints with sample files.")
        sys.exit(0)

    run_tests()

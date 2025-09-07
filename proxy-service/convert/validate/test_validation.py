"""
Test script for file validation functionality.

This script demonstrates how to use the file validation system
to validate various document formats.
"""

import os
import sys
from pathlib import Path

# Add the proxy-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from convert.validate import validate_file, ValidationError

def test_validation():
    """Test file validation for all supported formats."""

    # Base path for test files
    base_path = Path(__file__).parent.parent.parent / "tests" / "fixtures"

    test_cases = [
        ("sample.html", "html", {}),  # Test default behavior (no options)
        ("sample.html", "html", {"full": False}),
        ("sample.html", "html", {"full": True}),
        ("sample.pdf", "pdf", {}),
        ("sample.docx", "docx", {}),
        ("sample.md", "md", {}),
        ("sample.txt", "txt", {}),
        ("sample.tex", "tex", {}),
        ("sample.xlsx", "xlsx", {}),
        ("sample.pptx", "pptx", {}),
        ("sample.odt", "odt", {}),
        ("sample.ods", "ods", {}),
        ("sample.odp", "odp", {}),
    ]

    print("Testing File Validation System")
    print("=" * 40)

    for filename, format_type, options in test_cases:
        file_path = base_path / filename

        if not file_path.exists():
            print(f"❌ {format_type.upper()}: File not found - {file_path}")
            continue

        try:
            result = validate_file(str(file_path), format_type, **options)
            options_str = f" ({options})" if options else ""
            print(f"✅ {format_type.upper()}{options_str}: Validation passed")
        except ValidationError as e:
            print(f"❌ {format_type.upper()}: Validation failed - {e}")
        except Exception as e:
            print(f"❌ {format_type.upper()}: Unexpected error - {e}")

    print("\nTesting edge cases:")
    print("-" * 20)

    # Test non-existent file
    try:
        validate_file("/nonexistent/file.txt", "txt")
        print("❌ Non-existent file: Should have failed")
    except ValidationError:
        print("✅ Non-existent file: Correctly rejected")

    # Test empty format
    try:
        validate_file(str(base_path / "sample.txt"), "")
        print("❌ Empty format: Should have failed")
    except ValueError:
        print("✅ Empty format: Correctly rejected")

    # Test unsupported format
    try:
        validate_file(str(base_path / "sample.txt"), "unsupported")
        print("❌ Unsupported format: Should have failed")
    except ValueError:
        print("✅ Unsupported format: Correctly rejected")

if __name__ == "__main__":
    test_validation()

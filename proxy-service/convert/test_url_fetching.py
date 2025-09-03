#!/usr/bin/env python3
"""
Test script for URL fetching functionality.

This script demonstrates the URL fetching capabilities and can be used
for testing the integration.
"""

import asyncio
import sys
import os

# Add the convert module to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from convert.url_fetcher import (
    fetch_url_content,
    fetch_url_to_temp_file,
    detect_content_format,
    URLFetchError
)
from convert.url_helpers import (
    prepare_url_for_conversion,
    validate_and_prepare_url_conversion
)


async def test_basic_url_fetch():
    """Test basic URL fetching functionality."""
    print("=== Testing Basic URL Fetch ===")

    test_urls = [
        "https://httpbin.org/html",  # HTML content
        "https://httpbin.org/json",  # JSON content
    ]

    for url in test_urls:
        try:
            print(f"\nFetching: {url}")
            result = await fetch_url_content(url, timeout=10)

            print(f"Status: {result['status']}")
            print(f"Content-Type: {result['content_type']}")
            print(f"Content Length: {len(result['content'])} bytes")
            print(f"Final URL: {result['final_url']}")

            # Detect format
            detected_format = detect_content_format(
                result['content'],
                result['content_type'],
                url
            )
            print(f"Detected Format: {detected_format}")

        except URLFetchError as e:
            print(f"Fetch failed: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


async def test_temp_file_creation():
    """Test fetching URL to temporary file."""
    print("\n=== Testing Temp File Creation ===")

    url = "https://httpbin.org/html"
    try:
        print(f"Fetching to temp file: {url}")
        temp_path, metadata = await fetch_url_to_temp_file(url, timeout=10)

        print(f"Temp file created: {temp_path}")
        print(f"File exists: {os.path.exists(temp_path)}")
        print(f"File size: {os.path.getsize(temp_path)} bytes")
        print(f"Metadata: {metadata}")

        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print("Temp file cleaned up")

    except Exception as e:
        print(f"Temp file test failed: {e}")


async def test_conversion_preparation():
    """Test URL preparation for conversion."""
    print("\n=== Testing Conversion Preparation ===")

    test_cases = [
        ("https://httpbin.org/html", "unstructured-io", "html"),
        ("https://httpbin.org/html", "gotenberg", "html"),
        ("https://httpbin.org/html", "pandoc", "html"),
    ]

    for url, service, input_format in test_cases:
        try:
            print(f"\nTesting {service} with {url}")
            file_wrapper, metadata = await prepare_url_for_conversion(
                url, service, input_format, timeout=10
            )

            print(f"Fetch required: {metadata['fetch_required']}")
            if file_wrapper:
                print(f"Temp file: {metadata.get('temp_file_path')}")
                print(f"Detected format: {metadata.get('detected_format')}")
                await file_wrapper.close()

                # Clean up temp file
                temp_path = metadata.get('temp_file_path')
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                    print("Temp file cleaned up")

        except Exception as e:
            print(f"Conversion preparation failed: {e}")


async def test_validation():
    """Test URL validation."""
    print("\n=== Testing URL Validation ===")

    test_urls = [
        ("https://httpbin.org/html", True),  # Valid
        ("http://httpbin.org/html", True),   # Valid HTTP
        ("ftp://example.com", False),       # Invalid scheme
        ("not-a-url", False),               # Invalid format
        ("", False),                        # Empty
    ]

    for url, should_be_valid in test_urls:
        try:
            result = await validate_and_prepare_url_conversion(
                url, "unstructured-io", "html", timeout=5
            )
            is_valid = result[0] is not None or not result[1].get('fetch_required', True)
            status = "✓" if is_valid == should_be_valid else "✗"
            print(f"{status} {url} -> Valid: {is_valid} (Expected: {should_be_valid})")

            # Clean up if temp file was created
            metadata = result[1]
            temp_path = metadata.get('temp_file_path')
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception as e:
            is_valid = False
            status = "✓" if is_valid == should_be_valid else "✗"
            print(f"{status} {url} -> Valid: {is_valid} (Expected: {should_be_valid}) - {e}")


async def main():
    """Run all tests."""
    print("URL Fetching Test Suite")
    print("=" * 50)

    try:
        await test_basic_url_fetch()
        await test_temp_file_creation()
        await test_conversion_preparation()
        await test_validation()

        print("\n" + "=" * 50)
        print("All tests completed!")

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest suite failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

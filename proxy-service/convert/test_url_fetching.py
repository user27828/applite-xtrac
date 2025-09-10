#!/usr/bin/env python3
"""
Test script for URL fetching functionality.

This script demonstrates the URL fetching capabilities and can be used
for testing the integration.
"""

import asyncio
import sys
import os
import pytest

# Add the convert module to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# from convert.utils.url_fetcher import (
#     fetch_url_content,
#     fetch_url_to_temp_file,
#     detect_content_format,
#     URLFetchError
# )
from convert.utils.url_conversion_manager import URLConversionManager


@pytest.mark.asyncio
async def test_basic_url_fetch():
    """Test basic URL fetching functionality."""
    print("=== Testing Basic URL Fetch ===")

    test_urls = [
        "https://httpbin.org/html",  # HTML content
        "https://httpbin.org/json",  # JSON content
    ]

    url_manager = URLConversionManager()
    
    for url in test_urls:
        try:
            print(f"\nFetching: {url}")
            conversion_input = await url_manager.process_url_conversion(url, "html")
            
            print(f"Status: {conversion_input.metadata.get('status', 'Unknown')}")
            print(f"Content-Type: {conversion_input.metadata.get('content_type', 'Unknown')}")
            print(f"Content Length: {conversion_input.metadata.get('content_length', 'Unknown')} bytes")
            print(f"Final URL: {conversion_input.metadata.get('final_url', url)}")
            print(f"Detected Format: {conversion_input.metadata.get('detected_format', 'Unknown')}")
            
            # Clean up
            await conversion_input.cleanup()

        except Exception as e:
            print(f"Fetch failed: {e}")


@pytest.mark.asyncio
async def test_temp_file_creation():
    """Test fetching URL to temporary file."""
    print("\n=== Testing Temp File Creation ===")

    url = "https://httpbin.org/html"
    url_manager = URLConversionManager()
    
    try:
        print(f"Fetching to temp file: {url}")
        conversion_input = await url_manager.process_url_conversion(url, "pdf")  # Use PDF to force temp file creation
        
        if hasattr(conversion_input, 'temp_file_wrapper') and conversion_input.temp_file_wrapper:
            temp_path = conversion_input.temp_file_wrapper.file_path
            print(f"Temp file created: {temp_path}")
            print(f"File exists: {os.path.exists(temp_path)}")
            print(f"File size: {os.path.getsize(temp_path)} bytes")
            print(f"Metadata: {conversion_input.metadata}")
        else:
            print("No temp file was created (direct URL used)")
            print(f"Direct URL: {conversion_input.url}")
            print(f"Metadata: {conversion_input.metadata}")

        # Clean up
        await conversion_input.cleanup()
        print("Temp file cleaned up")

    except Exception as e:
        print(f"Temp file test failed: {e}")


@pytest.mark.asyncio
async def test_conversion_preparation():
    """Test URL preparation for conversion."""
    print("\n=== Testing Conversion Preparation ===")

    test_cases = [
        ("https://httpbin.org/html", "html"),
        ("https://httpbin.org/html", "pdf"),
        ("https://httpbin.org/html", "json"),
    ]

    url_manager = URLConversionManager()
    
    for url, output_format in test_cases:
        try:
            print(f"\nTesting URL conversion for {url} -> {output_format}")
            conversion_input = await url_manager.process_url_conversion(url, output_format)

            print(f"Detected format: {conversion_input.metadata['detected_format']}")
            print(f"Conversion path: {conversion_input.metadata['conversion_path']}")
            if hasattr(conversion_input, 'temp_file_wrapper'):
                print(f"Temp file created: {conversion_input.metadata.get('temp_file_path')}")
            
            # Clean up
            await conversion_input.cleanup()
            print("✓ Conversion preparation successful")
            
        except Exception as e:
            print(f"✗ Error: {e}")


@pytest.mark.asyncio
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

    url_manager = URLConversionManager()
    
    for url, should_be_valid in test_urls:
        try:
            conversion_input = await url_manager.process_url_conversion(url, "html")
            is_valid = True  # If no exception, it's valid
            status = "✓" if is_valid == should_be_valid else "✗"
            print(f"{status} {url} -> Valid: {is_valid} (Expected: {should_be_valid})")
            
            # Clean up
            await conversion_input.cleanup()

        except Exception as e:
            is_valid = False
            status = "✓" if is_valid == should_be_valid else "✗"
            print(f"{status} {url} -> Valid: {is_valid} (Expected: {should_be_valid}) - Error: {e}")


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

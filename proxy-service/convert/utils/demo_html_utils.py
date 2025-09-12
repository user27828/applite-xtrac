#!/usr/bin/env python3
"""
Demonstration of HTML processing utility functions.

This script shows how to use the process_html_content function with the htmlBodyWrap parameter.
"""

import sys
import os

# Add the parent directories to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from utils.html_utils import process_html_content


def demo_html_processing():
    """Demonstrate HTML processing with different scenarios."""

    print("=== HTML Processing Utility Demo ===\n")

    # Example 1: Full HTML document with htmlBodyWrap=False (extract content)
    full_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Sample Document</title>
    </head>
    <body>
        <h1>Hello World</h1>
        <p>This is a sample paragraph.</p>
        <div class="content">
            <span>Some content here</span>
        </div>
    </body>
    </html>
    """

    print("1. Full HTML Document → Extract Body Content (htmlBodyWrap=False)")
    print("Input:")
    print(full_html.strip())
    print("\nOutput:")
    result = process_html_content(full_html, html_body_wrap=False)
    print(result)
    print("-" * 60)

    # Example 2: Full HTML document with htmlBodyWrap=True (return as-is)
    print("\n2. Full HTML Document → Keep Wrapped (htmlBodyWrap=True)")
    print("Input: (same as above)")
    print("Output: (unchanged)")
    result = process_html_content(full_html, html_body_wrap=True)
    print("(Full HTML document returned unchanged)")
    print("-" * 60)

    # Example 3: HTML snippet with htmlBodyWrap=False (return as-is)
    html_snippet = '<h1>Hello World</h1><p>This is a paragraph.</p><div>Content</div>'

    print("\n3. HTML Snippet → Keep Unwrapped (htmlBodyWrap=False)")
    print("Input:")
    print(html_snippet)
    print("\nOutput:")
    result = process_html_content(html_snippet, html_body_wrap=False)
    print(result)
    print("-" * 60)

    # Example 4: HTML snippet with htmlBodyWrap=True (wrap it)
    print("\n4. HTML Snippet → Wrap in HTML Structure (htmlBodyWrap=True)")
    print("Input:")
    print(html_snippet)
    print("\nOutput:")
    result = process_html_content(html_snippet, html_body_wrap=True, title="Wrapped Document")
    print(result)
    print("-" * 60)

    # Example 5: Empty content
    print("\n5. Empty Content → Handle Gracefully")
    print("Input: ''")
    print("\nOutput with htmlBodyWrap=False:")
    result = process_html_content("", html_body_wrap=False)
    print(repr(result))

    print("\nOutput with htmlBodyWrap=True:")
    result = process_html_content("", html_body_wrap=True, title="Empty Document")
    print(result)


if __name__ == "__main__":
    demo_html_processing()

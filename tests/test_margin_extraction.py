#!/usr/bin/env python3
"""
Test suite for CSS margin extraction and conversion utilities.

This test validates the extract_page_margins_from_html() and
parse_css_length_to_inches() functions used for converting HTML/CSS
margin specifications to DOCX document margins.
"""

import sys
import os

# Add parent directory to path to import from utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pyconvert-service'))

from utils.css_margin_parser import (
    extract_page_margins_from_html,
    parse_css_length_to_inches,
    margins_to_points,
    margins_to_cm,
    margins_to_mm,
    format_margins_for_pandoc
)


def test_css_length_conversion():
    """Test CSS length to inches conversion."""
    print("Testing CSS length conversion...")
    
    tests = [
        ('0.75in', 0.75),
        ('1in', 1.0),
        ('2.54cm', 1.0),
        ('25.4mm', 1.0),
        ('72pt', 1.0),
        ('96px', 1.0),
        ('6pc', 1.0),
    ]
    
    for css_value, expected in tests:
        result = parse_css_length_to_inches(css_value)
        assert abs(result - expected) < 0.01, f"Failed: {css_value} = {result}, expected {expected}"
        print(f"  ✓ {css_value} = {result:.2f}in")
    
    print("CSS length conversion tests passed!\n")


def test_margin_extraction():
    """Test @page margin extraction."""
    print("Testing @page margin extraction...")
    
    # Test 1: Single margin value (dense resume template)
    html1 = """
    <style>
    @page {
        size: Letter;
        margin: 0.5in 0.5in 0.5in 0.5in;
    }
    </style>
    """
    margins1 = extract_page_margins_from_html(html1)
    assert margins1 == {'top': 0.5, 'right': 0.5, 'bottom': 0.5, 'left': 0.5}
    print(f"  ✓ Dense template (4-value): {margins1}")
    
    # Test 2: Standard template
    html2 = """
    <style>
    @page {
        size: Letter;
        margin: 0.75in 0.75in 0.75in 0.75in;
    }
    </style>
    """
    margins2 = extract_page_margins_from_html(html2)
    assert margins2 == {'top': 0.75, 'right': 0.75, 'bottom': 0.75, 'left': 0.75}
    print(f"  ✓ Standard template (4-value): {margins2}")
    
    # Test 3: Shorthand single value
    html3 = """
    <style>
    @page {
        margin: 1in;
    }
    </style>
    """
    margins3 = extract_page_margins_from_html(html3)
    assert margins3 == {'top': 1.0, 'right': 1.0, 'bottom': 1.0, 'left': 1.0}
    print(f"  ✓ Shorthand single: {margins3}")
    
    # Test 4: Two values (vertical/horizontal)
    html4 = """
    <style>
    @page {
        margin: 0.5in 1in;
    }
    </style>
    """
    margins4 = extract_page_margins_from_html(html4)
    assert margins4 == {'top': 0.5, 'right': 1.0, 'bottom': 0.5, 'left': 1.0}
    print(f"  ✓ Two values (tb/lr): {margins4}")
    
    # Test 5: Individual properties
    html5 = """
    <style>
    @page {
        margin-top: 0.5in;
        margin-right: 0.75in;
        margin-bottom: 1in;
        margin-left: 0.6in;
    }
    </style>
    """
    margins5 = extract_page_margins_from_html(html5)
    assert margins5 == {'top': 0.5, 'right': 0.75, 'bottom': 1.0, 'left': 0.6}
    print(f"  ✓ Individual properties: {margins5}")
    
    # Test 6: Mixed units
    html6 = """
    <style>
    @page {
        margin: 72pt 2.54cm 25.4mm 96px;
    }
    </style>
    """
    margins6 = extract_page_margins_from_html(html6)
    # All should be approximately 1 inch
    for side, value in margins6.items():
        assert abs(value - 1.0) < 0.01, f"{side} margin conversion failed"
    print(f"  ✓ Mixed units: {margins6}")
    
    # Test 7: No margins (empty result)
    html7 = "<html><body>No margins here</body></html>"
    margins7 = extract_page_margins_from_html(html7)
    assert margins7 == {}
    print(f"  ✓ No margins: {margins7}")
    
    print("@page margin extraction tests passed!\n")


def test_actual_template():
    """Test with actual resume template HTML."""
    print("Testing with actual resume template structure...")
    
    # Simulated base.html template content
    template_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {
                size: Letter;
                margin: {% if is_dense_margin %}0.5in 0.5in 0.5in 0.5in{% else %}0.75in 0.75in 0.75in 0.75in{% endif %};
            }
        </style>
    </head>
    <body>Resume content</body>
    </html>
    """
    
    # Test with dense margins (after template rendering)
    dense_html = template_html.replace(
        '{% if is_dense_margin %}0.5in 0.5in 0.5in 0.5in{% else %}0.75in 0.75in 0.75in 0.75in{% endif %}',
        '0.5in 0.5in 0.5in 0.5in'
    )
    dense_margins = extract_page_margins_from_html(dense_html)
    assert all(v == 0.5 for v in dense_margins.values())
    print(f"  ✓ Dense template rendering: {dense_margins}")
    
    # Test with standard margins
    standard_html = template_html.replace(
        '{% if is_dense_margin %}0.5in 0.5in 0.5in 0.5in{% else %}0.75in 0.75in 0.75in 0.75in{% endif %}',
        '0.75in 0.75in 0.75in 0.75in'
    )
    standard_margins = extract_page_margins_from_html(standard_html)
    assert all(v == 0.75 for v in standard_margins.values())
    print(f"  ✓ Standard template rendering: {standard_margins}")
    
    print("Resume template tests passed!\n")


def test_unit_conversions():
    """Test margin unit conversion utilities."""
    print("Testing unit conversion utilities...")
    
    margins = {'top': 1.0, 'right': 1.0, 'bottom': 1.0, 'left': 1.0}
    
    # Test points conversion
    points = margins_to_points(margins)
    assert all(v == 72.0 for v in points.values()), f"Points conversion failed: {points}"
    print(f"  ✓ margins_to_points: {points}")
    
    # Test cm conversion
    cm = margins_to_cm(margins)
    assert all(abs(v - 2.54) < 0.01 for v in cm.values()), f"CM conversion failed: {cm}"
    print(f"  ✓ margins_to_cm: {cm}")
    
    # Test mm conversion
    mm = margins_to_mm(margins)
    assert all(abs(v - 25.4) < 0.01 for v in mm.values()), f"MM conversion failed: {mm}"
    print(f"  ✓ margins_to_mm: {mm}")
    
    # Test Pandoc format
    pandoc_vars = format_margins_for_pandoc(margins)
    expected = {'margin-top': '1.0in', 'margin-right': '1.0in', 
                'margin-bottom': '1.0in', 'margin-left': '1.0in'}
    assert pandoc_vars == expected, f"Pandoc format failed: {pandoc_vars}"
    print(f"  ✓ format_margins_for_pandoc: {pandoc_vars}")
    
    print("Unit conversion tests passed!\n")


if __name__ == '__main__':
    print("=" * 60)
    print("CSS @page Margin Extraction Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_css_length_conversion()
        test_margin_extraction()
        test_actual_template()
        test_unit_conversions()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

"""
CSS Margin Parser Utility

This module provides utilities for extracting and converting CSS @page margin
specifications from HTML/CSS content. These functions are designed to be
reusable across different document conversion tools.

Functions:
    - parse_css_length_to_inches: Convert CSS length values to inches
    - extract_page_margins_from_html: Extract @page margins from HTML/CSS
    - margins_to_points: Convert margin dict from inches to points
    - margins_to_cm: Convert margin dict from inches to centimeters
    - margins_to_mm: Convert margin dict from inches to millimeters
"""

import re
from typing import Dict, Optional


def parse_css_length_to_inches(css_value: str) -> float:
    """
    Convert CSS length values to inches.
    
    Supports the following units:
    - in, inch: inches (1:1)
    - cm: centimeters (2.54 cm = 1 in)
    - mm: millimeters (25.4 mm = 1 in)
    - pt: points (72 pt = 1 in)
    - pc: picas (6 pc = 1 in)
    - px: pixels (96 px = 1 in, assuming 96 DPI)
    
    Args:
        css_value: CSS length string (e.g., "0.75in", "2.54cm", "72pt")
        
    Returns:
        Float value in inches. Returns 1.0 if parsing fails.
        
    Examples:
        >>> parse_css_length_to_inches("0.75in")
        0.75
        >>> parse_css_length_to_inches("2.54cm")
        1.0
        >>> parse_css_length_to_inches("72pt")
        1.0
    """
    # Remove whitespace
    css_value = css_value.strip()
    
    # Match number and unit
    match = re.match(r'^([\d.]+)\s*([a-z]+)?$', css_value, re.IGNORECASE)
    
    if not match:
        # Default to 1 inch if parsing fails
        return 1.0
    
    value = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) else 'in'
    
    # Conversion factors to inches
    conversions = {
        'in': 1.0,
        'inch': 1.0,
        'cm': 1.0 / 2.54,
        'mm': 1.0 / 25.4,
        'pt': 1.0 / 72.0,
        'pc': 1.0 / 6.0,  # picas
        'px': 1.0 / 96.0,  # Assuming 96 DPI
    }
    
    return value * conversions.get(unit, 1.0)


def extract_page_margins_from_html(html_content: str) -> Dict[str, float]:
    """
    Extract @page margin specifications from HTML/CSS content.
    
    This function parses CSS @page rules and extracts margin values,
    converting them to inches for consistent use across different
    document conversion tools.
    
    Supports:
    - Shorthand margin property:
      * Single value: margin: 0.75in; (all sides)
      * Two values: margin: 0.5in 0.75in; (vertical horizontal)
      * Three values: margin: 0.5in 0.75in 1in; (top horizontal bottom)
      * Four values: margin: 0.5in 0.75in 1in 0.6in; (top right bottom left)
    - Individual margin properties:
      * margin-top, margin-right, margin-bottom, margin-left
    
    Args:
        html_content: HTML string containing CSS @page rules
        
    Returns:
        Dictionary with keys 'top', 'right', 'bottom', 'left' containing
        margin values in inches. Returns empty dict if no margins found.
        
    Examples:
        >>> html = '<style>@page { margin: 0.75in; }</style>'
        >>> extract_page_margins_from_html(html)
        {'top': 0.75, 'right': 0.75, 'bottom': 0.75, 'left': 0.75}
        
        >>> html = '<style>@page { margin: 0.5in 1in; }</style>'
        >>> extract_page_margins_from_html(html)
        {'top': 0.5, 'right': 1.0, 'bottom': 0.5, 'left': 1.0}
    """
    margins = {}
    
    # Pattern to find @page rules
    page_rule_pattern = r'@page\s*\{([^}]+)\}'
    
    # Find all @page rules
    page_rules = re.findall(page_rule_pattern, html_content, re.IGNORECASE | re.DOTALL)
    
    for rule_content in page_rules:
        # Look for margin property (shorthand)
        margin_match = re.search(r'margin\s*:\s*([^;]+);', rule_content, re.IGNORECASE)
        
        if margin_match:
            margin_values = margin_match.group(1).strip().split()
            
            # Parse shorthand margin values based on number of values
            if len(margin_values) == 1:
                # margin: value; (all sides)
                value = parse_css_length_to_inches(margin_values[0])
                margins = {'top': value, 'right': value, 'bottom': value, 'left': value}
            elif len(margin_values) == 2:
                # margin: vertical horizontal;
                tb = parse_css_length_to_inches(margin_values[0])
                lr = parse_css_length_to_inches(margin_values[1])
                margins = {'top': tb, 'right': lr, 'bottom': tb, 'left': lr}
            elif len(margin_values) == 3:
                # margin: top horizontal bottom;
                top = parse_css_length_to_inches(margin_values[0])
                lr = parse_css_length_to_inches(margin_values[1])
                bottom = parse_css_length_to_inches(margin_values[2])
                margins = {'top': top, 'right': lr, 'bottom': bottom, 'left': lr}
            elif len(margin_values) == 4:
                # margin: top right bottom left;
                margins = {
                    'top': parse_css_length_to_inches(margin_values[0]),
                    'right': parse_css_length_to_inches(margin_values[1]),
                    'bottom': parse_css_length_to_inches(margin_values[2]),
                    'left': parse_css_length_to_inches(margin_values[3])
                }
        
        # Look for individual margin properties (these override shorthand)
        for side in ['top', 'right', 'bottom', 'left']:
            individual_match = re.search(
                rf'margin-{side}\s*:\s*([^;]+);',
                rule_content,
                re.IGNORECASE
            )
            if individual_match:
                margins[side] = parse_css_length_to_inches(individual_match.group(1).strip())
    
    return margins


def margins_to_points(margins: Dict[str, float]) -> Dict[str, float]:
    """
    Convert margins dictionary from inches to points.
    
    Useful for PDF libraries and tools that use points (72 points = 1 inch).
    
    Args:
        margins: Dictionary with margin values in inches
        
    Returns:
        Dictionary with margin values in points
        
    Example:
        >>> margins = {'top': 0.75, 'right': 1.0, 'bottom': 0.75, 'left': 1.0}
        >>> margins_to_points(margins)
        {'top': 54.0, 'right': 72.0, 'bottom': 54.0, 'left': 72.0}
    """
    return {k: v * 72.0 for k, v in margins.items()}


def margins_to_cm(margins: Dict[str, float]) -> Dict[str, float]:
    """
    Convert margins dictionary from inches to centimeters.
    
    Args:
        margins: Dictionary with margin values in inches
        
    Returns:
        Dictionary with margin values in centimeters
        
    Example:
        >>> margins = {'top': 1.0, 'right': 1.0, 'bottom': 1.0, 'left': 1.0}
        >>> margins_to_cm(margins)
        {'top': 2.54, 'right': 2.54, 'bottom': 2.54, 'left': 2.54}
    """
    return {k: v * 2.54 for k, v in margins.items()}


def margins_to_mm(margins: Dict[str, float]) -> Dict[str, float]:
    """
    Convert margins dictionary from inches to millimeters.
    
    Args:
        margins: Dictionary with margin values in inches
        
    Returns:
        Dictionary with margin values in millimeters
        
    Example:
        >>> margins = {'top': 1.0, 'right': 1.0, 'bottom': 1.0, 'left': 1.0}
        >>> margins_to_mm(margins)
        {'top': 25.4, 'right': 25.4, 'bottom': 25.4, 'left': 25.4}
    """
    return {k: v * 25.4 for k, v in margins.items()}


def format_margins_for_pandoc(margins: Dict[str, float]) -> Dict[str, str]:
    """
    Format margins dictionary for Pandoc command-line variables.
    
    Args:
        margins: Dictionary with margin values in inches
        
    Returns:
        Dictionary with Pandoc variable names and formatted values
        
    Example:
        >>> margins = {'top': 0.75, 'right': 1.0, 'bottom': 0.75, 'left': 1.0}
        >>> format_margins_for_pandoc(margins)
        {'margin-top': '0.75in', 'margin-right': '1.0in', 'margin-bottom': '0.75in', 'margin-left': '1.0in'}
    """
    return {f'margin-{k}': f'{v}in' for k, v in margins.items()}


def apply_margins_to_docx_sections(docx_document, margins: Dict[str, float]) -> None:
    """
    Apply margins to all sections in a python-docx Document object.
    
    This is a convenience function for applying extracted margins to DOCX documents
    using the python-docx library.
    
    Args:
        docx_document: A python-docx Document object
        margins: Dictionary with margin values in inches
        
    Example:
        >>> from docx import Document
        >>> doc = Document()
        >>> margins = {'top': 0.75, 'right': 1.0, 'bottom': 0.75, 'left': 1.0}
        >>> apply_margins_to_docx_sections(doc, margins)
    """
    from docx.shared import Inches
    
    for section in docx_document.sections:
        if 'top' in margins:
            section.top_margin = Inches(margins['top'])
        if 'bottom' in margins:
            section.bottom_margin = Inches(margins['bottom'])
        if 'left' in margins:
            section.left_margin = Inches(margins['left'])
        if 'right' in margins:
            section.right_margin = Inches(margins['right'])

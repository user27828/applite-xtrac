"""
Conversion lookup utilities for the /convert endpoints.

This module contains utility functions for looking up conversion methods,
supported formats, and service configurations.
"""

from typing import Dict, List, Tuple, Optional
import socket
from ..config import CONVERSION_MATRIX, SERVICE_URL_CONFIGS, ConversionService


def get_service_urls() -> Dict[str, str]:
    """
    Get service URLs with fallback mechanism for Docker vs local development.

    Returns:
        Dictionary mapping service names to their resolved URLs
    """
    urls = {}

    for service, config in SERVICE_URL_CONFIGS.items():
        # Try Docker URL first
        try:
            # Quick DNS resolution test
            socket.gethostbyname(config["docker"].replace("http://", "").split(":")[0])
            urls[service] = config["docker"]
        except socket.gaierror:
            # Fall back to localhost
            urls[service] = config["local"]

    return urls


def get_dynamic_service_urls():
    """Get service URLs with the same logic as the main app"""
    urls = get_service_urls()
    return {
        ConversionService.UNSTRUCTURED_IO: urls.get("unstructured-io"),
        ConversionService.LIBREOFFICE: urls.get("libreoffice"),
        ConversionService.PANDOC: urls.get("pyconvert"),
        ConversionService.GOTENBERG: urls.get("gotenberg"),
        ConversionService.LOCAL: None,
        ConversionService.WEASYPRINT: urls.get("pyconvert"),  # pyconvert
        ConversionService.MAMMOTH: urls.get("pyconvert"),  # pyconvert
        ConversionService.HTML4DOCX: urls.get("pyconvert"),  # pyconvert
        ConversionService.BEAUTIFULSOUP: urls.get("pyconvert"),  # pyconvert
    }


# Use dynamic URLs
DYNAMIC_SERVICE_URLS = get_dynamic_service_urls()


def get_conversion_methods(input_format: str, output_format: str) -> List[Tuple[ConversionService, str]]:
    """
    Get available conversion methods for a given input/output format pair.

    Args:
        input_format: Input file format (e.g., 'docx', 'pdf')
        output_format: Output file format (e.g., 'pdf', 'json')

    Returns:
        List of tuples containing (service, description)
    """
    # Format aliases to handle common variations
    format_aliases = {
        "tex": "latex",  # tex and latex are the same format
        "latex": "latex"
    }
    
    # Normalize input and output formats using aliases
    normalized_input = format_aliases.get(input_format.lower(), input_format.lower())
    normalized_output = output_format.lower()
    
    key = (normalized_input, normalized_output)
    return CONVERSION_MATRIX.get(key, [])


def get_primary_conversion(input_format: str, output_format: str) -> Optional[Tuple[ConversionService, str]]:
    """
    Get the primary (highest quality) conversion method for a format pair.

    Args:
        input_format: Input file format
        output_format: Output file format

    Returns:
        Tuple of (service, description) or None if no conversion available
    """
    methods = get_conversion_methods(input_format, output_format)
    if not methods:
        return None

    # Check if this is a chained conversion (list of lists) or simple conversion (list of tuples)
    first_method = methods[0]
    if isinstance(first_method, list) and len(first_method) == 4:
        # Chained conversion: [service, input, output, description]
        service, _, _, description = first_method
        return (service, description)
    else:
        # Simple conversion: (service, description)
        service, description = first_method
        return (service, description)


def get_all_conversions(input_format: str, output_format: str) -> List[Tuple[ConversionService, str]]:
    """
    Get all available conversion methods for a format pair, in priority order.

    Args:
        input_format: Input file format
        output_format: Output file format

    Returns:
        List of tuples containing (service, description) in priority order
    """
    methods = get_conversion_methods(input_format, output_format)
    if not methods:
        return []

    result = []
    for method in methods:
        # Check if this is a chained conversion (list of lists) or simple conversion (list of tuples)
        if isinstance(method, list) and len(method) == 4:
            # Chained conversion: [service, input, output, description]
            service, _, _, description = method
            result.append((service, description))
        else:
            # Simple conversion: (service, description)
            result.append(method)
    
    return result


def get_supported_conversions() -> Dict[str, List[str]]:
    """
    Get all supported input formats and their possible output formats.

    Returns:
        Dictionary mapping input formats to lists of output formats
    """
    supported = {}
    for (input_fmt, output_fmt), _ in CONVERSION_MATRIX.items():
        if input_fmt not in supported:
            supported[input_fmt] = []
        if output_fmt not in supported[input_fmt]:
            supported[input_fmt].append(output_fmt)

    return supported

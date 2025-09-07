"""
Conversion configuration for the /convert endpoints.

This module defines the conversion pairs and their preferred services based on
quality, reliability, and format support analysis.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum


# Service URL Configuration
# Define service URLs for different environments (Docker vs local development)
SERVICE_URL_CONFIGS = {
    "unstructured-io": {
        "docker": "http://unstructured-io:8000",
        "local": "http://localhost:8000"
    },
    "libreoffice": {
        "docker": "http://libreoffice:2004",
        "local": "http://localhost:2004"
    },
    "pandoc": {
        "docker": "http://pandoc:3000",
        "local": "http://localhost:3030"
    },
    "gotenberg": {
        "docker": "http://gotenberg:3000",
        "local": "http://localhost:3001"
    }
}

class ConversionService(Enum):
    """Available conversion services."""
    UNSTRUCTURED_IO = "unstructured-io"
    LIBREOFFICE = "libreoffice"
    PANDOC = "pandoc"
    GOTENBERG = "gotenberg"
    LOCAL = "local"


class ConversionPriority(Enum):
    """Priority levels for conversion methods."""
    PRIMARY = "primary"      # Best quality/reliability
    SECONDARY = "secondary"  # Good alternative
    TERTIARY = "tertiary"    # Fallback option


# Conversion matrix defining input -> output format mappings with preferred services
CONVERSION_MATRIX = {
    ("doc", "md"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy Word to Markdown (chained: LibreOffice → Pandoc)"),
    ],

    ("docx", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Word to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Word to HTML"),
    ],

    ("docx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Document structure extraction"),
    ],

    ("docx", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Word to Markdown"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Structure extraction only"),
    ],

    ("docx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality office document to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent office format support"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "Limited office format support"),
    ],

    ("docx", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Word to LaTeX"),
    ],

    ("docx", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Word to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "Word to Text"),
    ],

    ("eml", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Email structure extraction"),
    ],

    ("epub", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "E-book structure extraction"),
    ],

    ("epub", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "E-book to Markdown"),
    ],

    ("epub", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "E-book to PDF"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "E-book format support"),
    ],

    ("html", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "HTML to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "HTML to Word"),
    ],

    ("html", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "HTML structure extraction"),
    ],

    ("html", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "HTML to Markdown"),
    ],

    ("html", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-fidelity HTML to PDF with CSS support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Good for simple HTML"),
        (ConversionService.LIBREOFFICE, ConversionPriority.TERTIARY, "Basic HTML support"),
    ],

    ("html", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "HTML to LaTeX"),
    ],

    ("html", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "HTML text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "HTML to Text"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "HTML to Text"),
    ],

    ("latex", "docx"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Word"),
    ],

    ("latex", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to HTML"),
    ],

    ("latex", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "LaTeX structure extraction"),
    ],

    ("latex", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Markdown"),
    ],

    ("latex", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to PDF"),
    ],

    ("latex", "txt"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Text"),
    ],

    ("md", "docx"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to Word"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Via intermediate format"),
    ],

    ("md", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to HTML"),
    ],

    ("md", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Markdown structure extraction"),
    ],

    ("md", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to PDF via LaTeX"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Basic markdown support"),
    ],

    ("md", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to LaTeX"),
    ],

    ("md", "txt"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
    ],

    ("msg", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Outlook message structure extraction"),
    ],

    ("numbers", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Numbers to HTML via LibreOffice"),
    ],

    ("numbers", "json"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Apple Numbers to JSON via local processing"),
    ],

    ("numbers", "md"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Apple Numbers to Markdown via chained conversion"),
    ],

    ("numbers", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Numbers to Text via LibreOffice"),
    ],

    ("numbers", "xlsx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Numbers to Excel via LibreOffice"),
    ],

    ("odp", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument presentation support"),
    ],

    ("odp", "json"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Convert ODP to PPTX first, then extract structure"),
    ],

    ("odp", "md"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Convert ODP to PPTX first, then extract content"),
    ],

    ("odp", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Convert ODP to PPTX first, then extract text"),
    ],

    ("odp", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Convert ODP to PPTX first, then convert to HTML"),
    ],

    ("odp", "pptx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument presentation to PowerPoint"),
    ],

    ("ods", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument spreadsheet to HTML"),
    ],

    ("ods", "md"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "ODS to Markdown via local processing"),
    ],

    ("ods", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument spreadsheet support"),
    ],

    ("ods", "txt"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "ODS to Text via local processing"),
    ],

    ("odt", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "OpenDocument support"),
    ],

    ("odt", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "OpenDocument support"),
    ],

    ("odt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "OpenDocument structure extraction"),
    ],

    ("odt", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "OpenDocument to Markdown"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Structure extraction only"),
    ],

    ("odt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Good OpenDocument support"),
    ],

    ("odt", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "OpenDocument to Text"),
    ],

    ("pages", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to DOCX via LibreOffice")
    ],

    ("pages", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to HTML via LibreOffice")
    ],

    ("pages", "json"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Apple Pages to JSON via chained conversion"),
    ],

    ("pages", "md"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to Markdown (chained: LibreOffice → Pandoc)"),
    ],

    ("pages", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to PDF via LibreOffice"),
    ],

    ("pages", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to TXT via LibreOffice")
    ],

    ("pdf", "docx"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF text extraction to HTML"),
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "HTML to DOCX (chained: PDF → HTML → DOCX)"),
    ],

    ("pdf", "html"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF to HTML structure extraction"),
    ],

    ("pdf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF structure extraction"),
    ],

    ("pdf", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF to text structure"),
    ],

    ("pdf", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "PDF to Text"),
    ],

    ("ppt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy presentation structure extraction"),
    ],

    ("ppt", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy presentation to Markdown"),
    ],

    ("ppt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy presentation format support"),
        (ConversionService.GOTENBERG, ConversionPriority.SECONDARY, "May work via LibreOffice"),
    ],

    ("ppt", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy presentation text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Legacy presentation to Text"),
    ],

    ("ppt", "html"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy presentation to HTML"),
    ],

    ("pptx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Presentation structure extraction"),
    ],

    ("pptx", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Presentation to Markdown"),
    ],

    ("pptx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality presentation to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent presentation support"),
    ],

    ("pptx", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Presentation text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Presentation to Text"),
    ],

    ("pptx", "html"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Presentation to HTML"),
    ],

    ("rtf", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],

    ("rtf", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],

    ("rtf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "RTF structure extraction"),
    ],

    ("rtf", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "RTF to Markdown"),
    ],

    ("rtf", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Good RTF support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],

    ("rtf", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
    ],

    ("tex", "docx"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Word"),
    ],

    ("tex", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to HTML"),
    ],

    ("tex", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "LaTeX structure extraction"),
    ],

    ("tex", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Markdown"),
    ],

    ("tex", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to PDF via Pandoc"),
    ],

    ("tex", "txt"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Text"),
    ],

    ("txt", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Text to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to Word"),
    ],

    ("txt", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Text to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to HTML"),
    ],

    ("txt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Text structure extraction"),
    ],

    ("txt", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Text to Markdown"),
    ],

    ("txt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Simple text to PDF"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to PDF via LaTeX"),
    ],

    ("txt", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Text to LaTeX"),
    ],

    ("url", "html"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "URL to HTML content fetching"),
    ],

    ("url", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL content structure extraction"),
    ],

    ("url", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL to markdown conversion"),
    ],

    ("url", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "URL to PDF conversion with full CSS support"),
    ],

    ("url", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL to text conversion"),
    ],

    ("xls", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy Excel to HTML via LibreOffice"),
    ],

    ("xls", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy Excel structure extraction"),
    ],

    ("xls", "md"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Legacy Excel to Markdown via local processing"),
    ],

    ("xls", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy spreadsheet format support"),
        (ConversionService.GOTENBERG, ConversionPriority.SECONDARY, "May work via LibreOffice"),
    ],

    ("xls", "txt"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Legacy Excel to Text via local processing"),
    ],

    ("xlsx", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Excel to HTML via LibreOffice"),
    ],

    ("xlsx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Spreadsheet structure extraction"),
    ],

    ("xlsx", "md"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Excel to Markdown via local processing"),
    ],

    ("xlsx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality spreadsheet to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent spreadsheet support"),
    ],

    ("xlsx", "txt"): [
        (ConversionService.LOCAL, ConversionPriority.PRIMARY, "Excel to Text via local processing"),
    ],
}


# Pandoc format mappings for extensions to pandoc format names
PANDOC_FORMAT_MAP = {
    # Input formats
    "md": "markdown",
    "tex": "latex",
    "latex": "latex",
    "txt": "markdown",  # Changed from "plain" to "markdown" since Pandoc doesn't recognize "plain"
    "html": "html",
    "docx": "docx",
    "odt": "odt",
    "rtf": "rtf",
    "epub": "epub",
    "json": "json",
    "biblatex": "biblatex",
    "bibtex": "bibtex",
    "commonmark": "commonmark",
    "gfm": "gfm",
    "org": "org",
    "rst": "rst",
    "textile": "textile",
    "vimwiki": "vimwiki",
    "mediawiki": "mediawiki",
    "dokuwiki": "dokuwiki",
    "tikiwiki": "tikiwiki",
    "twiki": "twiki",
    "creole": "creole",
    "jira": "jira",
    "muse": "muse",
    "t2t": "t2t",
    "ipynb": "ipynb",
    "csv": "csv",
    "tsv": "tsv",
    "docbook": "docbook",
    "jats": "jats",
    "man": "man",
    "fb2": "fb2",
    "opml": "opml",
    "ris": "ris",
    "endnotexml": "endnotexml",
    "csljson": "csljson",
    "native": "native",
    # Output formats
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "markdown": "markdown",
    "latex": "latex",
    "plain": "plain",
    "asciidoc": "asciidoc",
    "beamer": "beamer",
    "context": "context",
    "docbook4": "docbook4",
    "docbook5": "docbook5",
    "dzslides": "dzslides",
    "epub2": "epub2",
    "epub3": "epub3",
    "haddock": "haddock",
    "icml": "icml",
    "jats_archiving": "jats_archiving",
    "jats_articleauthoring": "jats_articleauthoring",
    "jats_publishing": "jats_publishing",
    "markua": "markua",
    "ms": "ms",
    "opendocument": "opendocument",
    "pptx": "pptx",
    "revealjs": "revealjs",
    "s5": "s5",
    "slideous": "slideous",
    "slidy": "slidy",
    "tei": "tei",
    "texinfo": "texinfo",
    "xwiki": "xwiki",
    "zimwiki": "zimwiki",
    "typst": "typst",
    "chunkedhtml": "chunkedhtml",
    "commonmark_x": "commonmark_x",
    "markdown_github": "markdown_github",
    "markdown_mmd": "markdown_mmd",
    "markdown_phpextra": "markdown_phpextra",
    "markdown_strict": "markdown_strict",
}


# MIME type mappings for Unstructured IO output formats
UNSTRUCTURED_IO_MIME_MAPPING = {
    "json": "application/json",
    "md": "text/markdown", 
    "txt": "text/plain"
}


# Service mapping for conversion method names to service identifiers
# Used for filename generation and test reporting
CONVERSION_METHOD_TO_SERVICE_MAP = {
    "JSON Structure Extraction": "UNSTRUCTURED_IO",
    "Markdown Conversion": "PANDOC",
    "DOCX Conversion": "LIBREOFFICE",
    "HTML Conversion": "LIBREOFFICE",
    "PDF Generation": "GOTENBERG",
    "Text Extraction": "UNSTRUCTURED_IO",
    "XLSX Conversion": "LIBREOFFICE",
    "RTF Conversion": "LIBREOFFICE",
    "ODT Conversion": "LIBREOFFICE",
    "PPTX Conversion": "LIBREOFFICE",
    "File Conversion": "LOCAL"
}


def get_conversion_methods(input_format: str, output_format: str) -> List[Tuple[ConversionService, ConversionPriority, str]]:
    """
    Get available conversion methods for a given input/output format pair.

    Args:
        input_format: Input file format (e.g., 'docx', 'pdf')
        output_format: Output file format (e.g., 'pdf', 'json')

    Returns:
        List of tuples containing (service, priority, description)
    """
    key = (input_format.lower(), output_format.lower())
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

    # Return the highest priority method
    primary_methods = [m for m in methods if m[1] == ConversionPriority.PRIMARY]
    if primary_methods:
        service, _, description = primary_methods[0]
        return (service, description)

    # Fallback to any available method
    service, _, description = methods[0]
    return (service, description)


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


# All supported format pairs for reference
ALL_SUPPORTED_CONVERSIONS = list(CONVERSION_MATRIX.keys())

def get_service_urls() -> Dict[str, str]:
    """
    Get service URLs with fallback mechanism for Docker vs local development.
    
    Returns:
        Dictionary mapping service names to their resolved URLs
    """
    import os
    import socket
    
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

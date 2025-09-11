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
    },
    "local-weasyprint": {
        "docker": "http://localhost:8369",
        "local": "http://localhost:8369"
    }
}


class ConversionService(Enum):
    """Available conversion services."""
    UNSTRUCTURED_IO = "unstructured-io"
    LIBREOFFICE = "libreoffice"
    PANDOC = "pandoc"
    GOTENBERG = "gotenberg"
    LOCAL = "local"
    LOCAL_WEASYPRINT = "local-weasyprint"


# Service URL mappings (should match main app)
SERVICE_URLS = {
    ConversionService.UNSTRUCTURED_IO: "http://unstructured-io:8000",
    ConversionService.LIBREOFFICE: "http://libreoffice:2004",
    ConversionService.PANDOC: "http://pandoc:3000",
    ConversionService.GOTENBERG: "http://gotenberg:3000",
    ConversionService.LOCAL: None,  # Local processing, no URL needed
    ConversionService.LOCAL_WEASYPRINT: None  # Local WeasyPrint processing, no URL needed
}


# Passthrough formats - formats that can be passed through without conversion
# when input and output formats are the same
PASSTHROUGH_FORMATS = {
    "html",
    "txt", 
    "md"
}

# Conversion matrix defining input -> output format mappings with preferred services
CONVERSION_MATRIX = {
    ("doc", "md"): [
        [ConversionService.LIBREOFFICE, "doc", "docx", "Convert legacy DOC to DOCX using LibreOffice"],
        [ConversionService.PANDOC, "docx", "md", "Convert DOCX to Markdown using Pandoc"]
    ],

    ("docx", "html"): [
        (ConversionService.LIBREOFFICE, "Word to HTML"),
        (ConversionService.PANDOC, "Word to HTML"),
    ],

    ("docx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Document structure extraction"),
    ],

    ("docx", "md"): [
        (ConversionService.PANDOC, "Word to Markdown"),
        (ConversionService.UNSTRUCTURED_IO, "Structure extraction only"),
    ],

    ("docx", "pdf"): [
        (ConversionService.GOTENBERG, "High-quality office document to PDF"),
        (ConversionService.LIBREOFFICE, "Excellent office format support"),
        (ConversionService.PANDOC, "Limited office format support"),
    ],

    ("docx", "tex"): [
        (ConversionService.PANDOC, "Word to LaTeX"),
    ],

    ("docx", "txt"): [
        (ConversionService.LIBREOFFICE, "Word to Text"),
        (ConversionService.UNSTRUCTURED_IO, "Text extraction"),
        (ConversionService.PANDOC, "Word to Text"),
    ],

    ("eml", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Email structure extraction"),
    ],

    ("epub", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "E-book structure extraction"),
    ],

    ("epub", "md"): [
        (ConversionService.PANDOC, "E-book to Markdown"),
    ],

    ("epub", "pdf"): [
        (ConversionService.LIBREOFFICE, "E-book to PDF"),
        (ConversionService.PANDOC, "E-book format support"),
    ],

    ("html", "docx"): [
        (ConversionService.LIBREOFFICE, "HTML to Word"),
        (ConversionService.PANDOC, "HTML to Word"),
    ],

    ("html", "odt"): [
        (ConversionService.LIBREOFFICE, "HTML to ODT"),
        (ConversionService.PANDOC, "HTML to ODT"),
    ],

    ("html", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "HTML structure extraction"),
    ],

    ("html", "md"): [
        (ConversionService.PANDOC, "HTML to Markdown"),
    ],

    ("html", "pdf"): [
        (ConversionService.LOCAL_WEASYPRINT, "High-quality HTML to PDF with WeasyPrint"),
        (ConversionService.GOTENBERG, "High-fidelity HTML to PDF with CSS support"),
        (ConversionService.PANDOC, "Good for simple HTML"),
        (ConversionService.LIBREOFFICE, "Basic HTML support"),
    ],

    ("html", "tex"): [
        (ConversionService.PANDOC, "HTML to LaTeX"),
    ],

    ("html", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, "HTML text extraction"),
        (ConversionService.LIBREOFFICE, "HTML to Text"),
        (ConversionService.PANDOC, "HTML to Text"),
    ],

    ("latex", "docx"): [
        (ConversionService.PANDOC, "LaTeX to Word"),
    ],

    ("latex", "html"): [
        (ConversionService.PANDOC, "LaTeX to HTML"),
    ],

    ("latex", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "LaTeX structure extraction"),
    ],

    ("latex", "md"): [
        (ConversionService.PANDOC, "LaTeX to Markdown"),
    ],

    ("latex", "pdf"): [
        (ConversionService.PANDOC, "LaTeX to PDF"),
    ],

    ("latex", "txt"): [
        (ConversionService.PANDOC, "LaTeX to Text"),
    ],

    ("md", "docx"): [
        (ConversionService.PANDOC, "Markdown to Word"),
        (ConversionService.LIBREOFFICE, "Via intermediate format"),
    ],

    ("md", "html"): [
        (ConversionService.PANDOC, "Markdown to HTML"),
    ],

    ("md", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Markdown structure extraction"),
    ],

    ("md", "pdf"): [
        (ConversionService.PANDOC, "Markdown to PDF via LaTeX"),
        (ConversionService.LIBREOFFICE, "Basic markdown support"),
    ],

    ("md", "tex"): [
        (ConversionService.PANDOC, "Markdown to LaTeX"),
    ],

    ("md", "txt"): [
        (ConversionService.PANDOC, "Markdown to Text"),
        (ConversionService.UNSTRUCTURED_IO, "Text extraction"),
    ],

    ("msg", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Outlook message structure extraction"),
    ],

    ("numbers", "html"): [
        (ConversionService.LIBREOFFICE, "Apple Numbers to HTML via LibreOffice"),
    ],

    ("numbers", "json"): [
        [ConversionService.LIBREOFFICE, "numbers", "xlsx", "Convert Apple Numbers to XLSX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "xlsx", "json", "Convert XLSX to JSON using unstructured-io"]
    ],

    ("numbers", "md"): [
        [ConversionService.LIBREOFFICE, "numbers", "xlsx", "Convert Apple Numbers to XLSX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "xlsx", "md", "Convert XLSX to Markdown using unstructured-io"]
    ],

    ("numbers", "txt"): [
        (ConversionService.LIBREOFFICE, "Apple Numbers to Text via LibreOffice"),
    ],

    ("numbers", "xlsx"): [
        (ConversionService.LIBREOFFICE, "Apple Numbers to Excel via LibreOffice"),
    ],

    ("odp", "pdf"): [
        (ConversionService.LIBREOFFICE, "Native OpenDocument presentation support"),
    ],

    ("odp", "json"): [
        [ConversionService.LIBREOFFICE, "odp", "pptx", "Convert ODP to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "json", "Extract structure from PPTX using unstructured-io"]
    ],

    ("odp", "md"): [
        [ConversionService.LIBREOFFICE, "odp", "pptx", "Convert ODP to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "md", "Convert PPTX to Markdown using unstructured-io"]
    ],

    ("odp", "txt"): [
        [ConversionService.LIBREOFFICE, "odp", "pptx", "Convert ODP to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "txt", "Extract text from PPTX using unstructured-io"]
    ],

    ("odp", "html"): [
        [ConversionService.LIBREOFFICE, "odp", "pptx", "Convert ODP to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "json", "Convert PPTX to JSON using unstructured-io"],
        [ConversionService.LOCAL, "json", "html", "Convert JSON to HTML using local processing", {
            "special_handler": "presentation_to_html",
            "requires_temp_file": True
        }]
    ],

    ("odp", "pptx"): [
        (ConversionService.LIBREOFFICE, "OpenDocument presentation to PowerPoint"),
    ],

    ("ods", "html"): [
        (ConversionService.LIBREOFFICE, "OpenDocument spreadsheet to HTML"),
    ],

    ("ods", "md"): [
        (ConversionService.LOCAL, "ODS to Markdown via local processing"),
    ],

    ("ods", "pdf"): [
        (ConversionService.LIBREOFFICE, "Native OpenDocument spreadsheet support"),
    ],

    ("ods", "txt"): [
        (ConversionService.LOCAL, "ODS to Text via local processing"),
    ],

    ("odt", "docx"): [
        (ConversionService.LIBREOFFICE, "OpenDocument to Word"),
        (ConversionService.PANDOC, "OpenDocument support"),
    ],

    ("odt", "html"): [
        (ConversionService.LIBREOFFICE, "OpenDocument to HTML"),
        (ConversionService.PANDOC, "OpenDocument support"),
    ],

    ("odt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "OpenDocument structure extraction"),
    ],

    ("odt", "md"): [
        (ConversionService.PANDOC, "OpenDocument to Markdown"),
        (ConversionService.UNSTRUCTURED_IO, "Structure extraction only"),
    ],

    ("odt", "pdf"): [
        (ConversionService.LIBREOFFICE, "Native OpenDocument support"),
        (ConversionService.PANDOC, "Good OpenDocument support"),
    ],

    ("odt", "txt"): [
        (ConversionService.LIBREOFFICE, "OpenDocument to Text"),
        (ConversionService.UNSTRUCTURED_IO, "Text extraction"),
        (ConversionService.PANDOC, "OpenDocument to Text"),
    ],

    ("pages", "docx"): [
        (ConversionService.LIBREOFFICE, "Apple Pages to DOCX via LibreOffice")
    ],

    ("pages", "html"): [
        (ConversionService.LIBREOFFICE, "Apple Pages to HTML via LibreOffice")
    ],

    ("pages", "json"): [
        [ConversionService.LIBREOFFICE, "pages", "docx", "Convert Apple Pages to DOCX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "docx", "json", "Convert DOCX to JSON using Unstructured IO"]
    ],

    ("pages", "md"): [
        [ConversionService.LIBREOFFICE, "pages", "docx", "Convert Apple Pages to DOCX using LibreOffice"],
        [ConversionService.PANDOC, "docx", "md", "Convert DOCX to Markdown using Pandoc"]
    ],

    ("pages", "pdf"): [
        (ConversionService.LIBREOFFICE, "Apple Pages to PDF via LibreOffice"),
    ],

    ("pages", "txt"): [
        [ConversionService.LIBREOFFICE, "pages", "docx", "Convert Apple Pages to DOCX using LibreOffice"],
        [ConversionService.PANDOC, "docx", "txt", "Convert DOCX to TXT using Pandoc"]
    ],

    ("key", "pdf"): [
        (ConversionService.LIBREOFFICE, "Apple Keynote to PDF via LibreOffice")
    ],

    ("key", "odp"): [
        (ConversionService.LIBREOFFICE, "Apple Keynote to ODP via LibreOffice")
    ],

    ("key", "pptx"): [
        (ConversionService.LIBREOFFICE, "Apple Keynote to PPTX via LibreOffice")
    ],

    ("key", "md"): [
        [ConversionService.LIBREOFFICE, "key", "pptx", "Convert Apple Keynote to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "md", "Convert PPTX to Markdown using unstructured-io"]
    ],

    ("key", "txt"): [
        [ConversionService.LIBREOFFICE, "key", "pptx", "Convert Apple Keynote to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "txt", "Convert PPTX to Text using unstructured-io"]
    ],

    ("key", "html"): [
        [ConversionService.LIBREOFFICE, "key", "pptx", "Convert Apple Keynote to PPTX using LibreOffice"],
        [ConversionService.UNSTRUCTURED_IO, "pptx", "json", "Convert PPTX to JSON using unstructured-io"],
        [ConversionService.LOCAL, "json", "html", "Convert JSON to HTML using local processing", {
            "special_handler": "presentation_to_html",
            "requires_temp_file": True
        }]
    ],

    ("pdf", "docx"): [
        [ConversionService.UNSTRUCTURED_IO, "pdf", "html", "Extract text structure from PDF as HTML using Unstructured IO"],
        [ConversionService.PANDOC, "html", "docx", "Convert HTML to DOCX using Pandoc"]
    ],

    ("pdf", "html"): [
        (ConversionService.UNSTRUCTURED_IO, "PDF to HTML structure extraction"),
    ],

    ("pdf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "PDF structure extraction"),
    ],

    ("pdf", "md"): [
        (ConversionService.UNSTRUCTURED_IO, "PDF to text structure"),
    ],

    ("pdf", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, "PDF text extraction"),
        (ConversionService.LIBREOFFICE, "PDF to Text"),
    ],

    ("ppt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Legacy presentation structure extraction"),
    ],

    ("ppt", "md"): [
        (ConversionService.UNSTRUCTURED_IO, "Legacy presentation to Markdown"),
    ],

    ("ppt", "pdf"): [
        (ConversionService.LIBREOFFICE, "Legacy presentation format support"),
        (ConversionService.GOTENBERG, "May work via LibreOffice"),
    ],

    ("ppt", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, "Legacy presentation text extraction"),
        (ConversionService.LIBREOFFICE, "Legacy presentation to Text"),
    ],

    ("ppt", "html"): [
        (ConversionService.UNSTRUCTURED_IO, "Legacy presentation to HTML"),
    ],

    ("pptx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Presentation structure extraction"),
    ],

    ("pptx", "md"): [
        (ConversionService.UNSTRUCTURED_IO, "Presentation to Markdown"),
    ],

    ("pptx", "pdf"): [
        (ConversionService.GOTENBERG, "High-quality presentation to PDF"),
        (ConversionService.LIBREOFFICE, "Excellent presentation support"),
    ],

    ("pptx", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, "Presentation text extraction"),
        (ConversionService.LIBREOFFICE, "Presentation to Text"),
    ],

    ("pptx", "html"): [
        (ConversionService.UNSTRUCTURED_IO, "Presentation to HTML"),
    ],

    ("rtf", "docx"): [
        (ConversionService.LIBREOFFICE, "RTF to Word"),
        (ConversionService.PANDOC, "Limited RTF support"),
    ],

    ("rtf", "html"): [
        (ConversionService.LIBREOFFICE, "RTF to HTML"),
        (ConversionService.PANDOC, "Limited RTF support"),
    ],

    ("rtf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "RTF structure extraction"),
    ],

    ("rtf", "md"): [
        (ConversionService.PANDOC, "RTF to Markdown"),
    ],

    ("rtf", "pdf"): [
        (ConversionService.LIBREOFFICE, "Good RTF support"),
        (ConversionService.PANDOC, "Limited RTF support"),
    ],

    ("rtf", "txt"): [
        (ConversionService.LIBREOFFICE, "RTF to Text"),
        (ConversionService.UNSTRUCTURED_IO, "Text extraction"),
    ],

    ("tex", "docx"): [
        (ConversionService.PANDOC, "LaTeX to Word"),
    ],

    ("tex", "html"): [
        (ConversionService.PANDOC, "LaTeX to HTML"),
    ],

    ("tex", "json"): [
        [ConversionService.PANDOC, "tex", "docx", "Convert LaTeX to DOCX using Pandoc"],
        [ConversionService.UNSTRUCTURED_IO, "docx", "json", "Convert DOCX to JSON using Unstructured IO"]
    ],

    ("tex", "pdf"): [
        [ConversionService.PANDOC, "tex", "docx", "Convert LaTeX to DOCX using Pandoc"],
        [ConversionService.PANDOC, "docx", "pdf", "Convert DOCX to PDF using Pandoc"]
    ],

    ("tex", "txt"): [
        (ConversionService.PANDOC, "LaTeX to Text"),
    ],

    ("txt", "docx"): [
        (ConversionService.LIBREOFFICE, "Text to Word"),
        (ConversionService.PANDOC, "Text to Word"),
    ],

    ("txt", "html"): [
        (ConversionService.LIBREOFFICE, "Text to HTML"),
        (ConversionService.PANDOC, "Text to HTML"),
    ],

    ("txt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Text structure extraction"),
    ],

    ("txt", "md"): [
        (ConversionService.PANDOC, "Text to Markdown"),
    ],

    ("txt", "pdf"): [
        (ConversionService.LIBREOFFICE, "Simple text to PDF"),
        (ConversionService.PANDOC, "Text to PDF via LaTeX"),
    ],

    ("txt", "tex"): [
        (ConversionService.PANDOC, "Text to LaTeX"),
    ],

    ("url", "html"): [
        (ConversionService.LOCAL, "URL to HTML content fetching"),
    ],

    ("url", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "URL content structure extraction"),
    ],

    ("url", "md"): [
        (ConversionService.UNSTRUCTURED_IO, "URL to markdown conversion"),
    ],

    ("url", "pdf"): [
        (ConversionService.GOTENBERG, "URL to PDF conversion with full CSS support"),
    ],

    ("url", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, "URL to text conversion"),
    ],

    ("xls", "html"): [
        (ConversionService.LIBREOFFICE, "Legacy Excel to HTML via LibreOffice"),
    ],

    ("xls", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Legacy Excel structure extraction"),
    ],

    ("xls", "md"): [
        (ConversionService.LOCAL, "Legacy Excel to Markdown via local processing"),
    ],

    ("xls", "pdf"): [
        (ConversionService.LIBREOFFICE, "Legacy spreadsheet format support"),
        (ConversionService.GOTENBERG, "May work via LibreOffice"),
    ],

    ("xls", "txt"): [
        (ConversionService.LOCAL, "Legacy Excel to Text via local processing"),
    ],

    ("xlsx", "html"): [
        (ConversionService.LIBREOFFICE, "Excel to HTML via LibreOffice"),
    ],

    ("xlsx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, "Spreadsheet structure extraction"),
    ],

    ("xlsx", "md"): [
        (ConversionService.LOCAL, "Excel to Markdown via local processing"),
    ],

    ("xlsx", "pdf"): [
        (ConversionService.GOTENBERG, "High-quality spreadsheet to PDF"),
        (ConversionService.LIBREOFFICE, "Excellent spreadsheet support"),
    ],

    ("xlsx", "txt"): [
        (ConversionService.LOCAL, "Excel to Text via local processing"),
    ],

    ("url", "docx"): [
        (ConversionService.LIBREOFFICE, "URL to DOCX via HTML download and conversion"),
        (ConversionService.PANDOC, "URL to DOCX via HTML download and conversion"),
    ],

    ("url", "odt"): [
        (ConversionService.LIBREOFFICE, "URL to ODT via HTML download and conversion"),
        (ConversionService.PANDOC, "URL to ODT via HTML download and conversion"),
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
    "PDF Generation": "GOTENBERG",  # Default for PDF, but could be LOCAL_WEASYPRINT
    "Text Extraction": "UNSTRUCTURED_IO",
    "XLSX Conversion": "LIBREOFFICE",
    "RTF Conversion": "LIBREOFFICE",
    "ODT Conversion": "LIBREOFFICE",
    "PPTX Conversion": "LIBREOFFICE",
    "File Conversion": "LOCAL",
    "WeasyPrint PDF": "LOCAL_WEASYPRINT"
}


# All supported format pairs for reference
ALL_SUPPORTED_CONVERSIONS = list(CONVERSION_MATRIX.keys())

# Special handlers registry for custom conversion logic
SPECIAL_HANDLERS = {
    "presentation_to_html": "process_presentation_to_html"
}

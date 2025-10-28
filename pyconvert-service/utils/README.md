# CSS Margin Parser Utility

A reusable Python utility for extracting and converting CSS `@page` margin specifications from HTML/CSS content. This module is designed to be used across different document conversion tools that need to respect CSS margin definitions.

## Features

- **CSS Unit Conversion**: Converts CSS length values (in, cm, mm, pt, px, pc) to inches
- **@page Margin Extraction**: Parses CSS `@page` rules and extracts margin specifications
- **Multi-Format Support**: Converts margins to points, cm, mm, or Pandoc variables
- **Python-docx Integration**: Direct application of margins to DOCX documents
- **Robust Parsing**: Handles shorthand and individual margin properties with graceful fallbacks

## Installation

This utility is a standalone Python module with minimal dependencies:

```python
# For DOCX functionality only:
pip install python-docx
```

## Usage

### Basic Margin Extraction

```python
from utils.css_margin_parser import extract_page_margins_from_html

html = """
<style>
@page {
    margin: 0.75in;
}
</style>
"""

margins = extract_page_margins_from_html(html)
# Returns: {'top': 0.75, 'right': 0.75, 'bottom': 0.75, 'left': 0.75}
```

### CSS Unit Conversion

```python
from utils.css_margin_parser import parse_css_length_to_inches

# Convert various CSS units to inches
parse_css_length_to_inches("2.54cm")  # Returns 1.0
parse_css_length_to_inches("72pt")    # Returns 1.0
parse_css_length_to_inches("96px")    # Returns 1.0 (96 DPI)
```

### Apply Margins to DOCX Documents

```python
from docx import Document
from utils.css_margin_parser import (
    extract_page_margins_from_html,
    apply_margins_to_docx_sections
)

# Extract margins from HTML
margins = extract_page_margins_from_html(html_content)

# Apply to DOCX document
doc = Document()
apply_margins_to_docx_sections(doc, margins)
doc.save("output.docx")
```

### Convert to Different Units

```python
from utils.css_margin_parser import (
    margins_to_points,
    margins_to_cm,
    margins_to_mm
)

margins = {'top': 1.0, 'right': 1.0, 'bottom': 1.0, 'left': 1.0}

points = margins_to_points(margins)  # {'top': 72.0, ...}
cm = margins_to_cm(margins)          # {'top': 2.54, ...}
mm = margins_to_mm(margins)          # {'top': 25.4, ...}
```

### Format for Pandoc

```python
from utils.css_margin_parser import format_margins_for_pandoc

margins = {'top': 0.75, 'right': 1.0, 'bottom': 0.75, 'left': 1.0}

pandoc_vars = format_margins_for_pandoc(margins)
# Returns: {
#   'margin-top': '0.75in',
#   'margin-right': '1.0in',
#   'margin-bottom': '0.75in',
#   'margin-left': '1.0in'
# }

# Use with Pandoc command:
# pandoc input.html -o output.docx \
#   -V margin-top=0.75in -V margin-right=1.0in \
#   -V margin-bottom=0.75in -V margin-left=1.0in
```

## Supported CSS Margin Formats

### Shorthand Margin Property

```css
/* Single value - all sides */
@page {
  margin: 0.75in;
}

/* Two values - vertical horizontal */
@page {
  margin: 0.5in 1in;
}

/* Three values - top horizontal bottom */
@page {
  margin: 0.5in 0.75in 1in;
}

/* Four values - top right bottom left */
@page {
  margin: 0.5in 0.75in 1in 0.6in;
}
```

### Individual Margin Properties

```css
@page {
  margin-top: 0.5in;
  margin-right: 0.75in;
  margin-bottom: 1in;
  margin-left: 0.6in;
}
```

### Mixed Units

```css
@page {
  margin: 72pt 2.54cm 25.4mm 96px;
}
```

## Supported CSS Units

| Unit | Description | Conversion to Inches  |
| ---- | ----------- | --------------------- |
| `in` | Inches      | 1:1                   |
| `cm` | Centimeters | 2.54 cm = 1 in        |
| `mm` | Millimeters | 25.4 mm = 1 in        |
| `pt` | Points      | 72 pt = 1 in          |
| `px` | Pixels      | 96 px = 1 in (96 DPI) |
| `pc` | Picas       | 6 pc = 1 in           |

## API Reference

### `extract_page_margins_from_html(html_content: str) -> Dict[str, float]`

Extracts `@page` margin specifications from HTML/CSS content.

**Parameters:**

- `html_content` (str): HTML string containing CSS `@page` rules

**Returns:**

- Dictionary with keys `'top'`, `'right'`, `'bottom'`, `'left'` containing margin values in inches
- Empty dictionary if no margins found

**Example:**

```python
margins = extract_page_margins_from_html(html)
# {'top': 0.75, 'right': 0.75, 'bottom': 0.75, 'left': 0.75}
```

---

### `parse_css_length_to_inches(css_value: str) -> float`

Converts CSS length values to inches.

**Parameters:**

- `css_value` (str): CSS length string (e.g., "0.75in", "2.54cm", "72pt")

**Returns:**

- Float value in inches
- Returns 1.0 if parsing fails

**Example:**

```python
inches = parse_css_length_to_inches("2.54cm")  # 1.0
```

---

### `margins_to_points(margins: Dict[str, float]) -> Dict[str, float]`

Converts margin dictionary from inches to points (72 points = 1 inch).

**Parameters:**

- `margins` (dict): Dictionary with margin values in inches

**Returns:**

- Dictionary with margin values in points

---

### `margins_to_cm(margins: Dict[str, float]) -> Dict[str, float]`

Converts margin dictionary from inches to centimeters.

---

### `margins_to_mm(margins: Dict[str, float]) -> Dict[str, float]`

Converts margin dictionary from inches to millimeters.

---

### `format_margins_for_pandoc(margins: Dict[str, float]) -> Dict[str, str]`

Formats margins for Pandoc command-line variables.

**Returns:**

- Dictionary with Pandoc variable names and formatted values

---

### `apply_margins_to_docx_sections(docx_document, margins: Dict[str, float]) -> None`

Applies margins to all sections in a python-docx Document object.

**Parameters:**

- `docx_document`: A python-docx Document object
- `margins` (dict): Dictionary with margin values in inches

**Requires:**

- `python-docx` library installed

## Integration Examples

### With WeasyPrint (PDF Generation)

WeasyPrint natively respects CSS `@page` margins, but you can use this utility to verify or override:

```python
from weasyprint import HTML, CSS
from utils.css_margin_parser import extract_page_margins_from_html, margins_to_points

# Extract margins for validation
margins = extract_page_margins_from_html(html_content)
print(f"Document will use margins: {margins}")

# WeasyPrint respects @page natively
HTML(string=html_content).write_pdf('output.pdf')
```

### With html4docx (HTML to DOCX)

```python
from html4docx import HtmlToDocx
from utils.css_margin_parser import (
    extract_page_margins_from_html,
    apply_margins_to_docx_sections
)

# Convert HTML to DOCX
converter = HtmlToDocx()
doc = converter.parse_html_string(html_content)

# Extract and apply CSS margins
margins = extract_page_margins_from_html(html_content)
if margins:
    apply_margins_to_docx_sections(doc, margins)

doc.save('output.docx')
```

### With Pandoc (Command-Line)

```python
import subprocess
from utils.css_margin_parser import (
    extract_page_margins_from_html,
    format_margins_for_pandoc
)

# Extract margins
margins = extract_page_margins_from_html(html_content)
pandoc_vars = format_margins_for_pandoc(margins)

# Build Pandoc command with margin variables
cmd = ['pandoc', 'input.html', '-o', 'output.docx']
for key, value in pandoc_vars.items():
    cmd.extend(['-V', f'{key}={value}'])

subprocess.run(cmd)
```

### With ReportLab (PDF from scratch)

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate
from utils.css_margin_parser import (
    extract_page_margins_from_html,
    margins_to_points
)

# Extract margins and convert to points (ReportLab uses points)
margins = extract_page_margins_from_html(html_content)
points = margins_to_points(margins)

# Create PDF with margins
doc = SimpleDocTemplate(
    "output.pdf",
    pagesize=letter,
    topMargin=points['top'],
    bottomMargin=points['bottom'],
    leftMargin=points['left'],
    rightMargin=points['right']
)
```

## Service Integration

The CSS margin parser is integrated into multiple document conversion services:

### html4docx (HTML → DOCX)

**Automatic Integration**: Margins are extracted from HTML and applied to DOCX sections.

```python
# Automatic in /html4docx endpoint
margins = extract_page_margins_from_html(html_content)
if margins:
    apply_margins_to_docx_sections(docx_document, margins)
```

### pandoc (HTML → DOCX/PDF)

**Automatic Integration**: Margins are extracted and applied as pandoc variables for DOCX and PDF output.

```python
# Automatic in /pandoc endpoint for HTML input
margins = extract_page_margins_from_html(html_content)
pandoc_vars = format_margins_for_pandoc(margins)
# Adds -V margin-top=0.75in -V margin-right=1.0in etc. to pandoc command
```

### weasyprint (HTML → PDF)

**Validation Integration**: Margins are extracted for logging/validation (WeasyPrint supports CSS @page natively).

```python
# Automatic in /weasyprint endpoint
margins = extract_page_margins_from_html(html_content)
print(f"WeasyPrint detected margins: {margins}")
# WeasyPrint respects @page margins natively in PDF output
```

## Integration Test

Run the comprehensive integration test:

```bash
cd /path/to/applite-xtrac
python3 tests/test_margin_integration.py
```

This test verifies margin extraction works across all integrated services.

## Error Handling

The utility is designed with graceful error handling:

- **Invalid CSS values**: Returns 1.0 inch as default
- **Missing @page rules**: Returns empty dictionary
- **Mixed formats**: Individual properties override shorthand
- **DOCX application errors**: Should be wrapped in try/except to prevent conversion failure

```python
try:
    margins = extract_page_margins_from_html(html_content)
    if margins:
        apply_margins_to_docx_sections(doc, margins)
        print(f"Applied margins: {margins}")
except Exception as e:
    print(f"Warning: Failed to apply margins: {e}")
    # Conversion continues with default margins
```

## Testing

Run the comprehensive test suite:

```bash
cd /path/to/applite-xtrac
python3 tests/test_margin_extraction.py
```

The test suite validates:

- CSS unit conversions (in, cm, mm, pt, px, pc)
- Margin extraction patterns (shorthand, individual, mixed)
- Resume template scenarios
- Unit conversion utilities
- Pandoc formatting

## Design Principles

1. **Library Agnostic**: Core functions have no dependencies, work with any document tool
2. **Graceful Fallbacks**: Invalid input returns sensible defaults, doesn't crash
3. **Consistent Output**: Always returns margins in inches for cross-tool compatibility
4. **Comprehensive Coverage**: Handles all CSS margin formats and common edge cases
5. **Easy Integration**: Helper functions for common use cases (DOCX, Pandoc, etc.)

## Use Cases

- **Resume/CV Generation**: Preserve designer-specified margins in DOCX exports
- **Document Conversion Pipelines**: Consistent margin handling across HTML/PDF/DOCX
- **Template Systems**: Apply CSS-based margin specifications to various output formats
- **Multi-Format Publishing**: Extract margins once, apply to PDF, DOCX, etc.
- **Automated Document Processing**: Batch conversion with margin preservation

## Future Enhancements

Potential additions (not currently implemented):

- Page size extraction from `@page size` property
- Orientation detection (portrait/landscape)
- Additional CSS print properties (orphans, widows, page-break-\*)
- ODT (OpenDocument) format support
- Custom DPI configuration for pixel conversions

## License

Part of the AgentM.Resume project. See repository license for details.

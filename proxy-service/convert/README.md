# Conversion Endpoints

This directory contains the `/convert` endpoint implementations for the Multi-Service Document Processing API.

## Overview

The `/convert` endpoints provide high-level conversion aliases that automatically route requests to the most reliable service for each conversion type. These endpoints are designed to simplify document conversion workflows by abstracting away the complexity of choosing the right service.

## Priority Focus

Special attention has been given to formats commonly used for **resumes/CVs/cover letters**:

### Priority Input Formats
- `pptx`, `ppt` - PowerPoint presentations
- `docx`, `odt`, `rtf` - Word processing documents
- `html` - Web content
- `md` - Markdown
- `tex` - LaTeX
- `txt` - Plain text

### Priority Output Formats
- `pdf` - Universal document format
- `docx` - Modern Word format
- `html` - Web format
- `md` - Markdown
- `txt` - Plain text
- `json` - Structured data

## Available Endpoints

### PDF Output Conversions (High Priority)

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-pdf` | DOCX to PDF | Gotenberg | Resume/CV conversion |
| `POST /convert/pptx-pdf` | PPTX to PDF | Gotenberg | Presentation conversion |
| `POST /convert/ppt-pdf` | PPT to PDF | LibreOffice | Legacy presentation |
| `POST /convert/html-pdf` | HTML to PDF | Gotenberg | Web content to PDF |
| `POST /convert/md-pdf` | Markdown to PDF | Pandoc | Text content to PDF |
| `POST /convert/tex-pdf` | LaTeX to PDF | Pandoc | Academic content |
| `POST /convert/txt-pdf` | Text to PDF | LibreOffice | Simple text to PDF |
| `POST /convert/rtf-pdf` | RTF to PDF | LibreOffice | Legacy text format |
| `POST /convert/odt-pdf` | ODT to PDF | LibreOffice | Open document |

### JSON Structure Extraction

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-json` | DOCX to JSON | Unstructured IO | Document analysis |
| `POST /convert/pdf-json` | PDF to JSON | Unstructured IO | Document analysis |
| `POST /convert/pptx-json` | PPTX to JSON | Unstructured IO | Presentation analysis |
| `POST /convert/html-json` | HTML to JSON | Unstructured IO | Web content analysis |

### Markdown Conversions

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-md` | DOCX to Markdown | Pandoc | Content extraction |
| `POST /convert/html-md` | HTML to Markdown | Pandoc | Content extraction |
| `POST /convert/pdf-md` | PDF to Markdown | Unstructured IO | Content extraction |

### DOCX Conversions

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/md-docx` | Markdown to DOCX | Pandoc | Document creation |
| `POST /convert/html-docx` | HTML to DOCX | LibreOffice | Document creation |
| `POST /convert/rtf-docx` | RTF to DOCX | LibreOffice | Format upgrade |
| `POST /convert/txt-docx` | Text to DOCX | LibreOffice | Document creation |

### Additional Conversions

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/xlsx-pdf` | XLSX to PDF | Gotenberg | Spreadsheet to PDF |
| `POST /convert/xls-pdf` | XLS to PDF | LibreOffice | Legacy spreadsheet |
| `POST /convert/epub-pdf` | EPUB to PDF | LibreOffice | E-book to PDF |
| `POST /convert/ods-pdf` | ODS to PDF | LibreOffice | OpenDocument spreadsheet |
| `POST /convert/odp-pdf` | ODP to PDF | LibreOffice | OpenDocument presentation |

## Utility Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /convert/supported` | Get all supported conversion pairs |
| `GET /convert/info/{input}-{output}` | Get info about a specific conversion |

## Usage Examples

### Convert a DOCX Resume to PDF

```bash
curl -X POST "http://localhost:8369/convert/docx-pdf" \
  -F "file=@resume.docx" \
  -o resume.pdf
```

### Convert a Markdown Cover Letter to DOCX

```bash
curl -X POST "http://localhost:8369/convert/md-docx" \
  -F "file=@cover-letter.md" \
  -o cover-letter.docx
```

### Extract Structure from a PDF

```bash
curl -X POST "http://localhost:8369/convert/pdf-json" \
  -F "file=@document.pdf" \
  -o document-structure.json
```

### Convert HTML Content to PDF

```bash
curl -X POST "http://localhost:8369/convert/html-pdf" \
  -F "file=@webpage.html" \
  -o webpage.pdf
```

## Service Selection Logic

Each endpoint automatically selects the most reliable service based on:

1. **Quality**: Highest fidelity conversion
2. **Reliability**: Most stable service for the format pair
3. **Performance**: Best balance of speed and quality
4. **Format Support**: Comprehensive coverage of format features

### Primary Service Preferences

- **PDF Output**: Gotenberg (for HTML, DOCX, XLSX, PPTX) → LibreOffice (for others) → Pandoc (fallback)
- **JSON Output**: Unstructured IO (structure extraction)
- **DOCX Output**: LibreOffice (office formats) → Pandoc (markup formats)
- **Markdown Output**: Pandoc (primary) → Unstructured IO (fallback)
- **HTML Output**: LibreOffice (office formats) → Pandoc (markup formats)

## Error Handling

All endpoints include comprehensive error handling:

- **400**: Invalid file format or request
- **404**: Conversion pair not supported
- **500**: Internal conversion error
- **502**: Service unavailable
- **503**: Service timeout

## File Size Limits

- **General files**: 50MB limit
- **PDF files**: 100MB limit (for structure extraction)
- **Office documents**: 50MB limit
- **Text files**: 10MB limit

## Response Format

All conversion endpoints return:
- **Content-Type**: Appropriate MIME type for output format
- **Content-Disposition**: `attachment; filename=output.ext`
- **Streaming Response**: Efficient handling of large files

## Configuration

The conversion logic is defined in `config.py` and organized across several utility modules:

**Core Configuration (`config.py`)**:
- `CONVERSION_MATRIX`: Defines all supported conversion pairs and their service routing
- `SPECIAL_HANDLERS`: Registry for custom conversion logic

**Utility Modules**:
- `utils/conversion_lookup.py`: Functions for looking up conversion methods and service URLs
- `utils/conversion_chaining.py`: Logic for multi-step chained conversions  
- `utils/special_handlers.py`: Custom conversion handlers for special cases

The conversion system can be easily extended by:

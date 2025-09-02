# Format Support Matrix

This document provides a comprehensive overview of supported file formats across all services in the Multi-Service Document Processing API, including conversion capabilities and identified gaps.

## 📋 Table of Contents

- [Service Overview](#service-overview)
- [Comprehensive Format Support](#comprehensive-format-support)
  - [Text Documents](#text-documents)
  - [Spreadsheets](#spreadsheets)
  - [Presentations](#presentations)
  - [E-books and Publishing](#e-books-and-publishing)
  - [Email and Communications](#email-and-communications)
  - [Images and Graphics](#images-and-graphics)
  - [Legacy and Specialized Formats](#legacy-and-specialized-formats)
- [Output Format Support](#output-format-support)
- [Conversion Gaps and Limitations](#conversion-gaps-and-limitations)
- [Recommended Conversion Workflows](#recommended-conversion-workflows)
- [🔄 Conversion API Endpoints](#🔄-conversion-api-endpoints)
  - [Priority Focus](#🎯-priority-focus-resumecv-cover-letter-formats)
  - [Available Endpoints](#📋-available-endpoints)
  - [Usage Examples](#💡-usage-examples)
  - [Service Intelligence](#🧠-service-intelligence)
  - [Configuration](#⚙️-configuration)
- [Future Enhancement Opportunities](#future-enhancement-opportunities)
- [📚 Navigation](#📚-navigation)

---

# Service Overview

| Service | Primary Function | Key Formats | Output Formats |
|---------|------------------|-------------|----------------|
| **Unstructured IO** | Document structure extraction | PDF, DOCX, DOC, ODT, PPTX, PPT, XLSX, CSV, TSV, EML, MSG, RTF, EPUB, HTML, XML, PNG, JPG, HEIC, TXT | JSON (structure extraction) |
| **LibreOffice** | Office document conversion | Extensive office formats (DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP, etc.) | PDF, HTML, DOCX, ODT, and many others |
| **Pandoc** | Universal document conversion | Markdown, HTML, LaTeX, DOCX, ODT, RST, AsciiDoc, and 40+ formats | PDF, HTML, DOCX, LaTeX, Markdown, and 50+ formats |
| **Gotenberg** | HTML and office document to PDF conversion | HTML, URLs, DOCX, XLSX, PPTX, and other office formats | PDF |

## Comprehensive Format Support

### Text Documents
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Microsoft Word | .doc | ✅ | ✅ | ❌ | ❌ | Legacy format, good support |
| Word 2007+ | .docx | ✅ | ✅ | ✅ | ✅ | Universal support |
| OpenDocument Text | .odt | ✅ | ✅ | ✅ | ❌ | Open standard |
| Rich Text Format | .rtf | ✅ | ✅ | ❌ | ❌ | Limited conversion options |
| Plain Text | .txt | ✅ | ✅ | ✅ | ❌ | Universal support |
| HTML | .html | ✅ | ✅ | ✅ | ✅ | Web publishing - Gotenberg can convert HTML to PDF with full CSS support |
| Markdown | .md | ❌ | ❌ | ✅ | ❌ | Pandoc native |
| LaTeX | .tex | ❌ | ❌ | ✅ | ❌ | Academic publishing |
| reStructuredText | .rst | ❌ | ❌ | ✅ | ❌ | Python documentation |
| AsciiDoc | .asciidoc | ❌ | ❌ | ✅ | ❌ | Technical writing |
| MediaWiki | .wiki | ❌ | ❌ | ✅ | ❌ | Wiki markup |
| Textile | .textile | ❌ | ❌ | ✅ | ❌ | Lightweight markup |
| Org Mode | .org | ❌ | ❌ | ✅ | ❌ | Emacs format |
| FictionBook | .fb2 | ❌ | ✅ | ✅ | ❌ | E-book format |

### Spreadsheets
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Excel 97-2003 | .xls | ❌ | ✅ | ❌ | ✅ | Legacy format - Gotenberg supports via LibreOffice |
| Excel 2007+ | .xlsx | ✅ | ✅ | ❌ | ✅ | Modern Excel - Gotenberg supports via LibreOffice |
| OpenDocument Spreadsheet | .ods | ❌ | ✅ | ❌ | ❌ | Open standard |
| CSV | .csv | ✅ | ✅ | ✅ | ❌ | Universal data format |
| TSV | .tsv | ✅ | ✅ | ✅ | ❌ | Tab-separated values |
| dBase | .dbf | ❌ | ✅ | ❌ | ❌ | Database format |
| Apache Parquet | .parquet | ❌ | ✅ | ❌ | ❌ | Big data format |
| Gnumeric | .gnumeric | ❌ | ✅ | ❌ | ❌ | GNOME spreadsheet |

### Presentations
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| PowerPoint 97-2003 | .ppt | ✅ | ✅ | ❌ | ✅ | Legacy format - Gotenberg supports via LibreOffice |
| PowerPoint 2007+ | .pptx | ✅ | ✅ | ❌ | ✅ | Modern PowerPoint - Gotenberg supports via LibreOffice |
| OpenDocument Presentation | .odp | ❌ | ✅ | ❌ | ❌ | Open standard |
| Apple Keynote | .key | ❌ | ✅ | ❌ | ❌ | macOS format |

### E-books and Publishing
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| EPUB | .epub | ✅ | ✅ | ✅ | ❌ | E-book standard |
| FictionBook 2.0 | .fb2 | ❌ | ✅ | ✅ | ❌ | Russian e-book format |

### Email and Communications
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Email Message | .eml | ✅ | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| Outlook Message | .msg | ✅ | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |

### Images and Graphics
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| PNG | .png | ✅ | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| JPEG | .jpg, .jpeg | ✅ | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| HEIC | .heic | ✅ | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |

### Legacy and Specialized Formats
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| WordPerfect | .wpd | ❌ | ✅ | ❌ | ❌ | Legacy word processor |
| Microsoft Works | .wps, .wdb | ❌ | ✅ | ❌ | ❌ | Old office suite |
| Microsoft Write | .wri | ❌ | ✅ | ❌ | ❌ | Very old format |
| MacWrite | .mcw, .mwd | ❌ | ✅ | ❌ | ❌ | Classic Mac format |
| WriteNow | .wn | ❌ | ✅ | ❌ | ❌ | Old Mac format |
| Palm Doc | .pdb | ❌ | ✅ | ❌ | ❌ | PDA format |
| Pocket Word | .psw | ❌ | ✅ | ❌ | ❌ | Windows CE format |
| WordPerfect Graphics | .wpg | ❌ | ✅ | ❌ | ❌ | Vector graphics |
| Microsoft Publisher | .pub | ❌ | ✅ | ❌ | ❌ | Desktop publishing |
| Corel Draw | .cdr | ❌ | ✅ | ❌ | ❌ | Vector graphics |
| Freehand | .fh | ❌ | ✅ | ❌ | ❌ | Vector graphics |
| PageMaker | .p65, .pm, .pmd | ❌ | ✅ | ❌ | ❌ | Desktop publishing |
| QuarkXPress | .qxd, .qxt | ❌ | ✅ | ❌ | ❌ | Desktop publishing |
| Zoner Draw | .zmf | ❌ | ✅ | ❌ | ❌ | Vector graphics |

## Output Format Support

### Primary Output Formats
| Format | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Use Case |
|--------|----------------|-------------|--------|-----------|----------|
| PDF | ❌ | ✅ | ✅ | ✅ | Universal document format - Gotenberg provides high-fidelity HTML/CSS to PDF |
| HTML | ❌ | ✅ | ✅ | ✅ | Web publishing |
| DOCX | ❌ | ✅ | ✅ | ❌ | Modern Word format |
| ODT | ❌ | ✅ | ✅ | ❌ | Open document format |
| Markdown | ❌ | ❌ | ✅ | ❌ | Lightweight markup |
| LaTeX | ❌ | ❌ | ✅ | ❌ | Academic publishing |
| Plain Text | ❌ | ✅ | ✅ | ❌ | Simple text output |
| JSON | ✅ | ❌ | ❌ | ❌ | Structured data extraction |

### Specialized Output Formats
| Format | Service | Notes |
|--------|---------|-------|
| EPUB | LibreOffice, Pandoc | E-book creation |
| RTF | LibreOffice | Rich text format |
| DOC | LibreOffice | Legacy Word format |
| XLS | LibreOffice | Legacy Excel format |
| PPT | LibreOffice | Legacy PowerPoint format |
| MediaWiki | Pandoc | Wiki markup |
| AsciiDoc | Pandoc | Technical documentation |
| reStructuredText | Pandoc | Python docs |
| Man page | Pandoc | Unix manual pages |
| Jira | Pandoc | Issue tracking |
| DokuWiki | Pandoc | Wiki software |

## Conversion Gaps and Limitations

### Critical Gaps (No Service Support)
1. **Image Formats → Document Formats**
   - **Problem**: PNG, JPG, HEIC files can only be processed for text extraction by Unstructured IO
   - **Gap**: Cannot convert images to PDF, DOCX, HTML, or other document formats
   - **Impact**: Scanned documents, screenshots, and graphics cannot be converted to editable formats

2. **Email Formats → Document Formats**
   - **Problem**: EML and MSG files can only be processed for text extraction by Unstructured IO
   - **Gap**: Cannot convert emails to PDF, DOCX, or other document formats
   - **Impact**: Email archives cannot be converted to readable documents

### Limited Support Gaps
3. **Specialized E-book Formats**
   - **Problem**: FB2 format has limited conversion paths and may lose formatting
   - **Gap**: FB2 → PDF conversions may not preserve complex layouts
   - **Impact**: E-book conversion quality may be suboptimal

4. **Legacy Formats**
   - **Problem**: Very old formats (.wri, .mcw, .pdb, etc.) have limited modern support
   - **Gap**: Conversions may lose formatting or fail entirely
   - **Impact**: Archival documents may not convert properly

5. **Specialized Application Formats**
   - **Problem**: Formats like .pub, .cdr, .qxd have limited conversion options
   - **Gap**: Complex layouts and graphics may not convert well
   - **Impact**: Professional publishing documents may lose quality

### Service-Specific Limitations
6. **Unstructured IO Limitations**
   - Only outputs JSON structure extraction
   - Cannot convert between document formats
   - Limited to text and metadata extraction

7. **LibreOffice Limitations**
   - Best for office document formats
   - Limited support for modern markup formats (Markdown, AsciiDoc, etc.)
   - Some legacy formats may have conversion issues

8. **Pandoc Limitations**
   - Requires text-based input formats
   - Cannot process binary office documents directly (needs LibreOffice preprocessing)
   - Limited support for complex layouts and embedded objects

9. **Gotenberg Limitations**
   - Primarily focused on PDF generation
   - Limited support for converting between office document formats
   - Asynchronous processing may require additional handling in automation scripts

## Recommended Conversion Workflows

### For Office Documents → PDF
```
DOCX/DOC/ODT → LibreOffice → PDF (Best quality)
DOCX/DOC/ODT → Pandoc → PDF (Alternative, may lose formatting)
```

### For Markup → Office Documents
```
Markdown/HTML → Pandoc → DOCX (Best for simple documents)
Markdown/HTML → Pandoc → PDF → LibreOffice → DOCX (For complex layouts)
```

### For Mixed Content
```
Complex DOCX → Unstructured IO → JSON (Structure analysis)
Complex DOCX → LibreOffice → PDF (High-quality output)
Complex DOCX → Pandoc → Markdown (Text extraction)
```

### For Web Content
```
HTML → Pandoc → PDF (Best for articles)
HTML → Pandoc → DOCX (Editable output)
HTML → Unstructured IO → JSON (Content analysis)
```

## Future Enhancement Opportunities

1. **OCR Integration**: Add OCR service for image-to-text conversion
2. **Email Parser**: Add dedicated email-to-document conversion service
3. **Image Processing**: Add image-to-document conversion capabilities
4. **Legacy Format Support**: Improve conversion quality for old formats
5. **Format Detection**: Automatic format detection and optimal routing
6. **Batch Processing**: Support for converting multiple files simultaneously
7. **Quality Metrics**: Conversion quality assessment and format recommendations

---

# 🔄 Conversion API Endpoints

The API provides high-level conversion aliases at `/convert/*` that automatically route to the most reliable service for each conversion type. These endpoints are optimized for common document workflows, especially **resume/CV/cover letter** processing.

## 🎯 Priority Focus: Resume/CV/Cover Letter Formats

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

## 📋 Available Endpoints

### PDF Output Conversions (High Priority)

| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-pdf` | DOCX to PDF | Gotenberg | Resume/CV conversion |
| `POST /convert/pptx-pdf` | PPTX to PDF | Gotenberg | Presentation portfolios |
| `POST /convert/ppt-pdf` | PPT to PDF | LibreOffice | Legacy presentation |
| `POST /convert/html-pdf` | HTML to PDF | Gotenberg | Web resumes/profiles |
| `POST /convert/md-pdf` | Markdown to PDF | Pandoc | Technical resumes |
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

## 🔍 Utility Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /convert/supported` | Get all supported conversion pairs |
| `GET /convert/info/{input}-{output}` | Get info about a specific conversion |

## 💡 Usage Examples

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

## 🧠 Service Intelligence

Each endpoint automatically selects the optimal service based on quality and reliability:

### Primary Service Preferences

- **PDF Output**: Gotenberg (highest quality for HTML/DOCX/PPTX/XLSX) → LibreOffice → Pandoc
- **JSON Output**: Unstructured IO (best structure extraction)
- **DOCX Output**: LibreOffice (office formats) → Pandoc (markup formats)
- **Markdown Output**: Pandoc (native support) → Unstructured IO (fallback)
- **HTML Output**: LibreOffice (office formats) → Pandoc (markup formats)

## ⚠️ Error Handling

All endpoints include comprehensive error handling:

- **400**: Invalid file format or request
- **404**: Conversion pair not supported
- **500**: Internal conversion error
- **502**: Service unavailable
- **503**: Service timeout

## 📏 File Size Limits

- **General files**: 50MB limit
- **PDF files**: 100MB limit (for structure extraction)
- **Office documents**: 50MB limit
- **Text files**: 10MB limit

## 📤 Response Format

All conversion endpoints return:
- **Content-Type**: Appropriate MIME type for output format
- **Content-Disposition**: `attachment; filename=output.ext`
- **Streaming Response**: Efficient handling of large files

## ⚙️ Configuration

The conversion logic is defined in `proxy-service/convert/config.py` and can be easily extended:

```python
# Add new conversion pair
CONVERSION_MATRIX[("newformat", "output")] = [
    (ConversionService.SERVICE_NAME, ConversionPriority.PRIMARY, "Description"),
]
```

## 🧪 Testing

Test the endpoints with the provided examples or use the `/convert/supported` endpoint to see all available conversions.

---

## 📚 Navigation

- [← Back to Main README](../README.md)
- [Service Overview](#service-overview)
- [Comprehensive Format Support](#comprehensive-format-support)
  - [Text Documents](#text-documents)
  - [Spreadsheets](#spreadsheets)
  - [Presentations](#presentations)
  - [E-books and Publishing](#e-books-and-publishing)
  - [Email and Communications](#email-and-communications)
  - [Images and Graphics](#images-and-graphics)
  - [Legacy and Specialized Formats](#legacy-and-specialized-formats)
- [Output Format Support](#output-format-support)
- [Conversion Gaps and Limitations](#conversion-gaps-and-limitations)
- [Recommended Conversion Workflows](#recommended-conversion-workflows)
- [🔄 Conversion API Endpoints](#🔄-conversion-api-endpoints)
  - [Priority Focus](#🎯-priority-focus-resumecv-cover-letter-formats)
  - [Available Endpoints](#📋-available-endpoints)
  - [Usage Examples](#💡-usage-examples)
  - [Service Intelligence](#🧠-service-intelligence)
  - [Configuration](#⚙️-configuration)
- [Future Enhancement Opportunities](#future-enhancement-opportunities)

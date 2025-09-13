# Format Support Matrix

This document provides a comprehensive overview of supported file formats across all services in the Multi-Service Document Processing API, including conversion capabilities and identified gaps.

## 📋 Table of Contents

- [Format Support Matrix](#format-support-matrix)
  - [📋 Table of Contents](#-table-of-contents)
- [Service Overview](#service-overview)
  - [Master Format Support Matrix](#master-format-support-matrix)
  - [Comprehensive Format Support](#comprehensive-format-support)
    - [Text Documents](#text-documents)
    - [Spreadsheets](#spreadsheets)
    - [Presentations](#presentations)
    - [E-books and Publishing](#e-books-and-publishing)
    - [Email and Communications](#email-and-communications)
    - [Images and Graphics](#images-and-graphics)
    - [Legacy and Specialized Formats](#legacy-and-specialized-formats)
  - [Output Format Support](#output-format-support)
    - [Primary Output Formats](#primary-output-formats)
    - [Specialized Output Formats](#specialized-output-formats)
  - [Conversion Gaps and Limitations](#conversion-gaps-and-limitations)
    - [Critical Gaps (No Service Support)](#critical-gaps-no-service-support)
    - [Limited Support Gaps](#limited-support-gaps)
    - [Service-Specific Limitations](#service-specific-limitations)
  - [Recommended Conversion Workflows](#recommended-conversion-workflows)
    - [For Office Documents → PDF](#for-office-documents--pdf)
    - [For Markup → Office Documents](#for-markup--office-documents)
    - [For Mixed Content](#for-mixed-content)
    - [For Web Content](#for-web-content)
  - [Future Enhancement Opportunities](#future-enhancement-opportunities)
- [🔄 Conversion API Endpoints](#-conversion-api-endpoints)
  - [🎯 Priority Focus: Resume/CV/Cover Letter Formats](#-priority-focus-resumecvcover-letter-formats)
    - [Priority Input Formats](#priority-input-formats)
    - [Priority Output Formats](#priority-output-formats)
  - [📋 Complete Conversion Matrix](#-complete-conversion-matrix)
    - [PDF Output Conversions (High Priority)](#pdf-output-conversions-high-priority)
    - [JSON Structure Extraction](#json-structure-extraction)
    - [URL-Based Conversions](#url-based-conversions)
    - [DOCX Output Conversions](#docx-output-conversions)
    - [PPTX Output Conversions](#pptx-output-conversions)
    - [Markdown Output Conversions](#markdown-output-conversions)
    - [HTML Output Conversions](#html-output-conversions)
    - [LaTeX Output Conversions](#latex-output-conversions)
    - [Plain Text Output Conversions](#plain-text-output-conversions)
  - [XLSX Output Conversions](#xlsx-output-conversions)
  - [ODT Output Conversions](#odt-output-conversions)
  - [PPTX Output Conversions](#pptx-output-conversions-1)
  - [💡 Usage Examples](#-usage-examples)
    - [Convert a DOCX Resume to PDF](#convert-a-docx-resume-to-pdf)
    - [Extract PDF Structure](#extract-pdf-structure)
    - [Convert URL to PDF](#convert-url-to-pdf)
    - [Convert URL to HTML](#convert-url-to-html)
    - [Convert Markdown to DOCX](#convert-markdown-to-docx)
    - [Dynamic Endpoint Examples](#dynamic-endpoint-examples)
    - [List All Supported Conversions](#list-all-supported-conversions)
  - [🧠 Service Intelligence](#-service-intelligence)
    - [Clean and process HTML (remove scripts, comments, styles)](#clean-and-process-html-remove-scripts-comments-styles)
    - [Extract text content from HTML](#extract-text-content-from-html)
    - [Extract title from HTML](#extract-title-from-html)

---

# Service Overview

| Service | Primary Function | Key Formats | Output Formats |
|---------|------------------|-------------|----------------|
| **Unstructured IO** | Document structure extraction | PDF, DOCX, DOC, ODT, PPTX, PPT, XLSX, CSV, TSV, EML, MSG, RTF, EPUB, HTML, XML, PNG, JPG, HEIC, TXT | JSON (structure extraction) |
| **LibreOffice** | Office document conversion | Extensive office formats (DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP, etc.) | PDF, HTML, DOCX, ODT, and many others |
| **Pandoc** | Universal document conversion | Markdown, HTML, LaTeX, DOCX, ODT, RST, AsciiDoc, and 40+ formats | PDF, HTML, DOCX, LaTeX, Markdown, and 50+ formats |
| **WeasyPrint** | High-quality HTML to PDF conversion | HTML, URLs | PDF (with full CSS support) |
| **Gotenberg** | HTML and office document to PDF conversion | HTML, URLs, DOCX, XLSX, PPTX, and other office formats | PDF |
| **Mammoth** | DOCX to HTML conversion | DOCX | HTML (semantic conversion) |
| **html4docx** | HTML to DOCX conversion | HTML | DOCX (with formatting preservation) |
| **BeautifulSoup** | HTML cleaning and processing | HTML | HTML (cleaned and processed) |

## Master Format Support Matrix

| Input → Output | PDF | DOCX | HTML | MD | TEX | TXT | JSON | ODT | PPTX | ODP |
|----------------|-----|------|------|----|-----|-----|------|-----|------|-----|
| .asciidoc | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .csv | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ |
| .dbf | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ | ❌ |
| .doc | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .docx | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| .eml | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ |
| .epub | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .fb2 | ✅* | ❌ | ✅* | ✅* | ❌ | ✅* | ❌ | ❌ | ❌ | ❌ |
| .gnumeric | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ | ❌ |
| .heic | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ |
| .html | ✅ | ✅ | ✅** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| .jpg | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ |
| .key | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ❌ | ❌ | ✅ | ✅ |
| .latex | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .md | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| .msg | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ |
| .numbers | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .odp | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| .ods | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| .odt | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .org | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .pages | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .parquet | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ | ❌ |
| .pdf | ❌ | ✅ | ✅* | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .png | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ | ❌ |
| .ppt | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .pptx | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .rst | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .rtf | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .tex | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| .textile | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .tsv | ✅* | ❌ | ✅* | ❌ | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ |
| .txt | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| .url | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| .wiki | ✅* | ❌ | ✅* | ❌ | ✅* | ✅* | ❌ | ❌ | ❌ | ❌ |
| .xls | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| .xlsx | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |


> **Notes**: 
> - `✅*` indicates that the format pair is supported by the underlying services but does **not** have a dedicated `/convert/*` endpoint. These conversions are only accessible by directly calling the proxied service endpoints (refer to individual service documentation for syntax). Service names marked with `*` in the conversion tables also indicate missing `/convert/*` endpoints for those specific conversions.
> - `✅**` html`→`html` is a cleanup conversion.  It will fix malformed HTML.
> - **URL Input**: URL in/out conversions are generally anything supported in the matrix.

## Comprehensive Format Support

### Text Documents
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Microsoft Word | .doc | ✅ | ✅ | ❌ | ❌ | Legacy format, good support |
| Word 2007+ | .docx | ✅ | ✅ | ✅ | ✅ | Universal support |
| OpenDocument Text | .odt | ✅ | ✅ | ✅ | ❌ | Open standard |
| Rich Text Format | .rtf | ✅ | ✅ | ❌ | ❌ | Limited conversion options |
| Plain Text | .txt | ✅ | ✅ | ✅ | ❌ | Universal support |
| HTML | .html | ✅ | ✅ | ✅ | ✅ | Web publishing - Gotenberg can convert HTML to PDF with full CSS support, BeautifulSoup provides HTML cleaning and processing |
| Markdown | .md | ❌ | ❌ | ✅ | ❌ | Pandoc native |
| LaTeX | .tex | ❌ | ❌ | ✅ | ❌ | Academic publishing |
| reStructuredText | .rst | ❌ | ❌ | ✅* | ❌ | Python documentation |
| AsciiDoc | .asciidoc | ❌ | ❌ | ✅* | ❌ | Technical writing |
| MediaWiki | .wiki | ❌ | ❌ | ✅* | ❌ | Wiki markup |
| Textile | .textile | ❌ | ❌ | ✅* | ❌ | Lightweight markup |
| Org Mode | .org | ❌ | ❌ | ✅* | ❌ | Emacs format |
| FictionBook | .fb2 | ❌ | ✅* | ✅* | ❌ | E-book format |

### Spreadsheets
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Excel 97-2003 | .xls | ❌ | ✅ | ❌ | ✅ | Legacy format - Gotenberg supports via LibreOffice |
| Excel 2007+ | .xlsx | ✅ | ✅ | ❌ | ✅ | Modern Excel - Gotenberg supports via LibreOffice |
| OpenDocument Spreadsheet | .ods | ❌ | ✅ | ❌ | ❌ | Open standard |
| Apple Numbers | .numbers | ❌ | ✅ | ❌ | ❌ | macOS spreadsheet - dedicated conversion endpoints available |
| CSV | .csv | ✅* | ✅* | ✅* | ❌ | Universal data format |
| TSV | .tsv | ✅* | ✅* | ✅* | ❌ | Tab-separated values |
| dBase | .dbf | ❌ | ✅* | ❌ | ❌ | Database format |
| Apache Parquet | .parquet | ❌ | ✅* | ❌ | ❌ | Big data format |
| Gnumeric | .gnumeric | ❌ | ✅* | ❌ | ❌ | GNOME spreadsheet |

### Presentations
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| PowerPoint 97-2003 | .ppt | ✅ | ✅ | ❌ | ✅ | Legacy format - Gotenberg supports via LibreOffice |
| PowerPoint 2007+ | .pptx | ✅ | ✅ | ❌ | ✅ | Modern PowerPoint - Gotenberg supports via LibreOffice |
| OpenDocument Presentation | .odp | ❌ | ✅ | ❌ | ❌ | Open standard - dedicated conversion endpoints available |
| Apple Keynote | .key | ❌ | ✅* | ❌ | ❌ | macOS format |

### E-books and Publishing
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| EPUB | .epub | ✅ | ✅ | ✅ | ❌ | E-book standard |
| FictionBook 2.0 | .fb2 | ❌ | ✅* | ✅* | ❌ | Russian e-book format |

### Email and Communications
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| Email Message | .eml | ✅* | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| Outlook Message | .msg | ✅* | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |

### Images and Graphics
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| PNG | .png | ✅* | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| JPEG | .jpg, .jpeg | ✅* | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |
| HEIC | .heic | ✅* | ❌ | ❌ | ❌ | **GAP**: No conversion to document formats |

### Legacy and Specialized Formats
| Format | Extension | Unstructured IO | LibreOffice | Pandoc | Gotenberg | Notes |
|--------|-----------|----------------|-------------|--------|-----------|-------|
| WordPerfect | .wpd | ❌ | ✅* | ❌ | ❌ | Legacy word processor |
| Microsoft Works | .wps, .wdb | ❌ | ✅* | ❌ | ❌ | Old office suite |
| Microsoft Write | .wri | ❌ | ✅* | ❌ | ❌ | Very old format |
| MacWrite | .mcw, .mwd | ❌ | ✅* | ❌ | ❌ | Classic Mac format |
| WriteNow | .wn | ❌ | ✅* | ❌ | ❌ | Old Mac format |
| Palm Doc | .pdb | ❌ | ✅* | ❌ | ❌ | PDA format |
| Pocket Word | .psw | ❌ | ✅* | ❌ | ❌ | Windows CE format |
| WordPerfect Graphics | .wpg | ❌ | ✅* | ❌ | ❌ | Vector graphics |
| Microsoft Publisher | .pub | ❌ | ✅* | ❌ | ❌ | Desktop publishing |
| Corel Draw | .cdr | ❌ | ✅* | ❌ | ❌ | Vector graphics |
| Freehand | .fh | ❌ | ✅* | ❌ | ❌ | Vector graphics |
| PageMaker | .p65, .pm, .pmd | ❌ | ✅* | ❌ | ❌ | Desktop publishing |
| QuarkXPress | .qxd, .qxt | ❌ | ✅* | ❌ | ❌ | Desktop publishing |
| Zoner Draw | .zmf | ❌ | ✅* | ❌ | ❌ | Vector graphics |

## Output Format Support

### Primary Output Formats
| Format | Unstructured IO | LibreOffice | Pandoc | Gotenberg | WeasyPrint | Mammoth |
|--------|----------------|-------------|--------|-----------|------------|---------|
| PDF | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| HTML | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ |
| DOCX | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| ODT | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| PPTX | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| ODP | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Markdown | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| LaTeX | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Plain Text | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| JSON | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| XLSX | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |

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

5. **Presentation to Document Conversion**
   - **Problem**: PPT and PPTX files cannot be directly converted to DOCX format
   - **Gap**: No service currently supports presentation-to-document format conversion
   - **Impact**: PowerPoint presentations cannot be converted to Word documents
   - **Workaround**: Convert to PDF, HTML, or extract text content instead

6. **Specialized Application Formats**
   - **Problem**: Formats like .pub, .cdr, .qxd have limited conversion options
   - **Gap**: Complex layouts and graphics may not convert well
   - **Impact**: Professional publishing documents may lose quality

### Service-Specific Limitations
7. **Unstructured IO Limitations**
   - Only outputs JSON structure extraction
   - Cannot convert between document formats
   - Limited to text and metadata extraction

8. **LibreOffice Limitations**
   - Best for office document formats
   - Limited support for modern markup formats (Markdown, AsciiDoc, etc.)
   - Some legacy formats may have conversion issues

9. **Pandoc Limitations**
   - Requires text-based input formats
   - Cannot process binary office documents directly (needs LibreOffice preprocessing)
   - Limited support for complex layouts and embedded objects

10. **Gotenberg Limitations**
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
- `tex`, `latex` - Academic content
- `txt` - Plain text
- `pages` - Apple Pages documents
- `numbers` - Apple Numbers spreadsheets
- `url` - Web URLs

### Priority Output Formats
- `pdf` - Universal document format
- `docx` - Modern Word format
- `html` - Web format
- `md` - Markdown
- `xlsx` - Modern Excel format
- `txt` - Plain text
- `json` - Structured data
- `odt` - OpenDocument Text
- `pptx` - Modern PowerPoint format
- `odp` - OpenDocument Presentation

## 📋 Complete Conversion Matrix

### PDF Output Conversions (High Priority)

| Input → PDF | Primary Service | Description |
|-------------|----------------|-------------|
| `docx-pdf` | Gotenberg | DOCX to PDF |
| `pptx-pdf` | Gotenberg | PPTX to PDF |
| `ppt-pdf` | LibreOffice | PPT to PDF |
| `html-pdf` | Gotenberg/WeasyPrint | HTML to PDF (Gotenberg for basic, WeasyPrint for CSS) |
| `md-pdf` | Pandoc | Markdown to PDF |
| `tex-pdf` | Pandoc | LaTeX to PDF |
| `latex-pdf` | Pandoc | LaTeX to PDF |
| `txt-pdf` | LibreOffice | Text to PDF |
| `rtf-pdf` | LibreOffice | RTF to PDF |
| `odt-pdf` | LibreOffice | ODT to PDF |
| `xlsx-pdf` | Gotenberg | XLSX to PDF |
| `xls-pdf` | LibreOffice | XLS to PDF |
| `ods-pdf` | LibreOffice | ODS to PDF |
| `numbers-pdf` | LibreOffice | Numbers to PDF |
| `odp-pdf` | LibreOffice | ODP to PDF |
| `epub-pdf` | LibreOffice | EPUB to PDF |
| `pages-pdf` | LibreOffice | Apple Pages to PDF |
| `key-pdf` | LibreOffice | Apple Keynote to PDF |
| `url-pdf` | Gotenberg/WeasyPrint | URL to PDF |

### JSON Structure Extraction

| Input → JSON | Primary Service | Description |
|--------------|----------------|-------------|
| `docx-json` | Unstructured IO | DOCX structure extraction |
| `pdf-json` | Unstructured IO | PDF structure extraction |
| `pptx-json` | Unstructured IO | PPTX structure extraction |
| `ppt-json` | Unstructured IO | PPT structure extraction |
| `xlsx-json` | Unstructured IO | XLSX structure extraction |
| `html-json` | Unstructured IO | HTML structure extraction |
| `epub-json` | Unstructured IO | EPUB structure extraction |
| `rtf-json` | Unstructured IO | RTF structure extraction |
| `txt-json` | Unstructured IO | Text structure extraction |
| `numbers-json` | Unstructured IO | Numbers structure extraction |
| `latex-json` | Unstructured IO | LaTeX structure extraction |
| `tex-json` | Unstructured IO | LaTeX structure extraction |
| `eml-json` | Unstructured IO* | Email structure extraction |
| `msg-json` | Unstructured IO* | Outlook message extraction |
| `odp-json` | Unstructured IO | ODP structure extraction (chained: ODP → PPTX → JSON) |

### URL-Based Conversions

| URL → Output | Primary Service | Description |
|--------------|----------------|-------------|
| `url-pdf` | Gotenberg | URL to PDF |
| `url-json` | Unstructured IO | URL content structure |
| `url-md` | Unstructured IO | URL to Markdown |
| `url-txt` | Unstructured IO | URL to plain text |
| `url-html` | Local | URL to HTML |

### DOCX Output Conversions

| Input → DOCX | Primary Service | Description |
|--------------|----------------|-------------|
| `md-docx` | Pandoc | Markdown to DOCX |
| `html-docx` | LibreOffice | HTML to DOCX |
| `pdf-docx` | LibreOffice* | PDF to DOCX |
| `rtf-docx` | LibreOffice | RTF to DOCX |
| `txt-docx` | LibreOffice | Text to DOCX |
| `odt-docx` | LibreOffice | ODT to DOCX |
| `pages-docx` | LibreOffice | Apple Pages to DOCX |
| `latex-docx` | Pandoc | LaTeX to DOCX |
| `tex-docx` | Pandoc | LaTeX to DOCX |
| `url-docx` | LibreOffice/Pandoc | URL to DOCX |

### PPTX Output Conversions

| Input → PPTX | Primary Service | Description |
|--------------|----------------|-------------|
| `odp-pptx` | LibreOffice | ODP to PPTX |
| `ppt-pptx` | LibreOffice | PPT to PPTX |
| `key-pptx` | LibreOffice | Apple Keynote to PPTX |

### Markdown Output Conversions

| Input → MD | Primary Service | Description |
|------------|----------------|-------------|
| `docx-md` | Pandoc | DOCX to Markdown |
| `html-md` | Pandoc | HTML to Markdown |
| `pdf-md` | Unstructured IO | PDF to Markdown |
| `tex-md` | Pandoc | LaTeX to Markdown |
| `latex-md` | Pandoc | LaTeX to Markdown |
| `rtf-md` | Pandoc | RTF to Markdown |
| `txt-md` | Pandoc | Text to Markdown |
| `epub-md` | Pandoc | EPUB to Markdown |
| `pages-md` | LibreOffice | Apple Pages to Markdown |
| `numbers-md` | Unstructured IO | Numbers to Markdown |
| `odp-md` | Unstructured IO | ODP to Markdown (chained: ODP → PPTX → Markdown) |

### HTML Output Conversions

| Input → HTML | Primary Service | Description |
|--------------|----------------|-------------|
| `html-html` | BeautifulSoup | HTML cleaning and processing (remove scripts, comments, styles) |
| `docx-html` | LibreOffice/Mammoth | DOCX to HTML (LibreOffice for basic, Mammoth for semantic) |
| `pdf-html` | LibreOffice | PDF to HTML |
| `md-html` | Pandoc | Markdown to HTML |
| `tex-html` | Pandoc | LaTeX to HTML |
| `latex-html` | Pandoc | LaTeX to HTML |
| `rtf-html` | LibreOffice | RTF to HTML |
| `txt-html` | LibreOffice | Text to HTML |
| `odt-html` | LibreOffice | ODT to HTML |
| `xlsx-html` | LibreOffice | XLSX to HTML |
| `xls-html` | LibreOffice | XLS to HTML |
| `numbers-html` | LibreOffice | Numbers to HTML |
| `ppt-html` | LibreOffice | PPT to HTML |
| `pptx-html` | LibreOffice | PPTX to HTML |
| `odp-html` | LibreOffice | ODP to HTML |
| `ods-html` | LibreOffice | ODS to HTML |
| `pages-html` | LibreOffice | Apple Pages to HTML |
| `key-html` | LibreOffice | Apple Keynote to HTML |
| `url-html` | Local | URL to HTML |

### LaTeX Output Conversions

| Input → TEX | Primary Service | Description |
|-------------|----------------|-------------|
| `md-tex` | Pandoc* | Markdown to LaTeX |
| `html-tex` | Pandoc* | HTML to LaTeX |
| `docx-tex` | Pandoc* | DOCX to LaTeX |
| `txt-tex` | Pandoc* | Text to LaTeX |

### Plain Text Output Conversions

| Input → TXT | Primary Service | Description |
|-------------|----------------|-------------|
| `docx-txt` | LibreOffice* | DOCX to Text |
| `pdf-txt` | Unstructured IO | PDF to Text |
| `html-txt` | Unstructured IO | HTML to Text |
| `md-txt` | Pandoc | Markdown to Text |
| `rtf-txt` | LibreOffice | RTF to Text |
| `pages-txt` | LibreOffice | Apple Pages to Text |
| `numbers-txt` | Unstructured IO | Numbers to Text |
| `odp-txt` | Unstructured IO | ODP to Text (chained: ODP → PPTX → Text) |

## XLSX Output Conversions

| Input → XLSX | Primary Service | Description |
|--------------|----------------|-------------|
| `numbers-xlsx` | LibreOffice | Numbers to XLSX |

## ODT Output Conversions

| Input → ODT | Primary Service | Description |
|-------------|----------------|-------------|
| `docx-odt` | LibreOffice | DOCX to ODT |
| `html-odt` | LibreOffice | HTML to ODT |
| `pdf-odt` | LibreOffice* | PDF to ODT |
| `rtf-odt` | LibreOffice | RTF to ODT |
| `txt-odt` | LibreOffice | Text to ODT |
| `doc-odt` | LibreOffice | DOC to ODT |
| `pptx-odt` | LibreOffice* | PPTX to ODT |
| `url-odt` | LibreOffice | URL to ODT |

## PPTX Output Conversions

| Input → PPTX | Primary Service | Description |
|--------------|----------------|-------------|
| `odp-pptx` | LibreOffice | ODP to PPTX |
| `ppt-pptx` | LibreOffice | PPT to PPTX |
| `key-pptx` | LibreOffice | Apple Keynote to PPTX |

## 💡 Usage Examples

### Convert a DOCX Resume to PDF

```bash
curl -X POST "http://localhost:8369/convert/docx-pdf" -F "file=@resume.docx" -o resume.pdf
```

### Extract PDF Structure

```bash
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -o document-structure.json
```

### Convert URL to PDF

```bash
curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -o webpage.pdf
```

### Convert URL to HTML

```bash
curl -X POST "http://localhost:8369/convert/url-html" -F "url=https://example.com" -o webpage.html
```

### Convert Markdown to DOCX

```bash
curl -X POST "http://localhost:8369/convert/md-docx" -F "file=@document.md" -o document.docx
```

### Dynamic Endpoint Examples

The API supports dynamic endpoints for any supported conversion pair:

```bash
# Dynamic file conversion - any supported format pair
curl -X POST "http://localhost:8369/convert/docx-pdf" -F "file=@document.docx" -o document.pdf
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -o structure.json
curl -X POST "http://localhost:8369/convert/md-docx" -F "file=@document.md" -o document.docx
curl -X POST "http://localhost:8369/convert/html-pdf" -F "file=@webpage.html" -o webpage.pdf

# Dynamic URL conversion - any supported output format
curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -o webpage.pdf
curl -X POST "http://localhost:8369/convert/url-md" -F "url=https://example.com" -o webpage.md
curl -X POST "http://localhost:8369/convert/url-json" -F "url=https://example.com" -o webpage.json

# Dynamic URL conversion with custom User-Agent
curl -X POST "http://localhost:8369/convert/url-pdf" \
  -F "url=https://example.com" \
  -F "user_agent=Mozilla/5.0 (compatible; MyBot/1.0)" \
  -o webpage.pdf
```

### List All Supported Conversions

```bash
curl http://localhost:8369/convert/supported
```

## 🧠 Service Intelligence

Each endpoint automatically selects the optimal service:

- **PDF Output**: Gotenberg (highest quality for office documents) or WeasyPrint (highest quality for HTML/CSS rendering) or LibreOffice (fallback)
- **JSON Output**: Unstructured IO (best structure extraction)
- **DOCX Output**: LibreOffice (office formats) or Pandoc (markup formats)
- **HTML Output**: Mammoth (DOCX for semantic conversion) or LibreOffice (other office formats) or Pandoc (markup formats) or BeautifulSoup (HTML cleaning and processing)
- **HTML Processing**: BeautifulSoup (cleaning, text extraction, title extraction)
- **Markdown/LaTeX**: Pandoc (native support)
- **Legacy Formats**: LibreOffice (broadest compatibility)
- **URL Input**: Gotenberg for PDF, Unstructured IO for JSON/Markdown/Text, WeasyPrint for high-quality HTML-to-PDF
- **Text Processing**: Unstructured IO (structure extraction) or LibreOffice/Pandoc (format conversion)

---

> **⚠️ Note on Functionally Useless Conversions**: Some conversions may produce output that is functionally identical to the input. For example:
> - `txt-md`: Plain text to Markdown often results in identical output since plain text lacks Markdown-specific formatting
> - `txt-tex`: Plain text to LaTeX often results in identical output since plain text lacks LaTeX-specific markup
> - `md-txt`: Markdown to plain text may strip all formatting, resulting in identical content
> 
> These conversions are still available for completeness but may not provide meaningful transformation. Always verify the output quality for your specific use case.

### Clean and process HTML (remove scripts, comments, styles)
```bash
curl -X POST "http://localhost:8369/convert/html-html" \
  -F "file=@messy.html" \
  -F "remove_scripts=true" \
  -F "remove_comments=true" \
  -F "remove_styles=true" \
  -F "prettify=true" \
  -o clean.html
```

### Extract text content from HTML
```bash
curl -X POST "http://localhost:8369/convert/html-html" \
  -F "file=@webpage.html" \
  -F "extract_text=true" \
  -F "prettify=false" \
  -o webpage.txt
```

### Extract title from HTML
```bash
curl -X POST "http://localhost:8369/convert/html-html" \
  -F "file=@webpage.html" \
  -F "extract_title=true" \
  -o title.txt
```

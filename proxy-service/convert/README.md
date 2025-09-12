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

### Dynamic Conversion Endpoints

#### File Conversions
- `POST /{input_format}-{output_format}` - Convert uploaded files between any supported formats
- `POST /url-{output_format}` - Convert URLs to any supported output format

#### Utility Endpoints
- `GET /supported` - Get all supported conversion format pairs
- `GET /url-info/{input_format}-{output_format}` - Get information about URL conversion capabilities
- `POST /validate-url` - Validate a URL and its content format for conversion
- `GET /validate-url` - Validate a URL (GET method alternative)

### Priority Endpoints (High-Level Aliases)

#### PDF Output Conversions (High Priority)
| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-pdf` | DOCX to PDF | Gotenberg | Resume/CV conversion |
| `POST /convert/pptx-pdf` | PPTX to PDF | Gotenberg | Presentation conversion |
| `POST /convert/html-pdf` | HTML to PDF | WeasyPrint/Gotenberg | Web content to PDF |
| `POST /convert/md-pdf` | Markdown to PDF | Pandoc | Text content to PDF |
| `POST /convert/url-pdf` | URL to PDF | WeasyPrint/Gotenberg | Web page archiving |

#### JSON Structure Extraction
| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/docx-json` | DOCX to JSON | Unstructured IO | Document analysis |
| `POST /convert/pdf-json` | PDF to JSON | Unstructured IO | Document analysis |
| `POST /convert/url-json` | URL to JSON | Unstructured IO | Web content analysis |

#### Other Conversions
| Endpoint | Description | Primary Service | Use Case |
|----------|-------------|----------------|----------|
| `POST /convert/md-docx` | Markdown to DOCX | Pandoc | Document creation |
| `POST /convert/docx-html` | DOCX to HTML | Mammoth/LibreOffice | Document conversion |
| `POST /convert/url-md` | URL to Markdown | Unstructured IO | Content extraction |
| `POST /convert/url-txt` | URL to Text | Unstructured IO | Text extraction |

## Service Selection Logic

Each endpoint automatically selects the most reliable service based on:

1. **Quality**: Highest fidelity conversion
2. **Reliability**: Most stable service for the format pair
3. **Performance**: Best balance of speed and quality
4. **Format Support**: Comprehensive coverage of format features
5. **Content Type**: Automatic detection for URL inputs

### Primary Service Preferences

- **PDF Output**: 
  - Gotenberg (highest quality for office documents)
  - WeasyPrint (highest quality for HTML/CSS rendering)
  - LibreOffice (fallback for other formats)
  - Pandoc (for markup formats)
- **JSON Output**: Unstructured IO (best structure extraction)
- **DOCX Output**: LibreOffice (office formats) or Pandoc (markup formats)
- **HTML Output**: 
  - Mammoth (DOCX for semantic conversion)
  - LibreOffice (other office formats)
  - Pandoc (markup formats)
- **Markdown/LaTeX**: Pandoc (native support)
- **Legacy Formats**: LibreOffice (broadest compatibility)
- **URL Input**: 
  - Gotenberg for PDF
  - WeasyPrint for high-quality HTML-to-PDF
  - Unstructured IO for JSON/Markdown/Text
  - Local processing for HTML

### Dynamic Routing

The system uses intelligent routing based on:

- **Input format detection** (especially for URLs)
- **Service availability** and health
- **Conversion matrix** lookup
- **Fallback mechanisms** for failed conversions
- **Chained conversions** for complex format pairs

## Configuration

The conversion logic is defined in `config.py` and organized across several utility modules:

**Core Configuration (`config.py`)**:
- `CONVERSION_MATRIX`: Defines all supported conversion pairs and their service routing
- `SERVICE_URL_CONFIGS`: Service endpoint configurations for Docker vs local development
- `SPECIAL_HANDLERS`: Registry for custom conversion logic
- `ConversionService`: Enum defining available conversion services

**Utility Modules**:
- `utils/conversion_lookup.py`: Functions for looking up conversion methods and service URLs
- `utils/conversion_chaining.py`: Logic for multi-step chained conversions
- `utils/conversion_core.py`: Core conversion execution and service client management
- `utils/special_handlers.py`: Custom conversion handlers for special cases
- `utils/unstructured_utils.py`: Unstructured IO specific utilities
- `utils/url_processor.py`: URL fetching and processing utilities
- `utils/error_handling.py`: Centralized error handling and validation
- `utils/http_client.py`: HTTP client factory for service communication
- `utils/logging_config.py`: Centralized logging configuration
- `utils/temp_file_manager.py`: Temporary file management utilities
- `utils/mime_detector.py`: MIME type detection utilities

**Router (`router.py`)**:
- FastAPI route handlers for all `/convert/*` endpoints
- Dynamic endpoint pattern matching (`{input_format}-{output_format}`)
- URL processing integration
- Automatic service routing based on input/output format pairs
- Special case handling for complex conversions

The conversion system can be easily extended by:

1. **Adding new services** to the `ConversionService` enum
2. **Defining new conversions** in the `CONVERSION_MATRIX`
3. **Creating special handlers** for complex conversion logic
4. **Adding format detection** for new input types

## Usage Examples

### Dynamic Endpoints

#### File Conversion (Dynamic)
```bash
# Convert any supported format pair
curl -X POST "http://localhost:8369/convert/docx-pdf" -F "file=@document.docx" -o document.pdf
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -o structure.json
curl -X POST "http://localhost:8369/convert/md-docx" -F "file=@document.md" -o document.docx
curl -X POST "http://localhost:8369/convert/html-pdf" -F "file=@webpage.html" -o webpage.pdf
```

#### URL Conversion (Dynamic)
```bash
# Convert URLs to any supported output format
curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -o webpage.pdf
curl -X POST "http://localhost:8369/convert/url-md" -F "url=https://example.com" -o webpage.md
curl -X POST "http://localhost:8369/convert/url-json" -F "url=https://example.com" -o webpage.json
curl -X POST "http://localhost:8369/convert/url-txt" -F "url=https://example.com" -o webpage.txt
```

#### URL Conversion with Custom User-Agent
```bash
curl -X POST "http://localhost:8369/convert/url-pdf" \
  -F "url=https://example.com" \
  -F "user_agent=Mozilla/5.0 (compatible; MyBot/1.0)" \
  -o webpage.pdf
```

### Legacy High-Level Endpoints

#### Convert a DOCX Resume to PDF
```bash
curl -X POST "http://localhost:8369/convert/docx-pdf" \
  -F "file=@resume.docx" \
  -o resume.pdf
```

#### Convert a Markdown Cover Letter to DOCX
```bash
curl -X POST "http://localhost:8369/convert/md-docx" \
  -F "file=@cover-letter.md" \
  -o cover-letter.docx
```

#### Extract Structure from a PDF
```bash
curl -X POST "http://localhost:8369/convert/pdf-json" \
  -F "file=@document.pdf" \
  -o document-structure.json
```

#### Convert HTML Content to PDF
```bash
curl -X POST "http://localhost:8369/convert/html-pdf" \
  -F "file=@webpage.html" \
  -o webpage.pdf
```

### Utility Endpoints

#### List All Supported Conversions
```bash
curl http://localhost:8369/convert/supported
```

#### Get Conversion Information
```bash
curl http://localhost:8369/convert/url-info/html-pdf
```

#### Validate a URL for Conversion
```bash
curl -X POST "http://localhost:8369/convert/validate-url" \
  -d "url=https://example.com"
```

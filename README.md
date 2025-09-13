# AppLite Xtrac - Multi-Service Document Processing API

This project provides a unified API gateway for multiple document processing services using Docker and docker-compose.

## Goals

1. To extract the best semantic representation of common documents and output it for ETL
or LLM pipelines.
1. To convert well-structured and formatted HTML to PDF (via Gotenberg) or docx (via Unoserver, Pandoc, or html4docx).  Although these are the emphasis, many other input and output formats are supported.
2. To convert between popular formats or at least to popular formats from outdated or unpopular ones (right `.pages`!?).

## Services

- **Unstructured IO** (`/unstructured-io`): Document structure extraction and processing using the official Unstructured API
- **LibreOffice Unoserver** (`/libreoffice`): Document conversion using LibreOffice headless server
- **PyConvert API** (`/pyconvert`): Document format conversion with PDF support via FastAPI service (includes Pandoc, WeasyPrint, and Mammoth)
- **Gotenberg** (`/gotenberg`): High-fidelity HTML to PDF conversion, including support for URLs and office documents
- **Local Proxy**: In addition to handling proxying for the other services, this container has some smaller or manually-defined conversion services.

## Architecture

Platform: Linux

The main proxy service runs on a configurable port (default: 8369) and routes requests based on URL prefixes or patterns:

**Proxied sub-containers**:

Proxying to these containers aims to preserve the original functionality of the containers.  The documented features of these projects should all function as expected, but with the proxy URL prefix.

- `/unstructured-io/*` → Unstructured IO API (port 8000)
- `/libreoffice/*` → LibreOffice API (port 2004)
- `/gotenberg/*` → Gotenberg API (port 3001)
- `/pyconvert/*` → PyConvert API (port 3030) - has child services for Pandoc, WeasyPrint, and Mammoth

**Helper endpoints**:

- `/convert/{input-format}-{output-format}` → High-level conversion aliases (auto-routing)
- `/convert/url-{output-format}` → URL-to-format conversion
- `/ping` → General health check
- `/ping-all` → General health check - All container services
- `/{service}/ping` → Service-specific health check
- `/docs` → API documentation

**Markdown and txt format outputs for services**: 

- `/unstructured-io-md` → Normal Unstructured IO input file with markdown output
- `/unstructured-io-txt` → Normal Unstructured IO input file with text output
- `/libreoffice-md` → Normal LibreOffice input file with markdown output.  `-txt` isn't handled because LibreOffice can output that regularly.


**Proxy Features:**
- Supports all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)
- Streaming responses for large files
- Automatic header filtering (removes hop-by-hop headers)
- Request/response body forwarding
- Query parameter preservation

## Quick Start

1. Clone this repository
2. **For Docker**: Ensure Docker and docker-compose are installed
3. Run `docker-compose up --build`
4. The API will be available at `http://localhost:8369` (or your configured port via `APPLITEXTRAC_PORT`)

### Test Health Checks

```bash
# General ping (replace 8369 with your configured port)
curl http://localhost:8369/ping

# Comprehensive health check
curl http://localhost:8369/ping-all

# Individual service health checks
curl http://localhost:8369/unstructured-io/ping
curl http://localhost:8369/libreoffice/ping
curl http://localhost:8369/pyconvert/ping
curl http://localhost:8369/gotenberg/ping
```

### Alternative: Using the Helper Script

For easier management, use the provided script:

```bash
# Activate Python virtual environment
./run.sh activate

# Start services
./run.sh start
./run.sh up

# Start in background
./run.sh startd
./run.sh up-d

# Build services
./run.sh build

# View logs
./run.sh logs <service>

# Check status
./run.sh status
./run.sh health
./run.sh ps

# Restart services
./run.sh restart
./run.sh restartd

# Development mode (recommended for development)
./run.sh dev

# Stop development mode
./run.sh dev:stop

# Run tests
./run.sh test
./run.sh test:conversion
./run.sh test:url

# Update Docker images
./run.sh update

# Show resource usage
./run.sh resources

# Stop services
./run.sh stop
./run.sh down

# Clean up
./run.sh clean
```

### Network Security

**External Access:**
- Only the configured proxy port is exposed to the outside world (default: `8369`)
- All other services run on an isolated internal network

**Internal Network:**
- Services communicate via the `app-network` bridge network
- Individual service ports (8000, 2004, 3030, 3001) are not accessible externally
- All external requests must go through the proxy service

## Conversion Endpoints

The API provides high-level conversion aliases at `/convert/*` that automatically route to the most reliable service for each conversion type. These endpoints are optimized for common document workflows, especially **resume/CV/cover letter** processing.

### Priority Formats (Documents)

**Input Formats:** _\<http(s) URL\>_, `pptx`, `ppt`, `docx`, `odt`, `rtf`, `txt`, `html`, `md`, `tex`, `latex`, `pages`, `numbers`, `xlsx`, `xls`, `ods`, `odp`, `epub`, `eml`, `msg`  
**Output Formats:** `pdf`, `docx`, `html`, `md`, `txt`, `json`, `tex`, `xlsx`

### 📖 Further Documentation

For comprehensive information about all available conversion endpoints, usage examples, service selection logic, and configuration details, see **[docs/FORMATS.md](docs/FORMATS.md#🔄-conversion-api-endpoints)**.

For detailed information about URL fetching capabilities, Scrapy integration, and remote content processing, see **[docs/URL_FETCHING.md](docs/URL_FETCHING.md)**.

### Quick Examples

**Note:** Replace `8369` with your configured port if using `APPLITEXTRAC_PORT`.

**Convert DOCX to PDF:**
```bash
curl -X POST "http://localhost:8369/convert/docx-pdf" -F "file=@resume.docx" -o resume.pdf
```

**Extract PDF structure:**
```bash
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -o structure.json
```

**Convert URL to PDF:**
```bash
curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -o webpage.pdf
```

**Extract URL content structure:**
```bash
curl -X POST "http://localhost:8369/convert/url-json" -F "url=https://example.com" -o webpage.json
```

**Convert URL to Markdown:**
```bash
curl -X POST "http://localhost:8369/convert/url-md" -F "url=https://example.com" -o webpage.md
```

**Convert URL to plain text:**
```bash
curl -X POST "http://localhost:8369/convert/url-txt" -F "url=https://example.com" -o webpage.txt
```

**Convert Markdown to DOCX:**
```bash
curl -X POST "http://localhost:8369/convert/md-docx" -F "file=@document.md" -o document.docx
```

**Convert Apple Pages to PDF:**
```bash
curl -X POST "http://localhost:8369/convert/pages-pdf" -F "file=@document.pages" -o document.pdf
```

**Convert Excel to PDF:**
```bash
curl -X POST "http://localhost:8369/convert/xlsx-pdf" -F "file=@spreadsheet.xlsx" -o spreadsheet.pdf
```

**List all supported conversions:**
```bash
curl http://localhost:8369/convert/supported
```

**Get conversion details:**
```bash
curl http://localhost:8369/convert/info/docx-pdf
```

### Dynamic Endpoint Pattern

The API supports dynamic endpoints for any supported conversion pair using the pattern `/convert/{input_format}-{output_format}`:

**Supported Dynamic Conversions:**
- `POST /convert/{input_format}-{output_format}` - Convert files between any supported formats
- `POST /convert/url-{output_format}` - Convert URLs to any supported output format

**Examples:**
```bash
# Dynamic file conversion
curl -X POST "http://localhost:8369/convert/docx-pdf" -F "file=@document.docx" -o document.pdf
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -o structure.json
curl -X POST "http://localhost:8369/convert/md-docx" -F "file=@document.md" -o document.docx

# Dynamic URL conversion
curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -o webpage.pdf
curl -X POST "http://localhost:8369/convert/url-md" -F "url=https://example.com" -o webpage.md

# Dynamic URL conversion with custom User-Agent
curl -X POST "http://localhost:8369/convert/url-pdf" \
  -F "url=https://example.com" \
  -F "user_agent=Mozilla/5.0 (compatible; MyBot/1.0)" \
  -o webpage.pdf
```

**Format Validation:**
- Input and output formats must be 2-7 characters long
- Conversion pair must be supported (use `/convert/supported` to check)
- Invalid formats return HTTP 400 with error details

**User-Agent Parameter:**
- `user_agent` (optional): Custom User-Agent string to send with URL requests
- If not provided, uses default browser-like User-Agent
- Useful for sites that block default User-Agents or require specific identification
- Applies to both Scrapy and requests-based fetching methods

### Parameter Passing

All conversion endpoints automatically accept and pass through parameters to the underlying services. This allows you to customize the behavior of the conversion services:

**Unstructured IO Parameters:**
```bash
# Use hi_res strategy for better accuracy
curl -X POST "http://localhost:8369/convert/pdf-md" -F "file=@document.pdf" -F "strategy=hi_res" -o document.md

# Use fast strategy for speed
curl -X POST "http://localhost:8369/convert/pdf-md" -F "file=@document.pdf" -F "strategy=fast" -o document.md

# Pass multiple parameters
curl -X POST "http://localhost:8369/convert/pdf-json" -F "file=@document.pdf" -F "strategy=hi_res" -F "coordinates=true" -o document.json
```

**Direct Service Access:**
You can also pass parameters directly to services through the proxy:

```bash
# Direct unstructured-io access with parameters
curl -X POST "http://localhost:8369/unstructured-io/general/v0/general" -F "files=@document.pdf" -F "strategy=hi_res" -F "output_format=text/markdown"
```

### Service Intelligence

Each endpoint automatically selects the optimal service:
- **PDF Output**: Gotenberg (highest quality for HTML/DOCX/PPTX/XLSX) or WeasyPrint (high-quality HTML/CSS rendering via pyconvert service)
- **JSON Output**: Unstructured IO (best structure extraction)
- **DOCX Output**: LibreOffice or Pandoc (format-specific optimization)
- **URL Input**: Gotenberg for PDF, Unstructured IO for JSON/Markdown/Text, WeasyPrint for high-quality HTML-to-PDF

### Additional Endpoints

- `GET /convert/supported` - List all available conversions
- `GET /convert/info/{input}-{output}` - Get conversion details

## API Endpoints

### General
- `GET /ping` - General health check
- `GET /ping-all` - Comprehensive health check for all services
  - Returns: `{"success": true/false, "data": "ALL_SERVICES_HEALTHY/SOME_SERVICES_UNHEALTHY", "services": {...}}`
- `GET /docs` - API documentation (dark mode enabled)

### Unstructured IO
- `GET /unstructured-io/ping` - Unstructured IO health check (uses `/general/v0/general` endpoint)
- `POST /unstructured-io/general/v0/general` - Document processing (proxied to Unstructured IO)

**Unstructured IO Integration:**
- Uses the official [Unstructured API](https://github.com/Unstructured-IO/unstructured-api) for document structure extraction
- Supports advanced document parsing and element extraction
- Handles complex document layouts and formats
- ⚠️Warning: Running OCR on documents rich with images will make memory usage and time to completion rise proportional to the number of pages.  For example: I ran a visually rich, ~90MB, ~1000 page PDF, which consumed a peak of 6.8GB RAM, and took ~1 hour to process (2022 era system). If you know that a document does not have images needing OCR, you can pass `strategy=fast` to speed up processing.

**Sample Request:**
```bash
# Process a document for structure extraction
curl -X POST "http://localhost:8369/unstructured-io/general/v0/general" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@document.pdf" \
  -F "strategy=hi_res" \
  | jq .
```

**Features:**
- Multiple parsing strategies (`fast`, `hi_res`, `ocr_only`, `auto`)
- Element type detection (titles, paragraphs, tables, etc.)
- Coordinate extraction for document layout
- Support for PDF, DOCX, and other document formats

### LibreOffice
- `GET /libreoffice/ping` - LibreOffice health check (uses `/` root endpoint)
- `POST /libreoffice/request` - Document conversion (proxied to LibreOffice)

**LibreOffice Integration:**
- Uses [libreoffice-unoserver](https://github.com/unoconv/libreoffice-unoserver) for headless document conversion
- Supports conversion between various office document formats
- Runs LibreOffice in server mode for better performance

**Sample Request:**
```bash
# Convert a document (example with curl)
curl -X POST "http://localhost:8369/libreoffice/request" \
  -F "file=@document.docx" \
  -F "convert-to=pdf" \
  -o converted_document.pdf
```

**Advanced Request with Options:**
```bash
# Convert with additional LibreOffice options
curl -X POST "http://localhost:8369/libreoffice/request" \
  -F "file=@document.docx" \
  -F "convert-to=pdf" \
  -F "opts[]=--landscape" \
  -F "opts[]=--paper=A4" \
  -o converted_document.pdf
```

**Supported Conversions:**
- DOCX → PDF
- XLSX → PDF  
- PPTX → PDF
- ODT → PDF
- And many other office document format conversions

### PyConvert
- `GET /pyconvert/ping` - PyConvert health check (uses `/ping` endpoint)
- `POST /pyconvert/pandoc` - Document conversion using Pandoc
  - **Supported formats**: `pdf`, `docx`, `html`, `txt`, `md`, `tex`
  - **Form data**: `file` (file upload), `output_format` (string), `extra_args` (optional string)
  - **Features**: Automatic cleanup, timeout handling (60s), background file processing
- `POST /pyconvert/weasyprint` - High-quality HTML to PDF conversion using WeasyPrint
  - **Supported inputs**: HTML files, URLs
  - **Features**: Full CSS support, custom styling, advanced PDF options
  - **Parameters**: All WeasyPrint write_pdf() parameters supported
- `POST /pyconvert/mammoth` - DOCX to HTML conversion using Mammoth
  - **Features**: Semantic HTML conversion, style preservation, clean output
- `POST /pyconvert/html4docx` - HTML to DOCX conversion using html4docx
  - **Features**: HTML formatting preservation, table support, list conversion, style mapping

**PyConvert Integration:**
- Uses [Pandoc](https://pandoc.org/) for universal document conversion
- Includes [WeasyPrint](https://weasyprint.org/) for high-quality HTML to PDF conversion
- Includes [Mammoth](https://github.com/mwilliamson/mammoth.js) for DOCX to HTML conversion
- Includes [html4docx](https://github.com/ReddyKilowatt/html-for-docx) for HTML to DOCX conversion
- Supports conversion between markup formats and office documents
- Includes LaTeX support for high-quality PDF generation

**Sample Requests:**
```bash
# Convert Markdown to PDF (via Pandoc)
curl -X POST "http://localhost:8369/pyconvert/pandoc" \
  -F "file=@document.md" \
  -F "output_format=pdf" \
  -o converted_document.pdf

# Convert HTML to PDF (via WeasyPrint - high quality)
curl -X POST "http://localhost:8369/pyconvert/weasyprint" \
  -F "file=@document.html" \
  -F 'stylesheets=["https://example.com/style.css"]' \
  -o high_quality_document.pdf

# Convert URL to PDF (via WeasyPrint)
curl -X POST "http://localhost:8369/pyconvert/weasyprint" \
  -F "url=https://example.com" \
  -F "zoom=1.5" \
  -o webpage.pdf

# Convert DOCX to HTML (via Mammoth)
curl -X POST "http://localhost:8369/pyconvert/mammoth" \
  -F "file=@document.docx" \
  -o document.html

# Convert HTML to DOCX (via html4docx)
curl -X POST "http://localhost:8369/pyconvert/html4docx" \
  -F "file=@document.html" \
  -o document.docx

# Convert with custom Pandoc arguments
curl -X POST "http://localhost:8369/pyconvert/pandoc" \
  -F "file=@document.md" \
  -F "output_format=pdf" \
  -F 'extra_args=--pdf-engine=pdflatex --variable geometry:margin=1in' \
  -o styled_document.pdf
```

**Common Conversions:**
- Markdown/HTML → PDF (with LaTeX via Pandoc)
- HTML → PDF (with full CSS support via WeasyPrint)
- HTML → DOCX (with formatting preservation via html4docx)
- DOCX → Markdown/HTML
- Various markup formats ↔ Office documents
- Text files with custom formatting

### Gotenberg
- `GET /gotenberg/ping` - Gotenberg health check (uses `/` root endpoint)
- `POST /gotenberg/forms/chromium/convert/html` - HTML to PDF conversion
- `POST /gotenberg/forms/chromium/convert/url` - URL to PDF conversion
- `POST /gotenberg/forms/libreoffice/convert` - Office document to PDF conversion

**Gotenberg Integration:**
- Uses [Gotenberg](https://gotenberg.dev/)** for high-quality PDF generation from HTML, URLs, and office documents
- Powered by Chromium for accurate HTML/CSS rendering
- Supports LibreOffice for office document conversion
- Stateless API design for scalability

**Sample Requests:**
```bash
# Convert HTML file to PDF
curl -X POST "http://localhost:8369/gotenberg/forms/chromium/convert/html" \
  -F "files=@index.html" \
  -F "files=@styles.css" \
  -o document.pdf

# Convert URL to PDF
curl -X POST "http://localhost:8369/gotenberg/forms/chromium/convert/url" \
  -F "url=https://example.com" \
  -o webpage.pdf

# Convert Office document to PDF
curl -X POST "http://localhost:8369/gotenberg/forms/libreoffice/convert" \
  -F "files=@document.docx" \
  -o converted.pdf

# Convert with custom options
curl -X POST "http://localhost:8369/gotenberg/forms/chromium/convert/html" \
  -F "files=@index.html" \
  -F "marginTop=1" \
  -F "marginBottom=1" \
  -F "marginLeft=1" \
  -F "marginRight=1" \
  -F "paperWidth=8.27" \
  -F "paperHeight=11.69" \
  -F "preferCSSPageSize=false" \
  -o styled_document.pdf
```

**Key Features:**
- High-fidelity HTML to PDF conversion with full CSS support
- URL to PDF conversion for web content
- Office document conversion (DOCX, XLSX, PPTX, etc.)
- Custom page margins and paper sizes
- Header and footer support
- Image and font embedding
- Asynchronous processing support

## Health Checks

Health checks are implemented for each service:
- General `/ping` returns static response
- `/ping-all` checks all services and returns comprehensive status
- Service-specific pings attempt to connect to the underlying service using real API endpoints:
  - **Unstructured IO**: Uses `/general/v0/general` endpoint (GET request, accepts 405 as healthy)
  - **LibreOffice**: Uses `/` root endpoint (accepts 404 as healthy)
  - **Pandoc**: Uses `/ping` custom endpoint
  - **Gotenberg**: Uses `/` root endpoint

## Development

### Building Individual Services

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build pyconvert
docker-compose build proxy
```

### Running Services

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs

# Stop services
docker-compose down
```

### Docker-Specific Commands

```bash
# List running containers
docker ps

# View container logs
docker logs <container_name>

# Access container shell
docker exec -it <container_name> /bin/bash

# Clean up
```

### Development Workflow

```bash
# Start development mode (recommended)
./run.sh dev

# View logs for specific service
./run.sh logs proxy
./run.sh logs pyconvert
./run.sh logs gotenberg

# Run tests
./run.sh test
./run.sh test:conversion

# Check service status
./run.sh status

# Stop development mode
./run.sh dev:stop
```

### Docker Configuration Optimization

The `docker-compose.yml` file has been optimized using YAML anchors and aliases to reduce duplication:

#### YAML Anchors Used:
- `&common-service`: Shared network configuration for all services
- `&service-template`: Template for services with standard port mapping (defined for future use)
- `&env-template`: Template for services with standard environment variables (defined for future use)
- `&restart-policy`: Standardized restart policy for services that need it

#### Benefits:
- **Reduced duplication**: Common configurations are defined once and reused
- **Easier maintenance**: Changes to shared configurations only need to be made in one place
- **Consistency**: All services follow the same patterns for networking and basic configuration
- **Scalability**: Easy to add new services following the established patterns

#### Example Usage:
```yaml
# All services inherit the common network configuration
services:
  proxy:
    <<: *common-service  # Inherits networks: [app-network]
    build: ./proxy-service
    ports:
      - "${APPLITEXTRAC_PORT:-8369}:8369"
```

### Local Python Development

For local development without containers, you can run the Python services directly using a virtual environment.

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r proxy-service/requirements.txt
   pip install fastapi uvicorn python-multipart  # for pyconvert-service if needed
   ```

4. Run the services:
   ```bash
   # Run proxy service (in one terminal)
   cd proxy-service
   uvicorn app:app --host 0.0.0.0 --port 8369

   # Run pyconvert service (in another terminal)
   cd pyconvert-service
   uvicorn app:app --host 0.0.0.0 --port 3030
   ```

**Note:** 
- The proxy and pyconvert services can be run locally with Python
- Unstructured-io and libreoffice services require their respective containers or separate installations
- For pyconvert-service, ensure pandoc is installed on your system
- All services communicate via the `app-network` when using containers

## Container Runtime Options

This project uses Docker as the primary container runtime

**Installation:**
```bash
# Ubuntu/Debian
sudo apt install docker.io docker-compose

# CentOS/RHEL/Fedora
sudo dnf install docker docker-compose

# macOS (Untested!)
brew install docker docker-compose

# Windows (Only tested via WSL)
# Download and install Docker Desktop from https://www.docker.com/products/docker-desktop
```

**Alternative with Podman:**
If you prefer Podman, you can still use it:
```bash
# Using podman-compose
podman-compose up --build
```

## Security Considerations

- The LibreOffice and PyConvert services should not be exposed directly to the internet
- The proxy service handles routing and can implement additional security measures
- Docker's user namespace isolation provides security layers
- Consider adding authentication and rate limiting for production use

## Troubleshooting

For detailed troubleshooting information, see **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

## Credits & Acknowledgments

This project leverages several excellent open-source libraries and services. We extend our gratitude to the developers and maintainers of these projects:

### Core Dependencies

#### Python Libraries
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern, fast web framework for building APIs with Python 3.7+
- **[Uvicorn](https://www.uvicorn.org/)** - Lightning-fast ASGI server implementation
- **[httpx](https://www.python-httpx.org/)** - Fully featured HTTP client for Python 3
- **[python-multipart](https://github.com/andrew-d/python-multipart)** - Streaming multipart/form-data parser
- **[python-magic](https://github.com/ahupp/python-magic)** - File type identification using libmagic

#### Document Processing Libraries
- **[Unstructured](https://unstructured.io/)** - Open-source library for preprocessing and cleaning unstructured data
- **[WeasyPrint](https://weasyprint.org/)** - Converts HTML/CSS documents to PDF
- **[Mammoth](https://github.com/mwilliamson/python-mammoth)** - Convert DOCX files to HTML and vice versa
- **[html-for-docx](https://github.com/ReddyKilowatt/html-for-docx)** - Convert HTML to DOCX with formatting preservation
- **[Pandoc](https://pandoc.org/)** - Universal document converter

#### Data Processing Libraries
- **[pandas](https://pandas.pydata.org/)** - Powerful data structures for data analysis
- **[xlrd](https://xlrd.readthedocs.io/)** - Library for reading data from Excel files
- **[openpyxl](https://openpyxl.readthedocs.io/)** - Python library to read/write Excel 2010 xlsx/xlsm files
- **[odfpy](https://github.com/eea/odfpy)** - Python API for OpenDocument format
- **[numbers-parser](https://github.com/masaccio/numbers-parser)** - Parse Apple Numbers files

#### Web Scraping Libraries
- **[Scrapy](https://scrapy.org/)** - Fast high-level web crawling and web scraping framework
- **[scrapy-user-agents](https://github.com/cnu/scrapy-user-agents)** - Random user agent middleware for Scrapy

### External Services & Containers

#### Document Processing Services
- **[Unstructured IO API](https://github.com/Unstructured-IO/unstructured-api)** - REST API for document processing and data extraction
- **[LibreOffice Unoserver](https://github.com/unoconv/unoserver)** - LibreOffice-based document conversion server
- **[Gotenberg](https://gotenberg.dev/)** - Docker-powered stateless API for converting HTML, Markdown and Office documents to PDF
- **[Pandoc Server](https://github.com/jgm/pandoc)** - Universal markup converter with web service wrapper

#### Container Infrastructure
- **[Docker](https://www.docker.com/)** - Container platform for packaging and running applications
- **[Docker Compose](https://docs.docker.com/compose/)** - Tool for defining and running multi-container Docker applications

### License Acknowledgments

This project uses libraries under various open-source licenses including MIT, Apache 2.0, BSD, and GPL. Please refer to the individual project repositories for specific license information.

---

💓Love,
User27828
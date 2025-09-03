# AppLite Convert - Multi-Service Document Processing API

This project provides a unified API gateway for multiple document processing services using Podman and podman-compose.

## Goals

1. To extract the best semantic representation of common documents and output it for ETL
or LLM pipelines.  
1. To convert between popular formats or at least to popular formats from outdated or unpopular ones (right `.pages`!?).  
2. To convert well-structured, formatted, and supported formats to PDF (via Gotenberg).  Our emphasis is HTML>PDF, but many other inputs are supported.

## Services

- **Unstructured IO** (`/unstructured-io`): Document structure extraction and processing using the official Unstructured API
- **LibreOffice Unoserver** (`/libreoffice`): Document conversion using LibreOffice headless server
- **Pandoc API** (`/pandoc`): Document format conversion with PDF support via FastAPI service
- **Gotenberg** (`/gotenberg`): High-fidelity HTML to PDF conversion, including support for URLs and office documents

## Architecture

The main proxy service runs on a configurable port (default: 8369) and routes requests based on URL prefixes:

**Proxied sub-containers**:

Proxying to these containers aims to preserve the original functionality of the containers.  The documented features of these projects should all function as expected, but with the proxy URL prefix.

- `/unstructured-io/*` → Unstructured IO API (port 8000)
- `/libreoffice/*` → LibreOffice API (port 2004)
- `/pandoc/*` → Pandoc API (port 3000)
- `/gotenberg/*` → Gotenberg API (port 4000)

**Helper endpoints**:

- `/convert/*` → High-level conversion aliases (auto-routing)
- `/ping` → General health check
- `/ping-all` → General health check - All container services
- `/{service}/ping` → Service-specific health check
- `/docs` → API documentation

**Chained endpoints**: (uses multiple services or transforms service input/output)

- `/unstructured-io-md` → Normal Unstructured IO input file with markdown output
- `/unstructured-io-txt` → Normal Unstructured IO input file with text output
- `/libreoffice-md` → Normal LibreOffice input file with markdown output.  `-txt` isn't handled because LibreOffice can output that regularly.


**Proxy Features:**
- Supports all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)
- Streaming responses for large files
- Automatic header filtering (removes hop-by-hop headers)
- Request/response body forwarding
- Query parameter preservation

### Network Security

**External Access:**
- Only the configured proxy port is exposed to the outside world (default: `8369`)
- All other services run on an isolated internal network

**Internal Network:**
- Services communicate via the `app-network` bridge network
- Individual service ports (8000, 2004, 3000, 4000) are not accessible externally
- All external requests must go through the proxy service

## Conversion Endpoints

The API provides high-level conversion aliases at `/convert/*` that automatically route to the most reliable service for each conversion type. These endpoints are optimized for common document workflows, especially **resume/CV/cover letter** processing.

### Priority Formats (Documents)

**Input Formats:** _\<http(s) URL\>_, `pptx`, `ppt`, `docx`, `odt`, `rtf`, `txt`, `html`, `md`, `tex`, `latex`, `pages`  
**Output Formats:** `pdf`, `docx`, `html`, `md`, `txt`, `json`

### 📖 Complete Documentation

For comprehensive information about all available conversion endpoints, usage examples, service selection logic, and configuration details, see **[docs/FORMATS.md](docs/FORMATS.md#🔄-conversion-api-endpoints)**.

### Quick Examples

**Note:** Replace `8369` with your configured port if using `APPLITE_CONVERT_PORT`.

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

**List all supported conversions:**
```bash
curl http://localhost:8369/convert/supported
```

### Service Intelligence

Each endpoint automatically selects the optimal service:
- **PDF Output**: Gotenberg (highest quality for HTML/DOCX/PPTX/XLSX)
- **JSON Output**: Unstructured IO (best structure extraction)
- **DOCX Output**: LibreOffice or Pandoc (format-specific optimization)
- **URL Input**: Gotenberg for PDF, Unstructured IO for JSON/Markdown/Text

### Additional Endpoints

- `GET /convert/supported` - List all available conversions
- `GET /convert/info/{input}-{output}` - Get conversion details
- Full list in `proxy-service/convert/README.md`

## Quick Start

1. Clone this repository
2. **For Podman**: Ensure registries are configured (see troubleshooting section)
3. Run `podman-compose up --build`
4. The API will be available at `http://localhost:8369` (or your configured port via `APPLITE_CONVERT_PORT`)

### Test Health Checks

```bash
# General ping (replace 8369 with your configured port)
curl http://localhost:8369/ping

# Comprehensive health check
curl http://localhost:8369/ping-all

# Individual service health checks
curl http://localhost:8369/unstructured-io/ping
curl http://localhost:8369/libreoffice/ping
curl http://localhost:8369/pandoc/ping
curl http://localhost:8369/gotenberg/ping
```

### Alternative: Using the Helper Script

For easier management, use the provided script:

```bash
# Start services
./podman-run.sh up

# Start in background
./podman-run.sh up-d

# Build services
./podman-run.sh build

# View logs
./podman-run.sh logs

# Check status
./podman-run.sh status

# Stop services
./podman-run.sh down

# Clean up
./podman-run.sh clean
```

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
- Multiple parsing strategies (fast, hi_res, ocr_only, auto)
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

### Pandoc
- `GET /pandoc/ping` - Pandoc health check (uses `/ping` endpoint)
- `POST /pandoc/convert` - Document conversion
  - **Supported formats**: `pdf`, `docx`, `html`, `txt`, `md`, `tex`
  - **Form data**: `file` (file upload), `output_format` (string), `extra_args` (optional string)
  - **Features**: Automatic cleanup, timeout handling (60s), background file processing

**Pandoc Integration:**
- Uses [Pandoc](https://pandoc.org/) for universal document conversion
- Supports conversion between markup formats and office documents
- Includes LaTeX support for high-quality PDF generation

**Sample Request:**
```bash
# Convert Markdown to PDF
curl -X POST "http://localhost:8369/pandoc/convert" \
  -F "file=@document.md" \
  -F "output_format=pdf" \
  -o converted_document.pdf

# Convert with custom Pandoc arguments
curl -X POST "http://localhost:8369/pandoc/convert" \
  -F "file=@document.md" \
  -F "output_format=pdf" \
  -F 'extra_args=--pdf-engine=pdflatex --variable geometry:margin=1in' \
  -o styled_document.pdf
```

**Common Conversions:**
- Markdown/HTML → PDF (with LaTeX)
- DOCX → Markdown/HTML
- Various markup formats ↔ Office documents
- Text files with custom formatting

### Gotenberg
- `GET /gotenberg/ping` - Gotenberg health check (uses `/` root endpoint)
- `POST /gotenberg/forms/chromium/convert/html` - HTML to PDF conversion
- `POST /gotenberg/forms/chromium/convert/url` - URL to PDF conversion
- `POST /gotenberg/forms/libreoffice/convert` - Office document to PDF conversion

**Gotenberg Integration:**
- Uses [Gotenberg](https://gotenberg.dev/) for high-quality PDF generation from HTML, URLs, and office documents
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
podman-compose build

# Build specific service
podman-compose build pandoc
podman-compose build proxy
```

### Running Services

```bash
# Start all services
podman-compose up

# Start in background
podman-compose up -d

# View logs
podman-compose logs

# Stop services
podman-compose down
```

### Podman-Specific Commands

```bash
# List running containers
podman ps

# View container logs
podman logs <container_name>

# Access container shell
podman exec -it <container_name> /bin/bash

# Clean up
podman system prune
podman-compose down --volumes
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
   pip install fastapi uvicorn python-multipart  # for pandoc-service if needed
   ```

4. Run the services:
   ```bash
   # Run proxy service (in one terminal)
   cd proxy-service
   uvicorn app:app --host 0.0.0.0 --port 8369

   # Run pandoc service (in another terminal)
   cd pandoc-service
   uvicorn app:app --host 0.0.0.0 --port 3000
   ```

**Note:** 
- The proxy and pandoc services can be run locally with Python
- Unstructured-io and libreoffice services require their respective containers or separate installations
- For pandoc-service, ensure pandoc is installed on your system
- All services communicate via the `app-network` when using containers

## Container Runtime Options

This project uses Podman as the primary container runtime for enhanced security:

**Podman Benefits:**
- ✅ Rootless containers by default
- ✅ Daemonless architecture (no background service)
- ✅ Compatible with docker-compose via `podman-compose`
- ✅ Better security model for production deployments
- ✅ Native support for Kubernetes pod manifests

**Installation:**
```bash
# Ubuntu/Debian
sudo apt install podman podman-compose

# CentOS/RHEL/Fedora
sudo dnf install podman podman-compose

# macOS
brew install podman podman-compose

# Windows
winget install RedHat.Podman
```

**Alternative with Docker:**
If you prefer Docker, you can still use it:
```bash
# Using docker-compose
docker-compose up --build
```

## Security Considerations

- The LibreOffice and Pandoc services should not be exposed directly to the internet
- The proxy service handles routing and can implement additional security measures
- Podman's rootless mode provides additional security layers
- Consider adding authentication and rate limiting for production use

## Troubleshooting

### Quick Reference

**Common Issues & Solutions:**
- [Build cache problems](#docker-build-cache-issues) - Code changes not taking effect
- [Service connectivity](#podman-specific-troubleshooting) - Services not starting or unreachable  
- [Endpoint errors](#service-specific-endpoint-issues) - 404/422 errors from services
- [Memory issues](#libreoffice-memory-leak-solution) - LibreOffice memory accumulation
- [PEP 668 conflicts](#pep-668-externally-managed-environment) - Python package installation errors

### Common Issues

1. **Port conflicts**: Ensure port 8369 is available (other service ports are internal only)
2. **Build failures**: Check Podman installation and disk space
3. **Service connectivity**: Verify network configuration in docker-compose.yml
4. **Permission issues**: Podman runs rootless by default - ensure proper user permissions
5. **Build cache issues**: See [Docker Build Cache Issues](#docker-build-cache-issues)
6. **Requirements corruption**: See [Requirements.txt Corruption](#requirements-txt-corruption)
7. **Package size issues**: See [Unstructured Package Optimization](#unstructured-package-optimization)
8. **Service endpoint errors**: See [Service-Specific Endpoint Issues](#service-specific-endpoint-issues)

### Podman-Specific Troubleshooting

```bash
# Check if podman socket is running
podman system service --help

# Reset podman environment
podman system reset

# Fix shared mount warnings (run as root or with sudo)
# Add to /etc/containers/storage.conf:
# [storage]
#   driver = "overlay"
#   mount_program = "/usr/bin/fuse-overlayfs"
```

If you're using WSL (Ubuntu) and Podman Desktop on Windows, there's an alternative static-binary installation and connection method that can help avoid distribution packaging issues. See `docs/PODMAN-DESKTOP-WSL.md` for step-by-step instructions.

### Registry Configuration

If you encounter registry resolution issues:

```bash
# Check registries configuration
cat /etc/containers/registries.conf

# For unqualified image names, ensure registries are configured:
# unqualified-search-registries = ["docker.io", "registry.fedoraproject.org"]
```

### Build Issues

```bash
# Clean build cache
podman system prune -a

# Rebuild specific service
podman-compose build pandoc
podman-compose build proxy
```

### PEP 668 (Externally Managed Environment)

If you encounter "externally-managed-environment" errors:

**Solution Applied**: The pandoc service now uses a virtual environment to avoid PEP 668 restrictions in Alpine Linux.

**Manual Fix** (if needed):
```dockerfile
# In Dockerfile, add:
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --break-system-packages package_name
```

**Why This Happens**: Alpine Linux enforces PEP 668 to prevent conflicts with system package management.

### Logs

```bash
# View all logs
podman-compose logs

# View specific service logs
podman-compose logs proxy
podman-compose logs unstructured-io

# Follow logs in real-time
podman-compose logs -f
```

### Image Tag Issues

If you encounter "manifest unknown" errors:

**LibreOffice Image:**
```yaml
# Use specific version instead of latest
image: docker.io/libreofficedocker/libreoffice-unoserver:3.19
```

**Available LibreOffice tags:** `3.19`, `3.18`, `3.17`, `3.16`, `3.15`, `3.14`

### Entrypoint Conflicts

If services fail to start with "Unknown option" errors:

**Pandoc Service:**
- The Dockerfile now includes `ENTRYPOINT []` to override the default pandoc entrypoint
- Uses virtual environment path for uvicorn: `/opt/venv/bin/uvicorn`

### CNI Configuration Warnings

The warnings about "plugin firewall does not support config version" are non-critical:
- These are Podman networking warnings
- Services will still function normally
- Can be ignored unless networking issues occur

### LibreOffice Memory Leak Solution

**Issue**: Unoserver has a known memory leak that causes memory usage to grow indefinitely over time, eventually leading to process termination.

**Root Cause Identified**: Through systematic testing, we discovered that custom environment variables in docker-compose.yml were causing conversion failures. The issue was NOT with unoserver itself, but with conflicting configuration parameters.

**Solution Applied**: 
- Removed problematic environment variables (`UNOSERVER_ADDR`, `UNOSERVER_MAX_LIFETIME`, `UNOSERVER_MAX_REQUESTS`, `UNOCONVERT_TIMEOUT`)
- Added `UNOSERVER_STOP_AFTER=50` to restart the process after 50 requests, preventing memory accumulation
- Configured restart policy to handle automatic container recovery

**Testing Results**:
- ✅ Isolated unoserver container: Works perfectly (880ms conversion time)
- ✅ Docker-compose with default config: Works perfectly (531ms conversion time)  
- ✅ Docker-compose with memory leak solution: Works perfectly (642ms conversion time)
- ❌ Docker-compose with custom env vars: Fails with "Proxy error" and timeouts

**Configuration**:
```yaml
libreoffice:
  image: docker.io/libreofficedocker/libreoffice-unoserver:3.19
  environment:
    - UNOSERVER_STOP_AFTER=50  # Restart after 50 requests to prevent memory leaks
  deploy:
    restart_policy:
      condition: on-failure
      delay: 5s
      max_attempts: 3
      window: 120s
  networks:
    - app-network
```

**Why This Works**:
- The `--stop-after` parameter (added in unoserver 3.2) is the official solution for memory leaks
- Automatic container restart ensures continuous service availability
- No performance impact on individual conversions
- Prevents memory accumulation that causes system instability

## Features

- **Dark Mode Documentation**: The `/docs` endpoint automatically enables dark mode for better readability
- **Comprehensive Health Checks**: Real-time monitoring of all services with detailed status reporting
- **Full PDF Support**: PDF generation capabilities through Pandoc with LaTeX support
- **Multi-Format Conversion**: Support for PDF, DOCX, HTML, TXT, MD, and TEX formats
- **Security**: Podman rootless containers for enhanced security
- **Streaming Responses**: Efficient handling of large file transfers
- **Automatic Cleanup**: Background file cleanup for temporary processing files
- **Timeout Protection**: Configurable timeouts (60s for conversions, 10s for general requests, 5s for health checks)
- **Error Handling**: Comprehensive error handling with appropriate HTTP status codes

## License

This project is licensed under the Apache 2.0 License.

## Format Support

For comprehensive information about supported file formats, conversion capabilities, and identified gaps across all services, see [docs/FORMATS.md](docs/FORMATS.md).

This document includes:
- Detailed format support matrices for all services
- Conversion workflows and recommendations
- Identified gaps and limitations
- Future enhancement opportunities

### Docker Build Cache Issues

If you encounter persistent issues where code changes don't take effect after rebuilding containers:

**Symptoms:**
- API responses show old data despite code changes
- Container logs show old code execution
- Changes to Python files appear to be ignored
- Configuration updates don't take effect
- Router endpoints return old error messages

**Root Cause:**
Docker/Podman uses layer caching during builds. The `COPY . /app/` step may use a cached layer even when source files have changed, especially if only small changes are made to Python files.

**Immediate Verification:**
```bash
# Check if container has your changes
podman exec appliteconvert_proxy_1 cat /app/convert/config.py | grep "your_change"
podman exec appliteconvert_proxy_1 cat /app/convert/router.py | grep "your_endpoint"
```

**Solutions:**

1. **Force complete rebuild:**
```bash
# Remove existing image completely
podman rmi localhost/appliteconvert_proxy:latest

# Rebuild with no cache and pull latest base image
podman-compose build --no-cache --pull proxy

# Restart container
podman-compose up -d proxy
```

2. **Manual file update (temporary workaround):**
```bash
# Copy updated files directly into running container
podman cp proxy-service/convert/config.py appliteconvert_proxy_1:/app/convert/config.py
podman cp proxy-service/convert/router.py appliteconvert_proxy_1:/app/convert/router.py

# Restart container to reload Python modules
podman-compose restart proxy
```

3. **Add timestamp for cache busting:**
```dockerfile
# In Dockerfile, modify COPY command:
COPY . /app/
# To:
ARG BUILD_DATE
RUN echo "Build date: $BUILD_DATE"
COPY . /app/
```

Then rebuild with:
```bash
podman-compose build --build-arg BUILD_DATE=$(date +%s) proxy
```

4. **Clear Python cache:**
```bash
# Clear Python bytecode cache
podman exec appliteconvert_proxy_1 find /app -name "*.pyc" -delete
podman exec appliteconvert_proxy_1 find /app -name "__pycache__" -type d -exec rm -rf {} +

# Restart container
podman-compose restart proxy
```

**Prevention:**
- Use `--no-cache` flag when rebuilding after significant code changes
- Add version tags or timestamps to force cache invalidation
- Test API endpoints after container rebuilds to verify changes took effect
- When in doubt, use `podman rmi` to remove old images before rebuilding

### Service-Specific Endpoint Issues

If conversions fail with "404 page not found" or "422 Unprocessable Entity" errors:

**LibreOffice Service:**
- **Correct endpoint:** `/libreoffice/request` (not `/convert`)
- **Parameters:** `file` (multipart), `convert-to` (form field)
- **Example:**
```bash
curl -X POST "http://localhost:8369/libreoffice/request" \
  -F "file=@document.pages" \
  -F "convert-to=pdf" \
  -o output.pdf
```

**Pandoc Service:**
- **Endpoint:** `/pandoc/convert`
- **Parameters:** `file` (multipart), `output_format` (form field), `extra_args` (optional)
- **Note:** Pandoc doesn't support proprietary formats like `.pages`

**Gotenberg Service:**
- **Endpoint:** `/gotenberg/forms/libreoffice/convert` or `/gotenberg/forms/chromium/convert/html`
- **Parameters:** `files` (multipart), format-specific options

**Unstructured IO Service:**
- **Endpoint:** `/unstructured-io/general/v0/general`
- **Parameters:** `files` (multipart), `output_format` (form field)

**Verification:**
```bash
# Test direct service endpoints
curl http://localhost:8369/libreoffice/ping
curl http://localhost:8369/pandoc/ping
curl http://localhost:8369/gotenberg/
curl http://localhost:8369/unstructured-io/general/v0/general -F "files=@test.txt" -F "output_format=json"
```

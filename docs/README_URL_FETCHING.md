# URL Fetching for Document Conversions

This module provides comprehensive URL fetching capabilities for document conversion services, enabling seamless processing of remote web content.

## Overview

The URL fetching system bridges the gap between services that support direct URL input and those that require file uploads. It provides:

1. **Intelligent URL Processing** - Automatic content type detection and format inference
2. **Multi-Service Integration** - Works with all conversion services (Gotenberg, Unstructured-IO, LibreOffice, Pandoc)
3. **Robust Error Handling** - Comprehensive timeout, retry, and error recovery mechanisms
4. **Performance Optimization** - Connection pooling, caching, and resource management

## Features

### 🔗 **URL Fetching Capabilities**
- **Requests-based fetching** with async support for reliable operation
- **Content type auto-detection** from HTTP headers and content analysis
- **Format inference** for optimal conversion routing
- **Size limits** (50MB default) to prevent abuse
- **Timeout handling** with configurable limits (30s default)
- **Retry logic** with exponential backoff
- **User-agent customization** for better compatibility

### 📁 **Temporary File Management**
- **Automatic temp file creation** in `/tmp/applite-xtrac`
- **Smart filename generation** based on URL and detected content type
- **Resource cleanup** with context managers and error recovery
- **Metadata tracking** for debugging and monitoring

### 🔄 **Service Integration**
- **Transparent integration** with `/convert/url-*` endpoints
- **Format-specific routing** for optimal conversion quality
- **Service-specific optimizations** based on content type
- **Fallback mechanisms** for failed conversions

## Supported URL Conversions

### URL to PDF Conversions
| Endpoint | Primary Service | Description | Use Case |
|----------|----------------|-------------|----------|
| `POST /convert/url-pdf` | Gotenberg | URL to PDF with full CSS support | Web page archiving, reports |
| `POST /convert/url-pdf` | LibreOffice | Fallback for complex pages | Backup conversion method |

### URL to JSON Conversions
| Endpoint | Primary Service | Description | Use Case |
|----------|----------------|-------------|----------|
| `POST /convert/url-json` | Unstructured IO | URL content structure extraction | Web content analysis |
| `POST /convert/url-json` | LibreOffice | Fallback structure extraction | Backup analysis method |

### URL to Markdown Conversions
| Endpoint | Primary Service | Description | Use Case |
|----------|----------------|-------------|----------|
| `POST /convert/url-md` | Unstructured IO | URL to Markdown conversion | Content extraction |
| `POST /convert/url-md` | Pandoc | Fallback Markdown conversion | Alternative processing |

### URL to Text Conversions
| Endpoint | Primary Service | Description | Use Case |
|----------|----------------|-------------|----------|
| `POST /convert/url-txt` | Unstructured IO | URL to plain text | Text extraction |
| `POST /convert/url-txt` | LibreOffice | Fallback text extraction | Alternative processing |

## Usage Examples

### Convert Web Page to PDF

```bash
curl -X POST "http://localhost:8369/convert/url-pdf" \
  -F "url=https://example.com" \
  -o webpage.pdf
```

### Extract Web Content Structure

```bash
curl -X POST "http://localhost:8369/convert/url-json" \
  -F "url=https://example.com/article" \
  -o content-structure.json
```

### Convert Web Article to Markdown

```bash
curl -X POST "http://localhost:8369/convert/url-md" \
  -F "url=https://example.com/blog-post" \
  -o article.md
```

### Extract Plain Text from Web Page

```bash
curl -X POST "http://localhost:8369/convert/url-txt" \
  -F "url=https://example.com/document" \
  -o document.txt
```

### Convert URL with Custom User-Agent

```bash
# Use a custom User-Agent string for sites that require specific identification
curl -X POST "http://localhost:8369/convert/url-pdf" \
  -F "url=https://example.com" \
  -F "user_agent=Mozilla/5.0 (compatible; MyBot/1.0; +https://example.com/bot)" \
  -o webpage.pdf

# Use mobile User-Agent for mobile-optimized content
curl -X POST "http://localhost:8369/convert/url-html" \
  -F "url=https://example.com/mobile-page" \
  -F "user_agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15" \
  -o mobile-page.html
```

## Configuration

### Environment Variables

```bash
# URL fetching configuration
URL_FETCH_TIMEOUT=30          # Request timeout in seconds
URL_FETCH_MAX_SIZE=52428800   # Max file size (50MB)
URL_FETCH_RETRIES=3           # Number of retry attempts
URL_FETCH_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"  # Default user agent

# Custom User-Agent Support
# The user_agent parameter can be passed to any /convert/url-* endpoint:
# curl -X POST "http://localhost:8369/convert/url-pdf" -F "url=https://example.com" -F "user_agent=Your Custom User Agent"
# If not provided, the default browser-like User-Agent is used
```

### Content Type Detection

The system automatically detects content types and routes to appropriate services:

- **HTML pages** → Gotenberg (PDF), Unstructured IO (JSON/MD/TXT)
- **PDF links** → Unstructured IO (structure extraction)
- **Office documents** → LibreOffice/Pandoc (format conversion)
- **Images** → Limited support (metadata extraction only)
- **Plain text** → Direct processing

## Error Handling

### Common Issues and Solutions

**Timeout Errors:**
```json
{
  "error": "URL fetch timeout",
  "details": "Request exceeded 30s timeout",
  "solution": "Try a different URL or increase timeout"
}
```

**Size Limit Exceeded:**
```json
{
  "error": "Content too large",
  "details": "File size 75MB exceeds 50MB limit",
  "solution": "Use a different URL or increase size limit"
}
```

**Unsupported Content Type:**
```json
{
  "error": "Unsupported content type",
  "details": "Content type 'video/mp4' not supported",
  "solution": "Use URLs with document content"
}
```

## Performance Optimization

### Connection Pooling
- HTTP connection reuse to reduce latency
- Keep-alive connections for multiple requests
- Automatic connection cleanup

### Caching (Future Enhancement)
- URL content caching for repeated requests
- ETag and Last-Modified header support
- Configurable cache expiration

### Rate Limiting
- Built-in rate limiting to prevent abuse
- Configurable request limits per minute/hour
- Automatic backoff on rate limit hits

## Integration with Conversion Pipeline

The URL fetching system integrates seamlessly with the conversion pipeline:

1. **URL Validation** - Check URL format and accessibility
2. **Content Fetching** - Download content with timeout/retry logic
3. **Format Detection** - Analyze content type and structure
4. **Service Routing** - Route to optimal conversion service
5. **Result Processing** - Return converted content to user

## Monitoring and Debugging

### Debug Information
Enable debug logging to see URL fetching details:

```bash
export LOG_LEVEL=DEBUG
./run.sh dev
```

### Health Checks
Monitor URL fetching health:

```bash
curl http://localhost:8369/unstructured-io/ping
curl http://localhost:8369/gotenberg/ping
```

## Future Enhancements

- **Scrapy Integration** - Advanced web scraping capabilities
- **JavaScript Rendering** - Support for dynamic web content
- **Authentication Support** - Basic auth and API key handling
- **Proxy Support** - HTTP proxy configuration
- **Content Caching** - Intelligent caching layer
- **Batch Processing** - Multiple URL processing

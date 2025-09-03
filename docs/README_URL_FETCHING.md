# URL Fetching for Document Conversions

This module provides URL fetching capabilities for document conversion services that don't support direct URL input.

## Overview

Some conversion services (Unstructured-IO, LibreOffice, Pandoc) only accept file uploads, while others (Gotenberg) can process URLs directly. This module bridges that gap by:

1. **Fetching remote URLs** using requests (primary) with Scrapy as optional fallback
2. **Saving content to temporary files** for services that need file uploads
3. **Auto-detecting content formats** from URL responses
4. **Integrating seamlessly** with existing conversion endpoints

## Features

### 🔗 **URL Fetching**
- **Requests-based fetching** for reliable async operation
- **Scrapy integration** available as fallback (currently disabled due to event loop conflicts)
- **Content type detection** and format inference
- **Size limits** to prevent abuse (50MB default)
- **Timeout handling** with configurable limits
- **Retry logic** with exponential backoff

### 📁 **Temporary File Management**
- **Automatic temp file creation** in `/tmp/applite-convert`
- **Smart filename generation** based on URL and content
- **Resource cleanup** with context managers
- **Error recovery** with proper cleanup

### 🔄 **Service Integration**
- **Transparent integration** with existing `/convert/url-*` endpoints
- **Format auto-detection** for better conversion accuracy
- **Service-specific handling** for optimal results
- **Metadata tracking** for debugging and monitoring

## Current Implementation

**Primary Method:** requests library with retry logic  
**Fallback Method:** Scrapy (currently disabled due to async event loop conflicts)  
**File Storage:** `/tmp/applite-convert` directory  
**Size Limit:** 50MB per URL  
**Timeout:** 30 seconds default  

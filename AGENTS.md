# AppLite Xtrac AI Coding Assistant Instructions

## Engineering Standards

Every change — no matter how small — must follow first-principles logic and be production-grade.

- Before implementing, build a concrete plan. Back-trace (does each step follow from preconditions?) and forward-trace (do downstream consumers behave correctly?) to verify logical consistency.
- Eliminate implementation gaps, memory leaks, race conditions, and bugs before proposing a solution. Maximise code re-use: search for existing utilities before writing new ones.
- Optimise for robustness, security, and conciseness.
- If anything is unclear, ask — do not guess.

## Critical Agent Guidelines

**⚠️ AGENTS MUST NOT COMMIT CODE**: AI agents must never execute `git commit`, `git push`, or any other git write operations. All code changes should be left staged or unstaged for the user to commit manually. This ensures:

- User retains full control over commits and commit messages
- Commits remain authored by the user, not an AI agent
- All changes are reviewable before being committed
- Commit history remains clean and human-authored

If you need to record work, ask the user to commit or use task tracking instead.

## 🏗️ Architecture Overview

This is a **multi-service document processing API** that acts as a unified gateway for 4 different document processing services via a FastAPI proxy. The system prioritizes **resume/CV/cover letter processing** but supports comprehensive document conversion.

### Core Services Architecture
```
External Request → Proxy Service (port 8369) → Internal Services
                     ├── /unstructured-io/* → Port 8000 (structure extraction)
                     ├── /libreoffice/* → Port 2004 (office conversions)  
                     ├── /pandoc/* → Port 3000 (markup conversions + WeasyPrint)
                     ├── /gotenberg/* → Port 4000 (HTML→PDF, high quality)
                     └── /convert/* → Smart routing to best service
```

**Key principle**: Only port 8369 is exposed externally; all services communicate via `app-network` bridge on isolated subnet `172.20.0.0/16`.

## 🚀 Essential Workflows

### Starting/Managing Services
```bash
./run.sh up          # Start all services  
./run.sh up-d        # Start in background
./run.sh logs        # View logs
./run.sh status      # Check service health
./run.sh clean       # Full cleanup
```

**Critical**: Use `./run.sh` commands instead of raw docker-compose. The script handles port conflicts, service dependencies, and comprehensive health checks.

### Testing & Development
```bash
# From proxy-service/ directory
python test_runner.py all        # Run all tests
python test_runner.py unit       # Unit tests only
python test_runner.py integration # Integration tests
python test_runner.py conversion  # Conversion-specific tests
```

**Testing pattern**: Tests are organized by markers (`@pytest.mark.unit`, `@pytest.mark.conversion`) and use `conftest.py` fixtures for consistent service mocking.

## 🎯 Conversion Intelligence System

### Smart Routing Logic (`/convert/*` endpoints)
The conversion system in `proxy-service/convert/router.py` implements **service intelligence**:

- **PDF output** → Gotenberg (highest quality for office documents) or WeasyPrint (highest quality for HTML/CSS rendering)
- **JSON structure** → Unstructured IO (best semantic extraction) 
- **DOCX output** → LibreOffice or PyConvert (format-optimized)
- **URL input** → Gotenberg for PDF, Unstructured IO for JSON/Markdown/Text, WeasyPrint for high-quality HTML-to-PDF

### Configuration Pattern
Service routing defined in `convert/config.py` via `CONVERSION_MATRIX` with utility functions in `convert/utils/`:

**Core Configuration** (`config.py`):
- `CONVERSION_MATRIX`: Main conversion routing table
- `SPECIAL_HANDLERS`: Registry for custom handlers

**Utility Functions** (`utils/`):
- `conversion_lookup.py`: `get_conversion_methods()`, `get_service_urls()`
- `conversion_chaining.py`: `get_conversion_steps()`, `is_chained_conversion()`
- `special_handlers.py`: Custom conversion logic

## 🔧 Development Patterns

### Error Handling Convention
Use `create_error_response()` from `app.py` for consistent error formatting:
```python
return create_error_response(404, "SERVICE_UNAVAILABLE", service="pandoc")
```

### Proxy Header Filtering
**Critical**: Remove hop-by-hop headers via `HOP_BY_HOP` set in `app.py` when forwarding requests between services.

### URL Fetching Integration
The system includes Scrapy-based URL fetching (see `docs/URL_FETCHING.md`). URL conversions automatically handle:
- Content extraction → Unstructured IO
- PDF generation → Gotenberg
- Custom headers and authentication

### Local vs Docker Service URLs
Services auto-detect environment via `convert/config.py` and `convert/utils/conversion_lookup.py`:
```python
SERVICE_URL_CONFIGS = {
    "pandoc": {
        "docker": "http://pandoc:3000",    # Container name
        "local": "http://localhost:3030"   # Port mapping
    }
}
```

## 📝 Code Conventions

### File Organization
- `proxy-service/app.py` → Main FastAPI app with health checks and service proxying
- `proxy-service/convert/` → High-level conversion logic and routing
  - `config.py` → Core configuration (CONVERSION_MATRIX, SPECIAL_HANDLERS)
  - `utils/` → Utility modules for conversion logic
    - `conversion_lookup.py` → Lookup functions for conversions and services
    - `conversion_chaining.py` → Multi-step conversion chaining
    - `conversion_core.py` → Core conversion execution
    - `special_handlers.py` → Custom conversion handlers
    - `unstructured_utils.py` → Unstructured IO utilities
    - `url_processor.py` → Consolidated URL processing
  - `router.py` → FastAPI route handlers
- `proxy-service/convert/_local_/` → Local conversion implementations
- `proxy-service/convert/validate/` → Format validation and testing
- `tests/` → Pytest-based testing with comprehensive fixtures

### Import Pattern for Optional Dependencies
```python
try:
    from unstructured.staging.base import elements_to_md
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
```

### Environment Configuration
- `APPLITEXTRAC_PORT` → External proxy port (default: 8369)
- `APPLITEXTRAC_HTTP_TIMEOUT` → Request timeout (default: 0/unlimited)

### Adding New conversion pairs
- Prefer the best service for the input and output format, search the web to learn this.
- Prefer a single service versus chaining
- If no service support the input-output pair, determine if chaining one service to another will accomplish the goal.
- If chaining is necessary, and both chained services support it, use `docx` as the intermediary format.

## 🚨 Critical Considerations

1. **Memory usage**: Unstructured IO with `hi_res` strategy can consume 6GB+ RAM for image-heavy PDFs
2. **Service dependencies**: Proxy waits for all services to be healthy before accepting requests  
3. **Network isolation**: Never expose internal service ports externally
4. **Format priorities**: See `docs/FORMATS.md` for comprehensive conversion matrix and service capabilities

When modifying conversion logic, always test with the validation fixtures in `tests/validate_fixtures.py` and update `CONVERSION_MATRIX` accordingly.

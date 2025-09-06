# Proxy Service Test Suite

This directory contains comprehensive tests for the proxy-service component of the applite-xtrac project.

## 📁 Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   └── test_app.py         # Health endpoint tests
├── integration/             # Integration tests
│   └── test_conversions.py # Conversion endpoint tests
└── fixtures/                # Test data files
    ├── sample.doc
    ├── sample.docx
    ├── sample.html
    └── ... (other sample files)
```

## 🚀 Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements-dev.txt
```

### Quick Start

Run all tests:
```bash
pytest
```

Run specific test categories:
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Run with coverage
pytest --cov=. --cov-report=html
```

### Using the Test Runner Script

The `test_runner.py` script provides convenient commands:

```bash
# Install dependencies
python test_runner.py install-deps

# Run unit tests
python test_runner.py unit

# Run integration tests
python test_runner.py integration

# Run all tests
python test_runner.py all

# Run with coverage report
python test_runner.py coverage

# Clean test artifacts
python test_runner.py clean
```

## 🧪 Test Categories

### Unit Tests (`tests/unit/`)

- **Health Endpoints**: Test `/ping`, `/ping-all`, and individual service pings
- **Response Structure**: Validate JSON response formats
- **Error Handling**: Test error responses and status codes

### Integration Tests (`tests/integration/`)

- **Conversion Endpoints**: Test all `/convert/*` endpoints with real sample files
- **File Processing**: Validate file upload, processing, and download
- **URL Conversions**: Test URL-based conversion endpoints
- **Error Scenarios**: Test invalid inputs and error conditions

## 📊 Test Results

### Output Files

Test results are automatically saved to:
```
.data/tests/output-data/
├── conversion_test_results.json    # Detailed test results
├── sample_docx_docx-pdf.pdf       # Converted output files
├── sample_html_html-pdf.pdf       # ...
└── ...
```

### Results Format

Each test result includes:
```json
{
  "endpoint": "docx-pdf",
  "input_extension": "docx",
  "output_extension": "pdf",
  "input_file": "/path/to/sample.docx",
  "status": "✅",
  "conversion_method": "PDF Generation",
  "error_message": null,
  "output_file": "/path/to/output.pdf",
  "response_time_ms": 1250
}
```

## 🔧 Configuration

### pytest.ini

The `pytest.ini` file contains test configuration:
- Test discovery patterns
- Coverage settings
- Warning filters
- Custom markers

### Fixtures

Shared fixtures in `conftest.py`:
- `client`: FastAPI test client
- `async_client`: HTTPX async client
- Sample file fixtures for each format
- Output directory management

## 📈 Coverage

Run tests with coverage reporting:
```bash
pytest --cov=. --cov-report=html
```

Coverage reports are generated in:
- `htmlcov/index.html` - HTML coverage report
- Terminal output with missing lines
- `coverage.json` - Machine-readable coverage data

## 🏃 Available Sample Files

The test suite uses sample files from `tests/fixtures/`:

| Format | File | Used For |
|--------|------|----------|
| Markdown | `sample.md` | Text conversion tests |
| DOCX | `sample.docx` | Office document tests |
| PDF | `sample.pdf` | Document analysis tests |
| HTML | `sample.html` | Web content tests |
| LaTeX | `sample.latex` | Academic document tests |
| Plain Text | `sample.txt` | Basic conversion tests |
| And more... | | |

## 🔍 Test Markers

Use pytest markers to run specific test types:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests requiring external services
pytest -m service

# Run slow tests
pytest -m slow
```

## 🐛 Debugging Tests

### Verbose Output
```bash
pytest -v -s
```

### Stop on First Failure
```bash
pytest --tb=short -x
```

### Run Specific Test
```bash
pytest tests/integration/test_conversions.py::TestConversionEndpoints::test_conversion_endpoint_discovery -v
```

## 📝 Adding New Tests

### Unit Tests
1. Create test file in `tests/unit/`
2. Use descriptive test class and method names
3. Use fixtures from `conftest.py`
4. Follow the naming pattern `test_*`

### Integration Tests
1. Add to `tests/integration/`
2. Use sample files from fixtures
3. Save output files to `output_data_dir`
4. Update test results tracking

### Sample Files
1. Add new sample files to `tests/fixtures/`
2. Update `conftest.py` with new fixtures
3. Ensure files are reasonable size (< 1MB)

## 🚨 CI/CD Integration

The test suite is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run Tests
  run: |
    pip install -r requirements-dev.txt
    pytest --cov=. --cov-report=xml --junitxml=test-results.xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## 📋 Test Results Summary

After running integration tests, check:
- `📊 .data/tests/output-data/conversion_test_results.json` - Complete results
- `📈 htmlcov/index.html` - Coverage report
- `✅ Test output` - Real-time results in terminal

The test suite provides comprehensive coverage of all conversion endpoints and generates detailed reports for analysis and debugging.

"""
Shared test configuration and fixtures for proxy-service tests.
"""

import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from httpx import AsyncClient
import tempfile
import json
from typing import Dict, List

from app import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def client():
    """FastAPI test client for synchronous tests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
async def async_client():
    """HTTPX async client for asynchronous tests."""
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session")
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def fixtures_dir():
    """Directory containing test fixture files."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_markdown_file(fixtures_dir):
    """Path to sample markdown file."""
    return fixtures_dir / "sample.md"


@pytest.fixture
def sample_docx_file(fixtures_dir):
    """Path to sample DOCX file."""
    return fixtures_dir / "sample.docx"


@pytest.fixture
def sample_pdf_file(fixtures_dir):
    """Path to sample PDF file."""
    return fixtures_dir / "sample.pdf"


@pytest.fixture
def sample_html_file(fixtures_dir):
    """Path to sample HTML file."""
    return fixtures_dir / "sample.html"


@pytest.fixture
def sample_latex_file(fixtures_dir):
    """Path to sample LaTeX file."""
    return fixtures_dir / "sample.latex"


@pytest.fixture
def sample_tex_file(fixtures_dir):
    """Path to sample TeX file."""
    return fixtures_dir / "sample.tex"


@pytest.fixture
def sample_txt_file(fixtures_dir):
    """Path to sample text file."""
    return fixtures_dir / "sample.txt"


@pytest.fixture
def sample_rtf_file(fixtures_dir):
    """Path to sample RTF file."""
    return fixtures_dir / "sample.rtf"


@pytest.fixture
def sample_xlsx_file(fixtures_dir):
    """Path to sample XLSX file."""
    return fixtures_dir / "sample.xlsx"


@pytest.fixture
def sample_xls_file(fixtures_dir):
    """Path to sample XLS file."""
    return fixtures_dir / "sample.xls"


@pytest.fixture
def sample_pptx_file(fixtures_dir):
    """Path to sample PPTX file."""
    return fixtures_dir / "sample.pptx"


@pytest.fixture
def sample_ppt_file(fixtures_dir):
    """Path to sample PPT file."""
    return fixtures_dir / "sample.ppt"


@pytest.fixture
def sample_odt_file(fixtures_dir):
    """Path to sample ODT file."""
    return fixtures_dir / "sample.odt"


@pytest.fixture
def sample_ods_file(fixtures_dir):
    """Path to sample ODS file."""
    return fixtures_dir / "sample.ods"


@pytest.fixture
def sample_pages_file(fixtures_dir):
    """Path to sample Pages file."""
    return fixtures_dir / "sample.pages"


@pytest.fixture
def sample_numbers_file(fixtures_dir):
    """Path to sample Numbers file."""
    return fixtures_dir / "sample.numbers"


@pytest.fixture
def output_data_dir():
    """Directory for storing test output data."""
    # Use absolute path to workspace root
    workspace_root = Path(__file__).parent.parent.parent.resolve()
    output_dir = workspace_root / ".data" / "tests" / "output-data"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def conversion_test_results():
    """Dictionary to store conversion test results."""
    return {
        "timestamp": "2025-01-09T12:00:00Z",
        "test_run": "conversion_integration_tests",
        "results": [],
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
    }


# Conversion endpoint mappings for testing
# Dynamically generated from config.py to ensure all supported formats are tested
def _generate_conversion_endpoints():
    """Generate CONVERSION_ENDPOINTS dynamically from config.py"""
    from convert.utils.conversion_lookup import get_supported_conversions
    
    # Get all supported conversions from config
    supported = get_supported_conversions()
    
    # Convert to the format expected by tests
    endpoints = {}
    for input_fmt, output_fmts in supported.items():
        endpoints[input_fmt] = output_fmts
    
    return endpoints

CONVERSION_ENDPOINTS = _generate_conversion_endpoints()

URL_CONVERSION_ENDPOINTS = {
    "url": ["html", "json", "md", "pdf", "txt"]
}


@pytest.fixture
def available_sample_files(fixtures_dir):
    """List of available sample files for testing."""
    available_files = []
    for file_path in fixtures_dir.glob("sample.*"):
        if file_path.is_file():
            extension = file_path.suffix.lstrip('.')
            available_files.append({
                "path": file_path,
                "extension": extension,
                "filename": file_path.name
            })
    return available_files


@pytest.fixture
def testable_conversions(available_sample_files):
    """List of testable conversion combinations based on available files."""
    testable = []
    available_extensions = {f["extension"] for f in available_sample_files}

    for input_ext, output_exts in CONVERSION_ENDPOINTS.items():
        if input_ext in available_extensions:
            for output_ext in output_exts:
                testable.append({
                    "input_extension": input_ext,
                    "output_extension": output_ext,
                    "endpoint": f"{input_ext}-{output_ext}",
                    "sample_file": next((f for f in available_sample_files if f["extension"] == input_ext), None)
                })

    return testable

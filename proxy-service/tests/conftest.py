"""
Shared test configuration and fixtures for proxy-service tests.
"""

import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from httpx import AsyncClient
import tempfile
from datetime import datetime
import json
from typing import Dict, List, Generator, Union, Callable

from app import app


# ===== FIXTURE FACTORIES =====

class FixtureFactory:
    """Base factory class for creating parameterized test fixtures."""

    @staticmethod
    def create_file_fixture(fixtures_dir: Path, filename: str, description: str = None) -> Callable:
        """Factory for creating file path fixtures."""
        def fixture():
            file_path = fixtures_dir / filename
            if not file_path.exists():
                pytest.skip(f"Sample file {filename} not found in fixtures directory")
            return file_path
        fixture.__name__ = f"sample_{Path(filename).stem}_file"
        if description:
            fixture.__doc__ = description
        else:
            fixture.__doc__ = f"Path to sample {filename} file."
        return fixture

    @staticmethod
    def create_directory_fixture(base_path: Union[str, Path], create_parents: bool = True,
                                description: str = None) -> Callable:
        """Factory for creating directory fixtures."""
        def fixture():
            path = Path(base_path)
            if create_parents:
                path.mkdir(parents=True, exist_ok=True)
            elif not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            return path
        fixture.__name__ = f"{Path(base_path).name}_dir"
        if description:
            fixture.__doc__ = description
        else:
            fixture.__doc__ = f"Directory at {base_path}."
        return fixture

    @staticmethod
    def create_temp_directory_fixture(prefix: str = "test", description: str = None) -> Callable:
        """Factory for creating temporary directory fixtures."""
        def fixture():
            with tempfile.TemporaryDirectory(prefix=prefix) as tmpdir:
                yield Path(tmpdir)
        fixture.__name__ = f"{prefix}_temp_dir"
        if description:
            fixture.__doc__ = description
        else:
            fixture.__doc__ = f"Temporary directory with prefix '{prefix}'."
        return fixture


class ClientFactory:
    """Factory for creating different types of test clients."""

    @staticmethod
    def create_sync_client(app_instance, base_url: str = None, description: str = None) -> Callable:
        """Factory for creating synchronous FastAPI test clients."""
        def fixture():
            with TestClient(app_instance) as client:
                yield client
        fixture.__name__ = "sync_client"
        if description:
            fixture.__doc__ = description
        else:
            fixture.__doc__ = "FastAPI test client for synchronous tests."
        return fixture

    @staticmethod
    def create_async_client(app_instance, base_url: str = "http://testserver",
                           description: str = None) -> Callable:
        """Factory for creating asynchronous HTTPX clients."""
        async def fixture():
            async with AsyncClient(app=app_instance, base_url=base_url) as client:
                yield client
        fixture.__name__ = "async_client"
        if description:
            fixture.__doc__ = description
        else:
            fixture.__doc__ = "HTTPX async client for asynchronous tests."
        return fixture


# ===== STANDARD FIXTURES =====

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Client fixtures using factory
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


# Directory fixtures
@pytest.fixture(scope="session")
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def fixtures_dir():
    """Directory containing test fixture files."""
    return Path(__file__).parent / "fixtures"


# ===== FILE FIXTURES (GENERATED USING FACTORY) =====

# File extension mappings for sample files
SAMPLE_FILE_EXTENSIONS = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'html': 'html',
    'latex': 'latex',
    'tex': 'tex',
    'txt': 'txt',
    'rtf': 'rtf',
    'xlsx': 'xlsx',
    'xls': 'xls',
    'pptx': 'pptx',
    'ppt': 'ppt',
    'odt': 'odt',
    'ods': 'ods',
    'pages': 'pages',
    'numbers': 'numbers',
    'key': 'key',
    'odp': 'odp'
}


def _create_sample_file_fixture(extension: str, fixtures_dir: Path):
    """Helper function to create sample file fixtures."""
    filename = f"sample.{extension}"
    file_path = fixtures_dir / filename
    if not file_path.exists():
        pytest.skip(f"Sample file {filename} not found in fixtures directory")
    return file_path


# Generate file fixtures dynamically using the factory pattern
for format_name, extension in SAMPLE_FILE_EXTENSIONS.items():
    fixture_name = f"sample_{format_name}_file"

    def create_fixture(ext=extension):
        @pytest.fixture
        def fixture_func(fixtures_dir):
            filename = f"sample.{ext}"
            file_path = fixtures_dir / filename
            if not file_path.exists():
                pytest.skip(f"Sample file {filename} not found in fixtures directory")
            return file_path
        fixture_func.__name__ = f"sample_{format_name}_file"
        fixture_func.__doc__ = f"Path to sample {format_name.upper()} file."
        return fixture_func

    globals()[fixture_name] = create_fixture()


# ===== PARAMETERIZED FILE FIXTURES =====

@pytest.fixture(params=list(SAMPLE_FILE_EXTENSIONS.keys()))
def sample_file(request, fixtures_dir):
    """Parameterized fixture providing all available sample files."""
    format_name = request.param
    extension = SAMPLE_FILE_EXTENSIONS[format_name]
    filename = f"sample.{extension}"
    file_path = fixtures_dir / filename

    if not file_path.exists():
        pytest.skip(f"Sample file {filename} not found")

    return {
        'path': file_path,
        'format': format_name,
        'extension': extension,
        'filename': filename
    }


@pytest.fixture
def sample_file_by_extension(fixtures_dir):
    """Factory fixture for getting sample files by extension."""
    def get_sample_file(extension: str):
        """Get a sample file by its extension."""
        filename = f"sample.{extension}"
        file_path = fixtures_dir / filename

        if not file_path.exists():
            available = [f.name for f in fixtures_dir.glob("sample.*")]
            raise FileNotFoundError(
                f"Sample file {filename} not found. Available: {available}"
            )

        return file_path

    return get_sample_file


# ===== UTILITY FIXTURES =====

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
        "timestamp": datetime.now().isoformat() + "Z",
        "test_run": "conversion_integration_tests",
        "results": [],
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
    }


# ===== CONVERSION ENDPOINTS =====

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


# ===== DYNAMIC TEST DATA FIXTURES =====

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


# ===== ADVANCED FIXTURE FACTORY =====

class AdvancedFixtureFactory:
    """Advanced fixture factory for complex test scenarios."""

    @staticmethod
    def create_batch_file_fixtures(file_specs: Dict[str, str], fixtures_dir_fixture: str = "fixtures_dir"):
        """Create multiple file fixtures from a specification dictionary."""
        def batch_fixture_factory():
            fixtures = {}
            fixtures_dir = globals()[fixtures_dir_fixture]()

            for name, extension in file_specs.items():
                filename = f"sample.{extension}"
                file_path = fixtures_dir / filename
                if file_path.exists():
                    fixtures[name] = file_path
                else:
                    fixtures[name] = None  # File not available

            return fixtures

        return batch_fixture_factory

    @staticmethod
    def create_conditional_fixture(condition_func: Callable, true_fixture: Callable, false_fixture: Callable):
        """Create a fixture that conditionally uses different implementations."""
        def conditional_fixture():
            if condition_func():
                return true_fixture()
            else:
                return false_fixture()

        return conditional_fixture


# ===== BATCH FILE FIXTURES =====

# Create batch fixtures for common file groups
DOCUMENT_FILES = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'html': 'html',
    'latex': 'latex',
    'tex': 'tex',
    'txt': 'txt',
    'rtf': 'rtf'
}

SPREADSHEET_FILES = {
    'xlsx': 'xlsx',
    'xls': 'xls',
    'ods': 'ods',
    'numbers': 'numbers'
}

PRESENTATION_FILES = {
    'pptx': 'pptx',
    'ppt': 'ppt',
    'odp': 'odp',
    'key': 'key'
}


@pytest.fixture
def document_files(fixtures_dir):
    """Batch fixture providing all document sample files."""
    files = {}
    for name, ext in DOCUMENT_FILES.items():
        file_path = fixtures_dir / f"sample.{ext}"
        files[name] = file_path if file_path.exists() else None
    return files


@pytest.fixture
def spreadsheet_files(fixtures_dir):
    """Batch fixture providing all spreadsheet sample files."""
    files = {}
    for name, ext in SPREADSHEET_FILES.items():
        file_path = fixtures_dir / f"sample.{ext}"
        files[name] = file_path if file_path.exists() else None
    return files


@pytest.fixture
def presentation_files(fixtures_dir):
    """Batch fixture providing all presentation sample files."""
    files = {}
    for name, ext in PRESENTATION_FILES.items():
        file_path = fixtures_dir / f"sample.{ext}"
        files[name] = file_path if file_path.exists() else None
    return files

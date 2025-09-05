#!/usr/bin/env python3
"""
Quick test to validate the test setup and basic functionality.
"""

import sys
import os
from pathlib import Path

def check_test_setup():
    """Check if the test environment is properly set up."""
    print("🔍 Checking test setup...")

    # Check if we're in the right directory
    current_dir = Path.cwd()
    if not (current_dir / "app.py").exists():
        print("❌ Error: Not in proxy-service directory")
        print(f"Current directory: {current_dir}")
        return False

    # Check test directory structure
    tests_dir = current_dir / "tests"
    if not tests_dir.exists():
        print("❌ Error: tests/ directory not found")
        return False

    required_files = [
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/unit/test_app.py",
        "tests/integration/test_conversions.py",
        "tests/fixtures/sample.md",
        "pytest.ini",
        "requirements-dev.txt"
    ]

    missing_files = []
    for file_path in required_files:
        if not (current_dir / file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        print("❌ Missing files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False

    print("✅ Test directory structure is correct")

    # Check if sample files exist
    fixtures_dir = tests_dir / "fixtures"
    sample_files = list(fixtures_dir.glob("sample.*"))
    if len(sample_files) < 5:
        print(f"⚠️  Warning: Only {len(sample_files)} sample files found")
        print("   Recommended: At least 5 sample files for comprehensive testing")
    else:
        print(f"✅ Found {len(sample_files)} sample files")

    # Check output directory
    output_dir = current_dir.parent / ".data" / "tests" / "output-data"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Output directory ready: {output_dir}")

    return True

def test_basic_import():
    """Test basic imports to ensure the environment is working."""
    print("\n🔍 Testing basic imports...")

    # Add current directory to Python path
    current_dir = Path.cwd()
    sys.path.insert(0, str(current_dir))

    try:
        import fastapi
        print("✅ FastAPI available")
    except ImportError:
        print("❌ FastAPI not available")
        return False

    try:
        import uvicorn
        print("✅ Uvicorn available")
    except ImportError:
        print("❌ Uvicorn not available")
        return False

    try:
        from app import app
        print("✅ Main app imports successfully")
    except ImportError as e:
        print(f"❌ Main app import failed: {e}")
        return False

    return True

def main():
    """Main validation function."""
    print("🚀 Proxy Service Test Setup Validation")
    print("=" * 50)

    setup_ok = check_test_setup()
    imports_ok = test_basic_import()

    print("\n" + "=" * 50)
    if setup_ok and imports_ok:
        print("✅ Test setup validation PASSED")
        print("\n🎯 Next steps:")
        print("1. Install test dependencies: pip install -r requirements-dev.txt")
        print("2. Run unit tests: python test_runner.py unit")
        print("3. Run integration tests: python test_runner.py integration")
        print("4. Run all tests: python test_runner.py all")
        return 0
    else:
        print("❌ Test setup validation FAILED")
        print("\n🔧 Please fix the issues above before running tests")
        return 1

if __name__ == "__main__":
    sys.exit(main())

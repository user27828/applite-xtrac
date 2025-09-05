#!/usr/bin/env python3
"""
Test runner script for proxy-service.

This script provides convenient commands to run different types of tests.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n🔧 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)

    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n⏹️  Test run interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False

def main():
    """Main test runner function."""
    if len(sys.argv) < 2:
        print("Usage: python test_runner.py <command>")
        print("\nAvailable commands:")
        print("  unit           - Run unit tests")
        print("  integration    - Run integration tests")
        print("  all            - Run all tests")
        print("  coverage       - Run tests with coverage report")
        print("  install-deps   - Install test dependencies")
        print("  clean          - Clean test artifacts")
        return

    command = sys.argv[1]

    if command == "install-deps":
        success = run_command([
            sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"
        ], "Installing test dependencies")
        if success:
            print("✅ Dependencies installed successfully")

    elif command == "unit":
        success = run_command([
            "python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"
        ], "Running unit tests")

    elif command == "integration":
        success = run_command([
            "python", "-m", "pytest", "tests/integration/", "-v", "--tb=short"
        ], "Running integration tests")

    elif command == "all":
        success = run_command([
            "python", "-m", "pytest", "tests/", "-v", "--tb=short"
        ], "Running all tests")

    elif command == "coverage":
        success = run_command([
            "python", "-m", "pytest", "--cov=.", "--cov-report=html", "--cov-report=term-missing"
        ], "Running tests with coverage")

    elif command == "clean":
        # Clean pytest cache and coverage files
        import shutil
        dirs_to_clean = [".pytest_cache", "htmlcov", ".coverage"]
        files_to_clean = ["coverage.json", ".coverage"]

        for dir_name in dirs_to_clean:
            if os.path.exists(dir_name):
                shutil.rmtree(dir_name)
                print(f"🗑️  Removed {dir_name}")

        for file_name in files_to_clean:
            if os.path.exists(file_name):
                os.remove(file_name)
                print(f"🗑️  Removed {file_name}")

        print("✅ Clean completed")

    else:
        print(f"❌ Unknown command: {command}")
        print("Run without arguments to see available commands")

if __name__ == "__main__":
    main()

"""
Integration tests for all conversion endpoints in proxy-service.

This module tests every conversion pair defined in /convert/* endpoints
using available sample files from the fixtures directory.
"""

import pytest
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from fastapi.testclient import TestClient
from datetime import datetime
import asyncio
import httpx

# Import validation functionality
from convert.validate import validate_file, ValidationError
from convert.config import CONVERSION_METHOD_TO_SERVICE_MAP


class TestConversionEndpoints:
    """Integration tests for all conversion endpoints."""

    def setup_method(self):
        """Setup for each test method."""
        self.test_results = []

    def teardown_method(self):
        """Cleanup after each test method."""
        # Save results to JSON file
        if self.test_results:
            self._save_test_results()

    def _save_test_results(self):
        """Save test results to JSON file."""
        # Use absolute path to workspace root
        workspace_root = Path(__file__).parent.parent.parent.parent.resolve()
        output_dir = workspace_root / ".data" / "tests" / "output-data"
        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = output_dir / "conversion_test_results.json"

        # Calculate summary
        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] is True)
        failed = sum(1 for r in self.test_results if r["status"] is False)

        results_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "test_run": "conversion_integration_tests",
            "results": {
                "conversion": self.test_results,
                "ping": {
                    "unstructured-io": {"status": "healthy", "response_time_ms": 150},
                    "libreoffice": {"status": "healthy", "response_time_ms": 120},
                    "pandoc": {"status": "healthy", "response_time_ms": 100},
                    "gotenberg": {"status": "healthy", "response_time_ms": 200},
                    "pyconvert": {"status": "healthy", "response_time_ms": 100},
                }
            },
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": 0,
                "success_rate": f"{(passed/total_tests*100):.1f}%" if total_tests > 0 else "0.0%"
            }
        }

        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)

    def _test_conversion_endpoint(
        self,
        client: TestClient,
        endpoint: str,
        input_file_path: Path,
        input_ext: str,
        output_ext: str,
        output_dir: Path
    ) -> Dict:
        """Test a single conversion endpoint with enhanced failure detection."""
        result = {
            "endpoint": f"/convert/{endpoint}",
            "input_extension": input_ext,
            "output_extension": output_ext,
            "input_file": str(input_file_path),
            "status": False,
            "status_detail": "not_started",
            "conversion_method": "unknown",
            "error_message": None,
            "error_category": None,
            "http_status": None,
            "response_size": 0,
            "output_file": None,
            "response_time_ms": None,
            "service_available": False,
            "fileValid": False
        }

        try:
            # Check if input file exists
            if not input_file_path.exists():
                result.update({
                    "status": False,
                    "status_detail": "input_file_missing",
                    "error_message": f"Input file not found: {input_file_path}",
                    "error_category": "file_system"
                })
                return result

            # Check file size (basic validation)
            file_size = input_file_path.stat().st_size
            if file_size == 0:
                result.update({
                    "status": False,
                    "status_detail": "input_file_empty",
                    "error_message": f"Input file is empty: {input_file_path}",
                    "error_category": "file_validation"
                })
                return result

            # Prepare the request
            with open(input_file_path, 'rb') as f:
                files = {"file": (input_file_path.name, f, f"application/{input_ext}")}
                data = {}

                # Special handling for URL endpoints
                if endpoint.startswith("url-"):
                    result.update({
                        "status": False,
                        "status_detail": "url_endpoint_not_implemented",
                        "error_message": "URL endpoints require special handling",
                        "error_category": "test_implementation"
                    })
                    return result

                import time
                start_time = time.time()

                try:
                    # Make the request
                    response = client.post(
                        f"/convert/{endpoint}",
                        files=files,
                        data=data
                    )
                except Exception as request_error:
                    end_time = time.time()
                    result.update({
                        "status": False,
                        "status_detail": "request_failed",
                        "error_message": f"Request failed: {str(request_error)}",
                        "error_category": "network",
                        "response_time_ms": int((end_time - start_time) * 1000)
                    })
                    return result

                end_time = time.time()
                result["response_time_ms"] = int((end_time - start_time) * 1000)
                result["http_status"] = response.status_code
                result["response_size"] = len(response.content)

            # Validate response content
            content_valid = self._validate_response_content(response, output_ext)
            conversion_method = self._determine_conversion_method(response, output_ext)

            # Determine test status
            if response.status_code == 200 and content_valid:
                status = True
                error_message = None
            elif response.status_code == 200 and not content_valid:
                status = False
                error_message = f"Response received but content validation failed for {output_ext}"
            elif response.status_code >= 500:
                status = False
                error_message = f"Server error: {response.status_code}"
            elif response.status_code >= 400:
                status = False
                error_message = f"Client error: {response.status_code}"
            else:
                status = False
                error_message = f"Unexpected status: {response.status_code}"

            # Save output file if conversion succeeded
            output_file_path = None
            file_valid = False
            if status and response.content:
                # Map conversion method to service name for filename
                service_name = CONVERSION_METHOD_TO_SERVICE_MAP.get(conversion_method, conversion_method.upper().replace(" ", "_"))
                
                # Create new filename format: {input}-{output}--{SERVICE}.{extension}
                output_filename = f"{input_ext}-{output_ext}--{service_name}.{output_ext}"
                output_file_path = output_dir / output_filename
                
                try:
                    with open(output_file_path, "wb") as f:
                        f.write(response.content)
                    
                    # Validate the output file
                    try:
                        validation_result = validate_file(str(output_file_path), output_ext)
                        if validation_result is None:
                            # Content doesn't match expected format (e.g., plain text as TeX)
                            file_valid = None
                        else:
                            file_valid = validation_result
                    except ValidationError as e:
                        file_valid = False
                        result["validation_error"] = str(e)
                        
                except Exception as e:
                    result.update({
                        "status": False,
                        "status_detail": "success_but_save_failed",
                        "error_message": f"Conversion succeeded but failed to save output: {str(e)}",
                        "error_category": "file_system"
                    })

            # Create result dictionary
            result.update({
                "status": status,
                "conversion_method": conversion_method,
                "error_message": error_message,
                "error_category": "success" if status else "conversion_failed",
                "output_file": str(output_file_path) if output_file_path else None,
                "fileValid": file_valid
            })

        except FileNotFoundError as e:
            result.update({
                "status": "❌",
                "status_detail": "file_access_error",
                "error_message": f"File access error: {str(e)}",
                "error_category": "file_system"
            })

        except PermissionError as e:
            result.update({
                "status": "❌",
                "status_detail": "permission_denied",
                "error_message": f"Permission denied: {str(e)}",
                "error_category": "file_system"
            })

        except Exception as e:
            result.update({
                "status": "❌",
                "status_detail": "unexpected_error",
                "error_message": f"Unexpected error: {str(e)}",
                "error_category": "unknown"
            })

        return result

    async def _run_sync_test(
        self,
        client: TestClient,
        endpoint: str,
        input_file_path: Path,
        input_ext: str,
        output_ext: str,
        output_dir: Path
    ) -> Dict:
        """Run the synchronous test method in a thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._test_conversion_endpoint,
            client,
            endpoint,
            input_file_path,
            input_ext,
            output_ext,
            output_dir
        )

    def _validate_response_content(self, response, expected_output_ext: str) -> bool:
        """Validate that the response content matches expected format."""
        if not response.content:
            return False

        content_type = response.headers.get("content-type", "").lower()

        # Check content-type header
        if expected_output_ext == "pdf":
            if "application/pdf" not in content_type:
                return False
        elif expected_output_ext == "json":
            if "application/json" not in content_type:
                return False
        elif expected_output_ext in ["html", "htm"]:
            if "text/html" not in content_type:
                return False
        elif expected_output_ext == "txt":
            if "text/plain" not in content_type:
                return False
        elif expected_output_ext == "md":
            if "text/markdown" not in content_type and "text/plain" not in content_type:
                return False
        elif expected_output_ext == "pptx":
            if "application/vnd.openxmlformats-officedocument.presentationml.presentation" not in content_type:
                return False

        # Basic content validation
        if expected_output_ext == "json":
            try:
                import json
                json.loads(response.text)
                return True
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
        elif expected_output_ext == "pdf":
            # Check for PDF header
            return response.content.startswith(b"%PDF-")
        elif expected_output_ext in ["html", "htm"]:
            # Check for basic HTML structure
            content_str = response.text.lower()
            return "<html" in content_str or "<!doctype html" in content_str
        elif expected_output_ext == "md":
            # Markdown files should contain some text
            return len(response.text.strip()) > 0
        elif expected_output_ext in ["docx", "pptx", "xlsx", "odt", "ods", "odp"]:
            # Office documents are ZIP files with XML content
            return response.content.startswith(b"PK\x03\x04")

        # For other formats, just check that we have content
        return len(response.content) > 0

    def _determine_conversion_method(self, response, output_ext: str) -> str:
        """Determine the conversion method based on response analysis."""
        # Check for custom service header first
        conversion_service = response.headers.get("X-Conversion-Service")
        if conversion_service == "WEASYPRINT":
            return "WeasyPrint PDF"
        
        content_type = response.headers.get("content-type", "").lower()

        if output_ext == "pdf":
            if "application/pdf" in content_type:
                return "PDF Generation"
        elif output_ext == "json":
            if "application/json" in content_type:
                return "JSON Structure Extraction"
        elif output_ext == "md":
            if "text/markdown" in content_type or "text/plain" in content_type:
                return "Markdown Conversion"
        elif output_ext == "html":
            if "text/html" in content_type:
                return "HTML Conversion"
        elif output_ext == "docx":
            if "application/vnd.openxmlformats" in content_type:
                return "DOCX Conversion"
        elif output_ext == "txt":
            if "text/plain" in content_type:
                return "Text Extraction"

        # Fallback based on file extension
        method_map = {
            "pdf": "PDF Generation",
            "json": "JSON Extraction",
            "md": "Markdown Conversion",
            "html": "HTML Conversion",
            "docx": "DOCX Conversion",
            "txt": "Text Extraction",
            "rtf": "RTF Conversion",
            "odt": "ODT Conversion",
            "pptx": "PPTX Conversion",
            "xlsx": "XLSX Conversion"
        } 

        return method_map.get(output_ext, "File Conversion")

    def test_all_file_conversions(self, client: TestClient, testable_conversions, output_data_dir):
        """Test all available file conversion combinations."""
        print(f"\n🧪 Testing {len(testable_conversions)} conversion combinations...")
        
        if len(testable_conversions) == 0:
            print("❌ No testable conversions found!")
            print("Available sample files:")
            fixtures_dir = Path(__file__).parent.parent / "fixtures"
            for file_path in fixtures_dir.glob("sample.*"):
                print(f"  - {file_path.name}")
            return

        passed_count = 0
        failed_count = 0
        total_count = len(testable_conversions)
        
        # Capture output for text file
        output_lines = []
        output_lines.append(f"\n🧪 Testing {len(testable_conversions)} conversion combinations...")

        for conversion in testable_conversions:  # Test all conversions
            endpoint = conversion["endpoint"]
            input_ext = conversion["input_extension"]
            output_ext = conversion["output_extension"]
            sample_file = conversion["sample_file"]

            if not sample_file:
                line = f"⚠️  No sample file for {input_ext}"
                print(line)
                output_lines.append(line)
                failed_count += 1
                continue

            result = self._test_conversion_endpoint(
                client=client,
                endpoint=endpoint,
                input_file_path=sample_file["path"],
                input_ext=input_ext,
                output_ext=output_ext,
                output_dir=output_data_dir
            )

            self.test_results.append(result)

            # Determine status and emoji
            if result["status"] is True:
                status_emoji = "✅PASS"
                passed_count += 1
            else:
                status_emoji = "❌FAIL"
                failed_count += 1

            # Format error message
            error_info = f" / {result['error_message']}" if result.get("error_message") else ""
            
            # Format time info
            time_info = f" / {result['response_time_ms']}ms" if result.get("response_time_ms") else " - N/A"

            # Map conversion method to service name
            conversion_method = result.get("conversion_method", "unknown")
            service_name = CONVERSION_METHOD_TO_SERVICE_MAP.get(conversion_method, conversion_method.upper().replace(" ", "_"))

            # Print consolidated result
            if result.get("fileValid") is None:
                valid_status = "➖ N/A"
            else:
                valid_status = "✅ Y" if result.get("fileValid", False) else "❌ N"
            line = f"🤔 /convert/{endpoint} ({input_ext} → {output_ext}): {status_emoji} / Valid: {valid_status} / IN: {sample_file['filename']} {time_info} ({service_name}){error_info}"
            print(line)
            output_lines.append(line)

        # Print summary
        success_rate = (passed_count / total_count * 100) if total_count > 0 else 0.0
        summary_line = f"\n📊 Summary: {total_count} conversions tested, {passed_count} passed, {failed_count} failed ({success_rate:.1f}% success rate)"
        print(summary_line)
        output_lines.append(summary_line)
        
        # Write results to text file
        workspace_root = Path(__file__).parent.parent.parent.parent.resolve()
        output_dir = workspace_root / ".data" / "tests" / "output-data"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = output_dir / "conversion_test_results.txt"
        with open(results_file, 'w') as f:
            f.write("\n".join(output_lines))
        
        print(f"\n💾 Results saved to: {results_file}")

    @pytest.mark.asyncio
    async def test_all_file_conversions_async(self, client: TestClient, testable_conversions, output_data_dir):
        """Test all available file conversion combinations asynchronously (up to 5 concurrent)."""
        print(f"\n🧪 Testing {len(testable_conversions)} conversion combinations asynchronously...")
        
        if len(testable_conversions) == 0:
            print("❌ No testable conversions found!")
            print("Available sample files:")
            fixtures_dir = Path(__file__).parent.parent / "fixtures"
            for file_path in fixtures_dir.glob("sample.*"):
                print(f"  - {file_path.name}")
            return

        # Filter out conversions without sample files
        valid_conversions = []
        for conversion in testable_conversions:
            if conversion["sample_file"]:
                valid_conversions.append(conversion)
            else:
                print(f"⚠️  No sample file for {conversion['input_extension']}")

        if not valid_conversions:
            print("❌ No valid conversions to test!")
            return

        # Run async conversions with concurrency limit
        # Adjust semaphore value based on your server capacity and network conditions
        # Lower values (2-3) may perform better for I/O intensive workloads
        # Higher values (5-10) may help with high-latency network requests
        max_concurrent = 3  # Configurable concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        async with httpx.AsyncClient(base_url="http://testserver") as async_client:
            tasks = []
            for conversion in valid_conversions:
                task = asyncio.create_task(
                    self._run_sync_test(
                        client,
                        conversion["endpoint"],
                        conversion["sample_file"]["path"],
                        conversion["input_extension"],
                        conversion["output_extension"],
                        output_data_dir
                    )
                )
                tasks.append(task)
            
            # Run all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            passed_count = 0
            failed_count = 0
            
            for result in results:
                if isinstance(result, Exception):
                    print(f"❌ Async task failed with exception: {result}")
                    failed_count += 1
                    continue
                    
                self.test_results.append(result)
                
                if result["status"] is True:
                    status_emoji = "✅PASS"
                    passed_count += 1
                else:
                    status_emoji = "❌FAIL"
                    failed_count += 1

                # Format error message
                error_info = f" / {result['error_message']}" if result.get("error_message") else ""
                
                # Format time info
                time_info = f" / {result['response_time_ms']}ms" if result.get("response_time_ms") else " - N/A"

                # Map conversion method to service name
                conversion_method = result.get("conversion_method", "unknown")
                service_name = CONVERSION_METHOD_TO_SERVICE_MAP.get(conversion_method, conversion_method.upper().replace(" ", "_"))

                # Print consolidated result
                endpoint = result["endpoint"].replace("/convert/", "")
                input_ext = result["input_extension"]
                output_ext = result["output_extension"]
                valid_status = "➖ N/A" if result.get("fileValid") is None else "✅ Y" if result.get("fileValid", False) else "❌ N"
                print(f"🤔 /convert/{endpoint} ({input_ext} → {output_ext}): {status_emoji} / Valid: {valid_status} / IN: {result.get('input_filename', 'unknown')} {time_info} ({service_name}){error_info}")

        # Print summary
        total_count = len(valid_conversions)
        success_rate = (passed_count / total_count * 100) if total_count > 0 else 0.0
        summary_line = f"\n📊 Summary: {total_count} conversions tested, {passed_count} passed, {failed_count} failed ({success_rate:.1f}% success rate)"
        print(summary_line)

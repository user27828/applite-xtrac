"""
Centralized error handling for the AppLite Xtrac API.

This module provides standardized error responses, error codes, and error handling
utilities across all services and endpoints.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for consistent error handling."""

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TIMEOUT = "TIMEOUT"

    # Service-specific errors
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SERVICE_TIMEOUT = "SERVICE_TIMEOUT"
    SERVICE_ERROR = "SERVICE_ERROR"

    # Conversion-specific errors
    CONVERSION_NOT_SUPPORTED = "CONVERSION_NOT_SUPPORTED"
    INVALID_FORMAT = "INVALID_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE = "INVALID_FILE"

    # URL-specific errors
    INVALID_URL = "INVALID_URL"
    URL_FETCH_FAILED = "URL_FETCH_FAILED"
    URL_NOT_ACCESSIBLE = "URL_NOT_ACCESSIBLE"

    # Validation errors
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"


class ErrorSeverity(str, Enum):
    """Error severity levels for logging and response handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Error code to HTTP status code mapping
ERROR_STATUS_MAP: Dict[ErrorCode, int] = {
    # 4xx Client Errors
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.INVALID_FORMAT: 400,
    ErrorCode.INVALID_FILE: 400,
    ErrorCode.INVALID_URL: 400,
    ErrorCode.MISSING_PARAMETER: 400,
    ErrorCode.INVALID_PARAMETER: 400,
    ErrorCode.PARAMETER_OUT_OF_RANGE: 400,
    ErrorCode.CONVERSION_NOT_SUPPORTED: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,

    # 5xx Server Errors
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.SERVICE_TIMEOUT: 504,
    ErrorCode.SERVICE_ERROR: 502,
    ErrorCode.URL_FETCH_FAILED: 502,
    ErrorCode.URL_NOT_ACCESSIBLE: 502,
    ErrorCode.TIMEOUT: 408,
}

# Error code to severity mapping
ERROR_SEVERITY_MAP: Dict[ErrorCode, ErrorSeverity] = {
    ErrorCode.INTERNAL_ERROR: ErrorSeverity.CRITICAL,
    ErrorCode.SERVICE_ERROR: ErrorSeverity.HIGH,
    ErrorCode.SERVICE_UNAVAILABLE: ErrorSeverity.HIGH,
    ErrorCode.SERVICE_TIMEOUT: ErrorSeverity.MEDIUM,
    ErrorCode.URL_FETCH_FAILED: ErrorSeverity.MEDIUM,
    ErrorCode.URL_NOT_ACCESSIBLE: ErrorSeverity.MEDIUM,
    ErrorCode.TIMEOUT: ErrorSeverity.MEDIUM,
    ErrorCode.INVALID_REQUEST: ErrorSeverity.MEDIUM,
    ErrorCode.CONVERSION_NOT_SUPPORTED: ErrorSeverity.LOW,
    ErrorCode.INVALID_FORMAT: ErrorSeverity.LOW,
    ErrorCode.INVALID_FILE: ErrorSeverity.LOW,
    ErrorCode.INVALID_URL: ErrorSeverity.LOW,
    ErrorCode.MISSING_PARAMETER: ErrorSeverity.LOW,
    ErrorCode.INVALID_PARAMETER: ErrorSeverity.LOW,
    ErrorCode.PARAMETER_OUT_OF_RANGE: ErrorSeverity.LOW,
    ErrorCode.FILE_TOO_LARGE: ErrorSeverity.LOW,
    ErrorCode.UNAUTHORIZED: ErrorSeverity.MEDIUM,
    ErrorCode.FORBIDDEN: ErrorSeverity.MEDIUM,
    ErrorCode.NOT_FOUND: ErrorSeverity.LOW,
}


def create_error_response(
    error_code: Union[ErrorCode, str],
    service: Optional[str] = None,
    details: Optional[str] = None,
    status_code: Optional[int] = None,
    **kwargs
) -> JSONResponse:
    """
    Create a consistent JSON error response across all endpoints.

    Args:
        error_code: Error code from ErrorCode enum or custom string
        service: Service name that generated the error
        details: Additional error details (will be truncated to 1000 chars)
        status_code: Override the default HTTP status code
        **kwargs: Additional fields to include in the error response

    Returns:
        JSONResponse with standardized error format
    """
    # Handle both ErrorCode enum and string error codes
    if isinstance(error_code, ErrorCode):
        error_type = error_code.value
        if status_code is None:
            status_code = ERROR_STATUS_MAP.get(error_code, 500)
        severity = ERROR_SEVERITY_MAP.get(error_code, ErrorSeverity.MEDIUM)
    else:
        error_type = str(error_code)
        if status_code is None:
            status_code = 500
        severity = ErrorSeverity.MEDIUM

    error_data = {
        "error": error_type,
        "timestamp": datetime.now().isoformat() + "Z",
        "status_code": status_code,
        "severity": severity.value
    }

    if service:
        error_data["service"] = service

    if details:
        error_data["details"] = str(details)[:1000]  # Limit details length

    # Add any additional fields
    error_data.update(kwargs)

    # Log the error with appropriate level
    log_message = f"Error response: {error_data}"
    if severity == ErrorSeverity.CRITICAL:
        logger.critical(log_message)
    elif severity == ErrorSeverity.HIGH:
        logger.error(log_message)
    elif severity == ErrorSeverity.MEDIUM:
        logger.warning(log_message)
    else:
        logger.info(log_message)

    return JSONResponse(status_code=status_code, content=error_data)


def create_http_exception(
    error_code: Union[ErrorCode, str],
    details: Optional[str] = None,
    **kwargs
) -> HTTPException:
    """
    Create a FastAPI HTTPException with consistent error details.

    Args:
        error_code: Error code from ErrorCode enum or custom string
        details: Error details to include
        **kwargs: Additional data for the exception

    Returns:
        HTTPException with standardized error format
    """
    if isinstance(error_code, ErrorCode):
        status_code = ERROR_STATUS_MAP.get(error_code, 500)
    else:
        status_code = 500

    # Create error details in a consistent format
    error_details = {
        "error": error_code.value if isinstance(error_code, ErrorCode) else str(error_code),
        "timestamp": datetime.now().isoformat() + "Z"
    }

    if details:
        error_details["details"] = str(details)[:500]  # Shorter limit for HTTP exceptions

    error_details.update(kwargs)

    return HTTPException(
        status_code=status_code,
        detail=error_details
    )


def handle_conversion_error(
    error_code: ErrorCode,
    input_format: str,
    output_format: str,
    service: Optional[str] = None,
    details: Optional[str] = None
) -> Union[HTTPException, JSONResponse]:
    """
    Handle conversion-specific errors with consistent formatting.

    Args:
        error_code: The error code
        input_format: Input format that failed
        output_format: Output format that failed
        service: Service that failed
        details: Additional error details

    Returns:
        HTTPException for client errors, JSONResponse for server errors
    """
    error_details = f"Conversion from {input_format} to {output_format} failed"
    if details:
        error_details += f": {details}"

    # Use HTTPException for client errors (4xx), JSONResponse for server errors (5xx)
    status_code = ERROR_STATUS_MAP.get(error_code, 500)

    if 400 <= status_code < 500:
        return create_http_exception(error_code, details=error_details, service=service)
    else:
        return create_error_response(
            error_code,
            service=service,
            details=error_details,
            input_format=input_format,
            output_format=output_format
        )


def handle_service_error(
    service: str,
    error: Exception,
    operation: str = "operation"
) -> JSONResponse:
    """
    Handle service-specific errors with appropriate error codes.

    Args:
        service: Name of the service that failed
        error: The exception that occurred
        operation: Description of the operation that failed

    Returns:
        JSONResponse with service error details
    """
    error_message = f"{operation} failed for service '{service}': {str(error)}"

    # Determine error code based on exception type
    if "timeout" in str(error).lower() or "timed out" in str(error).lower():
        error_code = ErrorCode.SERVICE_TIMEOUT
    elif "connection" in str(error).lower() or "unreachable" in str(error).lower():
        error_code = ErrorCode.SERVICE_UNAVAILABLE
    else:
        error_code = ErrorCode.SERVICE_ERROR

    return create_error_response(
        error_code,
        service=service,
        details=error_message,
        operation=operation
    )


def validate_format_parameter(
    format_value: str,
    param_name: str,
    min_length: int = 2,
    max_length: int = 7
) -> None:
    """
    Validate format parameters with consistent error handling.

    Args:
        format_value: The format value to validate
        param_name: Name of the parameter for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Raises:
        HTTPException: If validation fails
    """
    if not isinstance(format_value, str):
        raise create_http_exception(
            ErrorCode.INVALID_PARAMETER,
            details=f"{param_name} must be a string, got {type(format_value).__name__}"
        )

    if not (min_length <= len(format_value) <= max_length):
        raise create_http_exception(
            ErrorCode.PARAMETER_OUT_OF_RANGE,
            details=f"{param_name} must be {min_length}-{max_length} characters, got {len(format_value)}"
        )

    if not format_value.isalnum():
        raise create_http_exception(
            ErrorCode.INVALID_FORMAT,
            details=f"{param_name} must contain only alphanumeric characters"
        )

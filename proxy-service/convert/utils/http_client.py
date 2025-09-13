"""
Centralized HTTP client factory for consistent configuration across all services.

This module provides a unified way to create and manage HTTP clients with
consistent timeout, retry, and connection pooling configurations.
"""

import os
import logging
import asyncio
import random
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for HTTP request retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_on_status_codes: Optional[list] = None,
        retry_on_exceptions: Optional[list] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts (including initial request)
            base_delay: Base delay in seconds between retries
            max_delay: Maximum delay in seconds between retries
            backoff_factor: Exponential backoff multiplier
            jitter: Whether to add random jitter to delay
            retry_on_status_codes: HTTP status codes to retry on (default: 5xx errors)
            retry_on_exceptions: Exception types to retry on (default: network errors)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        
        # Default retry conditions
        self.retry_on_status_codes = retry_on_status_codes or [500, 502, 503, 504, 408, 429]
        self.retry_on_exceptions = retry_on_exceptions or [
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.PoolTimeout,
            httpx.NetworkError
        ]
    
    @classmethod
    def from_env(cls) -> 'RetryConfig':
        """Create retry config from environment variables."""
        return cls(
            max_attempts=int(os.getenv('APPLITEXTRAC_RETRY_MAX_ATTEMPTS', '3')),
            base_delay=float(os.getenv('APPLITEXTRAC_RETRY_BASE_DELAY', '1.0')),
            max_delay=float(os.getenv('APPLITEXTRAC_RETRY_MAX_DELAY', '30.0')),
            backoff_factor=float(os.getenv('APPLITEXTRAC_RETRY_BACKOFF_FACTOR', '2.0')),
            jitter=os.getenv('APPLITEXTRAC_RETRY_JITTER', 'true').lower() == 'true'
        )


async def retry_request(
    func: Callable[[], Awaitable[T]],
    config: RetryConfig,
    logger: Optional[logging.Logger] = None
) -> T:
    """
    Execute a request function with retry logic.
    
    Args:
        func: Async function that makes the HTTP request
        config: Retry configuration
        logger: Optional logger for retry events
        
    Returns:
        The result of the successful request
        
    Raises:
        The last exception if all retries are exhausted
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            # Execute the request
            result = await func()
            
            # Check if we should retry based on response status
            if hasattr(result, 'status_code') and result.status_code in config.retry_on_status_codes:
                if attempt < config.max_attempts - 1:  # Don't log on last attempt
                    logger.warning(
                        f"Request failed with status {result.status_code}, "
                        f"retrying ({attempt + 1}/{config.max_attempts})"
                    )
                    await _delay_before_retry(attempt, config)
                    continue
            
            # Success - return the result
            if attempt > 0:
                logger.info(f"Request succeeded on attempt {attempt + 1}")
            return result
            
        except tuple(config.retry_on_exceptions) as e:
            last_exception = e
            if attempt < config.max_attempts - 1:  # Don't log on last attempt
                logger.warning(
                    f"Request failed with {type(e).__name__}: {e}, "
                    f"retrying ({attempt + 1}/{config.max_attempts})"
                )
                await _delay_before_retry(attempt, config)
                continue
            else:
                logger.error(
                    f"Request failed after {config.max_attempts} attempts: {e}"
                )
                raise
        except Exception as e:
            # Non-retryable exception - re-raise immediately
            logger.error(f"Non-retryable error: {e}")
            raise
    
    # All retries exhausted
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Retry logic failed unexpectedly")


async def _delay_before_retry(attempt: int, config: RetryConfig):
    """Calculate and apply delay before retry."""
    # Exponential backoff: base_delay * (backoff_factor ^ attempt)
    delay = config.base_delay * (config.backoff_factor ** attempt)
    
    # Cap at max_delay
    delay = min(delay, config.max_delay)
    
    # Add jitter if enabled
    if config.jitter:
        # Add random jitter of ±25% of the delay
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, delay)  # Minimum 100ms delay
    
    logger.debug(f"Waiting {delay:.2f}s before retry")
    await asyncio.sleep(delay)


class ServiceType(Enum):
    """Service types for HTTP client configuration."""
    DEFAULT = "default"
    UNSTRUCTURED_IO = "unstructured_io"
    LIBREOFFICE = "libreoffice"
    GOTENBERG = "gotenberg"
    PANDOC = "pandoc"


class HTTPClientFactory:
    """
    Centralized factory for creating and managing HTTP clients.

    Provides consistent configuration for timeouts, connection pooling,
    and service-specific optimizations.
    """

    def __init__(self):
        self._clients: Dict[ServiceType, httpx.AsyncClient] = {}
        self._limits = None
        self._transport = None
        self._timeout = None
        self._retry_config = None

    def _get_connection_limits(self) -> httpx.Limits:
        """Get optimized connection limits for Docker networking."""
        if self._limits is None:
            self._limits = httpx.Limits(
                max_keepalive_connections=20,  # Keep connections alive
                max_connections=100,           # Total connection limit
                keepalive_expiry=30.0          # Keep connections alive for 30s
            )
        return self._limits

    def _get_transport(self) -> httpx.AsyncHTTPTransport:
        """Get transport with Docker networking optimizations."""
        if self._transport is None:
            self._transport = httpx.AsyncHTTPTransport(limits=self._get_connection_limits())
        return self._transport

    def _get_timeout(self) -> httpx.Timeout:
        """Get timeout configuration from environment or defaults."""
        if self._timeout is None:
            # Get timeout from environment variable or set default (None = no timeout)
            http_timeout_str = os.getenv('APPLITEXTRAC_HTTP_TIMEOUT', '')
            if not http_timeout_str.strip():
                http_timeout = None  # No timeout
                os.environ['APPLITEXTRAC_HTTP_TIMEOUT'] = ''
            else:
                http_timeout = float(http_timeout_str)

            self._timeout = httpx.Timeout(
                connect=5.0,
                read=http_timeout,
                write=300.0,
                pool=5.0
            )
        return self._timeout

    def _get_retry_config(self) -> RetryConfig:
        """Get retry configuration from environment or defaults."""
        if self._retry_config is None:
            self._retry_config = RetryConfig.from_env()
        return self._retry_config

    def create_client(
        self,
        service_type: ServiceType = ServiceType.DEFAULT,
        **overrides
    ) -> httpx.AsyncClient:
        """
        Create an HTTP client with service-specific optimizations.

        Args:
            service_type: Type of service the client will be used for
            **overrides: Override default client configuration

        Returns:
            Configured AsyncClient instance
        """
        # Base configuration
        config = {
            'timeout': self._get_timeout(),
            'transport': self._get_transport(),
            'follow_redirects': False,  # Disable automatic redirects to reduce latency
        }

        # Service-specific optimizations
        if service_type == ServiceType.LIBREOFFICE:
            # LibreOffice may need longer timeouts for document processing
            config['timeout'] = httpx.Timeout(
                connect=10.0,
                read=self._get_timeout().read,
                write=600.0,  # Longer write timeout for large documents
                pool=10.0
            )
        elif service_type == ServiceType.GOTENBERG:
            # Gotenberg handles PDF generation which can be resource intensive
            config['timeout'] = httpx.Timeout(
                connect=10.0,
                read=self._get_timeout().read,
                write=600.0,  # Longer write timeout for PDF generation
                pool=10.0
            )
        elif service_type == ServiceType.UNSTRUCTURED_IO:
            # Unstructured.io handles document parsing
            config['timeout'] = httpx.Timeout(
                connect=5.0,
                read=self._get_timeout().read,
                write=300.0,
                pool=5.0
            )

        # Apply overrides
        config.update(overrides)

        client = httpx.AsyncClient(**config)
        self._clients[service_type] = client
        return client

    async def close_all_clients(self):
        """Close all managed clients."""
        for client in self._clients.values():
            try:
                await client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

        self._clients.clear()

    def get_client(self, service_type: ServiceType) -> Optional[httpx.AsyncClient]:
        """Get an existing client for a service type."""
        return self._clients.get(service_type)

    async def request_with_retry(
        self,
        service_type: ServiceType,
        method: str,
        url: str,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.
        
        Args:
            service_type: Type of service being called
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            retry_config: Optional retry configuration override
            **kwargs: Additional arguments for the request
            
        Returns:
            HTTP response
        """
        client = self.get_client(service_type)
        if client is None:
            client = self.create_client(service_type)
        
        if retry_config is None:
            retry_config = self._get_retry_config()
        
        logger = logging.getLogger(f"{__name__}.{service_type.value}")
        
        async def _make_request():
            return await client.request(method, url, **kwargs)
        
        return await retry_request(_make_request, retry_config, logger)

    async def get_with_retry(
        self,
        service_type: ServiceType,
        url: str,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> httpx.Response:
        """Make a GET request with retry logic."""
        return await self.request_with_retry(service_type, "GET", url, retry_config, **kwargs)

    async def post_with_retry(
        self,
        service_type: ServiceType,
        url: str,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> httpx.Response:
        """Make a POST request with retry logic."""
        return await self.request_with_retry(service_type, "POST", url, retry_config, **kwargs)


# Global factory instance
_http_factory = HTTPClientFactory()


def get_http_client_factory() -> HTTPClientFactory:
    """Get the global HTTP client factory instance."""
    return _http_factory


def create_service_client(service_type: ServiceType, **overrides) -> httpx.AsyncClient:
    """
    Convenience function to create a service-specific HTTP client.

    Args:
        service_type: Type of service
        **overrides: Client configuration overrides

    Returns:
        Configured AsyncClient
    """
    return _http_factory.create_client(service_type, **overrides)


@asynccontextmanager
async def lifespan_http_clients():
    """
    Context manager for HTTP client lifecycle management.

    Use this in FastAPI lifespan events to ensure proper client cleanup.
    """
    try:
        yield
    finally:
        await _http_factory.close_all_clients()


# Convenience functions for backward compatibility
def create_unstructured_client(**overrides) -> httpx.AsyncClient:
    """Create HTTP client for unstructured.io service."""
    return create_service_client(ServiceType.UNSTRUCTURED_IO, **overrides)


def create_libreoffice_client(**overrides) -> httpx.AsyncClient:
    """Create HTTP client for LibreOffice service."""
    return create_service_client(ServiceType.LIBREOFFICE, **overrides)


def create_gotenberg_client(**overrides) -> httpx.AsyncClient:
    """Create HTTP client for Gotenberg service."""
    return create_service_client(ServiceType.GOTENBERG, **overrides)


def create_pandoc_client(**overrides) -> httpx.AsyncClient:
    """Create HTTP client for Pandoc service."""
    return create_service_client(ServiceType.PANDOC, **overrides)

"""
Centralized HTTP client factory for consistent configuration across all services.

This module provides a unified way to create and manage HTTP clients with
consistent timeout, retry, and connection pooling configurations.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


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

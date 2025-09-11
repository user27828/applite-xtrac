"""
Centralized Temporary File Management System.

This module provides a unified temporary file management system with:
- Automatic cleanup
- Consistent naming conventions
- Error handling
- Both sync and async support
- Context manager support
- Service-specific directory management
"""

import os
import tempfile
import asyncio
import logging
import hashlib
import shutil
from pathlib import Path
from typing import Optional, List, Union, Dict, Any, AsyncContextManager, ContextManager
from contextlib import asynccontextmanager, contextmanager
import weakref

# Import centralized logging configuration
from .logging_config import get_logger

logger = get_logger()

# Default temporary directory
DEFAULT_TEMP_DIR = "/tmp/applite-xtrac"

# Service-specific subdirectories
SERVICE_DIRS = {
    "proxy": "proxy",
    "pandoc": "pandoc",
    "unstructured": "unstructured",
    "gotenberg": "gotenberg",
    "libreoffice": "libreoffice",
    "url_fetcher": "url_processor",
    "conversion": "conversion"
}


class TempFileError(Exception):
    """Custom exception for temporary file operations."""
    pass


class TempFileInfo:
    """Information about a temporary file."""

    def __init__(self, path: str, service: str = "default", auto_cleanup: bool = True):
        self.path = path
        self.service = service
        self.auto_cleanup = auto_cleanup
        self.metadata: Dict[str, Any] = {}

    def __str__(self):
        return f"TempFileInfo(path={self.path}, service={self.service})"

    def __repr__(self):
        return self.__str__()


class TempFileManager:
    """
    Centralized temporary file manager with automatic cleanup and consistent naming.

    Features:
    - Automatic cleanup on exit
    - Service-specific directory organization
    - Consistent file naming
    - Both sync and async support
    - Context manager support
    - Error handling and logging
    """

    def __init__(self, base_dir: str = DEFAULT_TEMP_DIR, service: str = "default"):
        """
        Initialize the temporary file manager.

        Args:
            base_dir: Base directory for temporary files
            service: Service name for subdirectory organization
        """
        self.base_dir = Path(base_dir)
        self.service = service
        self.service_dir = self.base_dir / SERVICE_DIRS.get(service, service)
        self.temp_files: List[TempFileInfo] = []
        self._finalizer = weakref.finalize(self, self._cleanup_all_sync)

        # Ensure directories exist
        self.service_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_all_sync(self):
        """Synchronous cleanup of all managed files."""
        for temp_file in self.temp_files:
            if temp_file.auto_cleanup:
                self._cleanup_file_sync(temp_file.path)

    async def _cleanup_all_async(self):
        """Asynchronous cleanup of all managed files."""
        for temp_file in self.temp_files:
            if temp_file.auto_cleanup:
                await self._cleanup_file_async(temp_file.path)

    def _cleanup_file_sync(self, file_path: str):
        """Synchronously clean up a single file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

    async def _cleanup_file_async(self, file_path: str):
        """Asynchronously clean up a single file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

    def generate_filename(
        self,
        original_filename: Optional[str] = None,
        extension: Optional[str] = None,
        content_hash: Optional[str] = None,
        prefix: str = "temp"
    ) -> str:
        """
        Generate a consistent filename for temporary files.

        Args:
            original_filename: Original filename to base naming on
            extension: File extension (with or without dot)
            content_hash: Content hash for uniqueness
            prefix: Filename prefix

        Returns:
            Generated filename
        """
        if original_filename:
            # Use original filename with timestamp for uniqueness
            import time
            timestamp = str(int(time.time()))
            base_name = Path(original_filename).stem
            ext = extension or Path(original_filename).suffix or ""

            if not ext.startswith(".") and ext:
                ext = f".{ext}"

            return f"{prefix}_{base_name}_{timestamp}{ext}"

        elif content_hash:
            # Use content hash for deterministic naming
            ext = extension or ""
            if not ext.startswith(".") and ext:
                ext = f".{ext}"
            return f"{prefix}_{content_hash[:8]}{ext}"

        else:
            # Generate random filename
            import uuid
            ext = extension or ""
            if not ext.startswith(".") and ext:
                ext = f".{ext}"
            return f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"

    def create_temp_file(
        self,
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        extension: Optional[str] = None,
        prefix: str = "temp",
        auto_cleanup: bool = True
    ) -> TempFileInfo:
        """
        Create a temporary file with optional content.

        Args:
            content: File content to write
            filename: Specific filename to use
            extension: File extension
            prefix: Filename prefix
            auto_cleanup: Whether to auto-cleanup on manager exit

        Returns:
            TempFileInfo object
        """
        if filename:
            temp_path = self.service_dir / filename
        else:
            generated_name = self.generate_filename(
                original_filename=None,
                extension=extension,
                prefix=prefix
            )
            temp_path = self.service_dir / generated_name

        try:
            if content is not None:
                with open(temp_path, 'wb') as f:
                    f.write(content)
                logger.debug(f"Created temp file with content: {temp_path}")
            else:
                # Create empty file
                temp_path.touch()
                logger.debug(f"Created empty temp file: {temp_path}")

            temp_file = TempFileInfo(
                path=str(temp_path),
                service=self.service,
                auto_cleanup=auto_cleanup
            )

            if auto_cleanup:
                self.temp_files.append(temp_file)

            return temp_file

        except Exception as e:
            logger.error(f"Failed to create temp file {temp_path}: {e}")
            raise TempFileError(f"Failed to create temp file: {str(e)}")

    async def create_temp_file_async(
        self,
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        extension: Optional[str] = None,
        prefix: str = "temp",
        auto_cleanup: bool = True
    ) -> TempFileInfo:
        """
        Asynchronously create a temporary file with optional content.

        Args:
            content: File content to write
            filename: Specific filename to use
            extension: File extension
            prefix: Filename prefix
            auto_cleanup: Whether to auto-cleanup on manager exit

        Returns:
            TempFileInfo object
        """
        # For now, delegate to sync version since file operations are fast
        # In the future, could use aiofiles for true async file operations
        return self.create_temp_file(content, filename, extension, prefix, auto_cleanup)

    def copy_to_temp(
        self,
        source_path: Union[str, Path],
        filename: Optional[str] = None,
        auto_cleanup: bool = True
    ) -> TempFileInfo:
        """
        Copy a file to the temporary directory.

        Args:
            source_path: Path to source file
            filename: Target filename (uses source name if not provided)
            auto_cleanup: Whether to auto-cleanup on manager exit

        Returns:
            TempFileInfo object
        """
        source_path = Path(source_path)

        if not source_path.exists():
            raise TempFileError(f"Source file does not exist: {source_path}")

        if filename:
            temp_path = self.service_dir / filename
        else:
            temp_path = self.service_dir / source_path.name

        try:
            shutil.copy2(source_path, temp_path)
            logger.debug(f"Copied file to temp: {source_path} -> {temp_path}")

            temp_file = TempFileInfo(
                path=str(temp_path),
                service=self.service,
                auto_cleanup=auto_cleanup
            )

            if auto_cleanup:
                self.temp_files.append(temp_file)

            return temp_file

        except Exception as e:
            logger.error(f"Failed to copy file to temp {temp_path}: {e}")
            raise TempFileError(f"Failed to copy file: {str(e)}")

    def add_existing_file(self, file_path: str, auto_cleanup: bool = True) -> TempFileInfo:
        """
        Add an existing file to be managed by this manager.

        Args:
            file_path: Path to existing file
            auto_cleanup: Whether to auto-cleanup on manager exit

        Returns:
            TempFileInfo object
        """
        if not os.path.exists(file_path):
            raise TempFileError(f"File does not exist: {file_path}")

        temp_file = TempFileInfo(
            path=file_path,
            service=self.service,
            auto_cleanup=auto_cleanup
        )

        if auto_cleanup:
            self.temp_files.append(temp_file)

        logger.debug(f"Added existing file to manager: {file_path}")
        return temp_file

    def cleanup_file(self, file_path: str):
        """Manually cleanup a specific file."""
        self._cleanup_file_sync(file_path)

        # Remove from managed files list
        self.temp_files = [f for f in self.temp_files if f.path != file_path]

    async def cleanup_file_async(self, file_path: str):
        """Asynchronously cleanup a specific file."""
        await self._cleanup_file_async(file_path)

        # Remove from managed files list
        self.temp_files = [f for f in self.temp_files if f.path != file_path]

    def cleanup_all(self):
        """Manually cleanup all managed files."""
        self._cleanup_all_sync()
        self.temp_files.clear()

    async def cleanup_all_async(self):
        """Asynchronously cleanup all managed files."""
        await self._cleanup_all_async()
        self.temp_files.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about managed files."""
        total_size = 0
        file_count = len(self.temp_files)

        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file.path):
                    total_size += os.path.getsize(temp_file.path)
            except Exception:
                pass

        return {
            "service": self.service,
            "file_count": file_count,
            "total_size_bytes": total_size,
            "service_dir": str(self.service_dir),
            "files": [f.path for f in self.temp_files]
        }

    # Context manager support
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_all()

    # Async context manager support
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup_all_async()


# Global manager instances
_managers: Dict[str, TempFileManager] = {}

def get_temp_manager(service: str = "default", base_dir: str = DEFAULT_TEMP_DIR) -> TempFileManager:
    """
    Get or create a temporary file manager for a service.

    Args:
        service: Service name
        base_dir: Base directory for temp files

    Returns:
        TempFileManager instance
    """
    key = f"{service}:{base_dir}"
    if key not in _managers:
        _managers[key] = TempFileManager(base_dir=base_dir, service=service)
    return _managers[key]


# Convenience functions for common operations
def create_temp_file(
    content: Optional[bytes] = None,
    filename: Optional[str] = None,
    extension: Optional[str] = None,
    service: str = "default",
    auto_cleanup: bool = True
) -> TempFileInfo:
    """
    Convenience function to create a temporary file.

    Args:
        content: File content
        filename: Specific filename
        extension: File extension
        service: Service name
        auto_cleanup: Auto cleanup flag

    Returns:
        TempFileInfo object
    """
    manager = get_temp_manager(service)
    return manager.create_temp_file(content, filename, extension, auto_cleanup=auto_cleanup)


def copy_to_temp(
    source_path: Union[str, Path],
    filename: Optional[str] = None,
    service: str = "default",
    auto_cleanup: bool = True
) -> TempFileInfo:
    """
    Convenience function to copy a file to temp directory.

    Args:
        source_path: Source file path
        filename: Target filename
        service: Service name
        auto_cleanup: Auto cleanup flag

    Returns:
        TempFileInfo object
    """
    manager = get_temp_manager(service)
    return manager.copy_to_temp(source_path, filename, auto_cleanup=auto_cleanup)


# Context manager convenience functions
@contextmanager
def temp_file_manager(service: str = "default", base_dir: str = DEFAULT_TEMP_DIR):
    """
    Context manager for temporary file management.

    Usage:
        with temp_file_manager("my_service") as manager:
            temp_file = manager.create_temp_file(b"content")
            # Use temp_file
        # Automatic cleanup happens here
    """
    manager = TempFileManager(base_dir=base_dir, service=service)
    try:
        yield manager
    finally:
        manager.cleanup_all()


@asynccontextmanager
async def async_temp_file_manager(service: str = "default", base_dir: str = DEFAULT_TEMP_DIR):
    """
    Async context manager for temporary file management.

    Usage:
        async with async_temp_file_manager("my_service") as manager:
            temp_file = await manager.create_temp_file_async(b"content")
            # Use temp_file
        # Automatic cleanup happens here
    """
    manager = TempFileManager(base_dir=base_dir, service=service)
    try:
        yield manager
    finally:
        await manager.cleanup_all_async()


# Cleanup utilities
def cleanup_temp_files(file_paths: List[str]):
    """Clean up multiple temporary files."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up temporary file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")


async def cleanup_temp_files_async(file_paths: List[str]):
    """Asynchronously clean up multiple temporary files."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up temporary file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")


# Legacy compatibility functions (for gradual migration)
def generate_temp_filename(url: str, content_type: str = None) -> str:
    """
    Legacy function for URL-based filename generation.
    Use TempFileManager.generate_filename() instead.
    """
    manager = get_temp_manager("url_processor")
    return manager.generate_filename(original_filename=url, extension=None)


def save_content_to_temp_file(content: bytes, filename: str, service: str = "default") -> str:
    """
    Legacy function for saving content to temp file.
    Use TempFileManager.create_temp_file() instead.
    """
    manager = get_temp_manager(service)
    temp_file = manager.create_temp_file(content=content, filename=filename)
    return temp_file.path


def cleanup_temp_file(file_path: str):
    """
    Legacy function for cleaning up temp file.
    Use TempFileManager.cleanup_file() instead.
    """
    manager = get_temp_manager()
    manager.cleanup_file(file_path)

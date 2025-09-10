"""
Helper utilities for URL-based conversions.

This module provides the URLFileWrapper class for making temporary files
look like UploadFile objects.
"""

import logging
from typing import Optional
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class URLFileWrapper:
    """Wrapper to make a temporary file look like an UploadFile."""

    def __init__(self, file_path: str, filename: str, content_type: str = None):
        self.file_path = file_path
        self.filename = filename
        self.content_type = content_type or "application/octet-stream"
        self._file = None

    async def read(self, size: int = -1) -> bytes:
        """Read from the temporary file."""
        if self._file is None:
            self._file = open(self.file_path, 'rb')

        if size == -1:
            return self._file.read()
        else:
            return self._file.read(size)

    async def seek(self, position: int) -> None:
        """Seek to a position in the file."""
        if self._file is None:
            self._file = open(self.file_path, 'rb')
        self._file.seek(position)

    async def close(self):
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

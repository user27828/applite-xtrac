"""
JSON file validation.

Validates JSON files using parsing and structure checks.
"""

import json as json_lib
from pathlib import Path
from typing import Optional
import logging

from ..base_validator import TextBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class JSONValidator(TextBasedValidator):
    """JSON file validator using the base validation framework."""

    def __init__(self):
        super().__init__("json")

    def _validate_content(self, content: str, **options) -> bool:
        """
        Validate JSON file content.

        Args:
            content: JSON content to validate
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic text content validation
        self._validate_basic_text_content(content)

        try:
            parsed = json_lib.loads(content)
        except json_lib.JSONDecodeError as e:
            raise ValidationError(
                f"Invalid JSON format: {e}",
                format_type=self.format_name,
                details={"json_error": str(e), "position": e.pos if hasattr(e, 'pos') else None}
            )

        # Additional validation: check if it's not just a primitive
        if not isinstance(parsed, (dict, list)):
            self.logger.warning("JSON file contains only a primitive value (not object or array)")

        # Check for empty structures
        if isinstance(parsed, (dict, list)) and len(parsed) == 0:
            self.logger.info("JSON file contains empty object/array")

        return True

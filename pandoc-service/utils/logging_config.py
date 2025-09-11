"""
Centralized logging configuration for the applite-xtrac application.

This module provides:
- Consistent logging setup across all modules
- Pre-configured loggers with standard formatting
- Environment-based configuration (development/production)
- Utility functions for common logging patterns
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime


# ===== LOGGING CONFIGURATION =====

class LogLevel:
    """Standard log levels with string representations."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    @staticmethod
    def from_string(level_str: str) -> int:
        """Convert string log level to integer."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'WARN': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
            'FATAL': logging.CRITICAL,
        }
        return level_map.get(level_str.upper(), logging.INFO)


class LogConfig:
    """Centralized logging configuration."""

    # Default log format
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Development format (more verbose)
    DEV_FORMAT = '%(asctime)s [%(levelname)8s] %(name)s:%(lineno)d - %(message)s'

    # JSON format for production
    JSON_FORMAT = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'

    @staticmethod
    def get_log_level() -> int:
        """Get log level from environment or default to INFO."""
        level_str = os.getenv('LOG_LEVEL', os.getenv('LOGLEVEL', 'INFO'))
        return LogLevel.from_string(level_str)

    @staticmethod
    def get_log_format() -> str:
        """Get log format based on environment."""
        format_type = os.getenv('LOG_FORMAT', 'standard').lower()

        if format_type == 'dev' or format_type == 'development':
            return LogConfig.DEV_FORMAT
        elif format_type == 'json':
            return LogConfig.JSON_FORMAT
        else:
            return LogConfig.DEFAULT_FORMAT

    @staticmethod
    def should_log_to_file() -> bool:
        """Check if logging to file is enabled."""
        return os.getenv('LOG_TO_FILE', 'false').lower() in ('true', '1', 'yes')

    @staticmethod
    def get_log_file_path() -> Optional[Path]:
        """Get log file path from environment."""
        log_file = os.getenv('LOG_FILE')
        if log_file:
            return Path(log_file)
        return None


# ===== LOGGER FACTORY =====

class LoggerFactory:
    """Factory for creating pre-configured loggers."""

    _loggers: Dict[str, logging.Logger] = {}
    _configured = False

    @classmethod
    def configure_logging(cls, level: Optional[int] = None,
                         format_str: Optional[str] = None,
                         log_to_file: bool = False,
                         log_file: Optional[Union[str, Path]] = None) -> None:
        """Configure the root logger with consistent settings."""

        if cls._configured:
            return  # Already configured

        # Get configuration from environment or parameters
        log_level = level or LogConfig.get_log_level()
        log_format = format_str or LogConfig.get_log_format()
        should_log_to_file = log_to_file or LogConfig.should_log_to_file()
        log_file_path = Path(log_file) if log_file else LogConfig.get_log_file_path()

        # Create formatter
        formatter = logging.Formatter(log_format)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (if enabled)
        if should_log_to_file:
            if log_file_path:
                # Ensure directory exists
                log_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Use rotating file handler for production
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file_path,
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=5
                )
                file_handler.setLevel(log_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)

        cls._configured = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger with the given name."""
        if name not in cls._loggers:
            # Ensure logging is configured
            cls.configure_logging()

            # Create logger
            logger = logging.getLogger(name)
            cls._loggers[name] = logger

        return cls._loggers[name]

    @classmethod
    def get_module_logger(cls) -> logging.Logger:
        """Get a logger for the current module (uses __name__)."""
        import inspect
        frame = inspect.currentframe()
        try:
            # Get the caller's module name
            caller_frame = frame.f_back
            module_name = caller_frame.f_globals.get('__name__', 'unknown')
            return cls.get_logger(module_name)
        finally:
            del frame


# ===== UTILITY FUNCTIONS =====

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Convenience function to get a logger."""
    if name:
        return LoggerFactory.get_logger(name)
    else:
        return LoggerFactory.get_module_logger()


def setup_logging(level: Optional[Union[str, int]] = None,
                 format_type: Optional[str] = None,
                 log_to_file: bool = False,
                 log_file: Optional[Union[str, Path]] = None) -> None:
    """Setup logging with the given configuration."""
    if isinstance(level, str):
        level = LogLevel.from_string(level)

    LoggerFactory.configure_logging(
        level=level,
        format_str=format_type,
        log_to_file=log_to_file,
        log_file=log_file
    )


# ===== BACKWARD COMPATIBILITY =====

# For backward compatibility, provide the old-style logger creation
def create_logger(name: str) -> logging.Logger:
    """Create a logger (backward compatibility function)."""
    return get_logger(name)


# ===== AUTO-CONFIGURATION =====

# Auto-configure logging when this module is imported
LoggerFactory.configure_logging()
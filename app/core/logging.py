# app/core/logging.py
"""
RealtorNet Logging Configuration

Console handler: JSON format in production, text format in development.
File handler: text format with rotation (all environments).

All modules import the module-level `logger` instance - no changes needed
in callers after this update.
"""

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JSONFormatter(logging.Formatter):  # pragma: no cover
    """
    Formats log records as single-line JSON objects.
    Used on the console handler in production so log aggregators
    (Datadog, CloudWatch, Logtail, etc.) can parse fields directly.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "file": f"{record.filename}:{record.lineno}",
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class LoggerConfiguration:
    """Centralized logger configuration for RealtorNet."""

    TEXT_FORMAT = (
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[%(filename)s:%(lineno)d] - %(message)s"
    )
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def get_log_directory() -> Path:
        """Create and return the log directory path."""
        log_dir = Path(os.getcwd()) / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)
        return log_dir

    @classmethod
    def configure_logger(
        cls,
        name: str = "realtornet",
        log_level: int = logging.INFO,
    ) -> logging.Logger:
        """
        Configure logger with console + rotating file handlers.

        Console handler uses JSON format in production, text in development.
        File handler always uses text format for local readability.
        """
        env = os.getenv("ENV", "development").lower()
        is_production = env == "production"

        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.handlers.clear()

        # --- Console handler ---
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        if is_production:  # pragma: no cover
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter(cls.TEXT_FORMAT, datefmt=cls.DATE_FORMAT)
            )

        # --- File handler with rotation ---
        log_dir = cls.get_log_directory()
        log_file = (
            log_dir
            / f"{name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter(cls.TEXT_FORMAT, datefmt=cls.DATE_FORMAT)
        )

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger


# Application-wide logger instance - imported by all modules as:
#   from app.core.logging import logger
logger = LoggerConfiguration.configure_logger()


def log_method_call(logger_instance=logger):  # pragma: no cover
    """
    Decorator to log method entry and exit.
    Useful for tracing and debugging.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger_instance.info(f"Entering method: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger_instance.info(f"Exiting method: {func.__name__}")
                return result
            except Exception as e:
                logger_instance.error(f"Exception in {func.__name__}: {str(e)}")
                raise
        return wrapper
    return decorator


__all__ = ["logger", "log_method_call", "LoggerConfiguration"]

# app/core/logging.py
"""
RealtorNet Logging Configuration
Provides structured logging with rotation and multiple handlers.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path


class LoggerConfiguration:
    """Centralized logger configuration for RealtorNet."""
    
    @staticmethod
    def get_log_directory() -> Path:
        """Create and return the log directory path."""
        log_dir = Path(os.getcwd()) / 'logs'
        log_dir.mkdir(exist_ok=True, parents=True)
        return log_dir

    @classmethod
    def configure_logger(
        cls, 
        name: str = 'realtornet',
        log_level: int = logging.INFO
    ) -> logging.Logger:
        """
        Configure a comprehensive logger with multiple handlers.
        
        Args:
            name: Logger name (default: 'realtornet')
            log_level: Logging level (default: INFO)
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        
        # Clear existing handlers to prevent duplicates
        logger.handlers.clear()
        
        # Formatter with comprehensive information
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        
        # File Handler with Log Rotation
        log_dir = cls.get_log_directory()
        log_file = log_dir / f'{name}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.log'
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # Add handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger


# Application-wide logger instance
logger = LoggerConfiguration.configure_logger()


def log_method_call(logger_instance=logger):
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


__all__ = ['logger', 'log_method_call', 'LoggerConfiguration']
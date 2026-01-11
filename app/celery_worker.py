# app/celery_worker.py
"""
Celery Worker Entry Point for RealtorNet
Handles background task processing for email, notifications, and analytics.

Usage (Development):
    celery -A app.celery_worker worker --loglevel=info --pool=solo --concurrency=1

Usage (Production):
    celery -A app.celery_worker.celery_app worker --loglevel=info -Q email,default
    
Production Configuration:
    - Use prefork pool for better performance
    - Enable autoscaling: --autoscale=10,3
    - Set max tasks per child: --max-tasks-per-child=1000
    - Enable task result backend in Redis
"""

import logging
from app.core.celery_config import celery_app

# Task autodiscovery - import task modules to register them with Celery
# Note: These imports appear unused but are required for Celery to discover tasks
import app.tasks.email_tasks  # noqa: F401


# Configure logging for worker
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    """
    Start the Celery worker when run directly.
    
    For production deployments, use the celery CLI instead of this entry point:
        celery -A app.celery_worker.celery_app worker [options]
    """
    logger.info("Starting Celery worker...")
    celery_app.start()
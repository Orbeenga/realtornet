# app/core/celery_config.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "realtornet",
    broker=settings.REDIS_CELERY_BROKER,   # redis://localhost:6379/1
    backend=settings.REDIS_CELERY_BACKEND  # redis://localhost:6379/2
)

celery_app.conf.task_routes = {
    "app.tasks.email_tasks.*": {"queue": "email"},
}

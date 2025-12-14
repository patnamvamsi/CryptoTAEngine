"""
Celery application for distributed task processing.
"""
from celery import Celery
import logging

from core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'cryptota_engine',
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND
)

# Configuration
celery_app.conf.update(
    task_serializer='pickle',
    accept_content=['pickle', 'json'],
    result_serializer='pickle',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

logger.info("Celery app configured")

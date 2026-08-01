"""
Celery application instance shared by every worker task across
modules (M5 sync polling today; M6 OCR/embeddings, M7 AI jobs, and M9
notification digests plug into the same app as they land).

Run the worker with:
    celery -A app.workers.celery_app worker --loglevel=info

Run the beat scheduler (for the periodic eCourts sync jobs below) with:
    celery -A app.workers.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "nyayaai",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.workers"])

# Plan C.7 point 3: "every synced case refreshed on a schedule: daily
# at 06:00 IST baseline; cases with a hearing today re-checked at
# 14:00 and 19:00 IST (orders/next dates appear in the evening)."
celery_app.conf.beat_schedule = {
    "ecourts-sync-daily-baseline": {
        "task": "app.workers.ecourts_worker.sync_all_cases",
        "schedule": crontab(hour=6, minute=0),
    },
    "ecourts-sync-hearing-today-afternoon": {
        "task": "app.workers.ecourts_worker.sync_hearing_today_cases",
        "schedule": crontab(hour=14, minute=0),
    },
    "ecourts-sync-hearing-today-evening": {
        "task": "app.workers.ecourts_worker.sync_hearing_today_cases",
        "schedule": crontab(hour=19, minute=0),
    },
}

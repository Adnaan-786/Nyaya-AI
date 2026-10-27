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
    # Plan C.10 point 2: digest at user-configured time (scanned every
    # notification_digest_scan_interval_minutes so each user's own
    # digest_time is honored), morning reminder fixed at 07:30 IST,
    # outcome nudge fixed at 20:00 IST.
    "notification-digest-scan": {
        "task": "app.workers.notification_worker.digest_scan",
        "schedule": crontab(minute=f"*/{settings.notification_digest_scan_interval_minutes}"),
    },
    "notification-morning-reminders": {
        "task": "app.workers.notification_worker.morning_reminders",
        "schedule": crontab(hour=7, minute=30),
    },
    "notification-outcome-nudges": {
        "task": "app.workers.notification_worker.outcome_nudges",
        "schedule": crontab(hour=20, minute=0),
    },
    # Plan C.11.3 / C.11.6
    "billing-overdue-and-reminders": {
        "task": "app.workers.billing_worker.overdue_and_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "billing-subscription-downgrades": {
        "task": "app.workers.billing_worker.subscription_downgrades",
        "schedule": crontab(hour=2, minute=0),
    },
}

# `celery_app.autodiscover_tasks(["app.workers"])` above follows
# Django's app-registry convention (looks for an `app.workers.tasks`
# submodule), which doesn't apply to this plain-package layout. Import
# the task modules explicitly instead, so their @celery_app.task
# decorators actually run and register at worker startup.
from app.workers import ai_worker as _ai_worker  # noqa: E402,F401
from app.workers import billing_worker as _billing_worker  # noqa: E402,F401
from app.workers import document_worker as _document_worker  # noqa: E402,F401
from app.workers import ecourts_worker as _ecourts_worker  # noqa: E402,F401
from app.workers import notification_worker as _notification_worker  # noqa: E402,F401

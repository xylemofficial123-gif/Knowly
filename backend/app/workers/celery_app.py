from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "knowledge_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "nightly-decision-extraction": {
        "task": "app.workers.tasks.run_decision_extraction",
        "schedule": 86400,
    },
    "hourly-clickup-sync": {
        "task": "app.workers.tasks.sync_clickup",
        "schedule": 3600,
    },
    "meet-sync-every-30min": {
        "task": "app.workers.tasks.sync_meet_transcripts",
        "schedule": 1800,
    },
    "drive-sync-every-30min": {
        "task": "app.workers.tasks.sync_drive",
        "schedule": 1800,
    },
    "calendar-sync-every-30min": {
        "task": "app.workers.tasks.sync_calendar",
        "schedule": 1800,
    },
}

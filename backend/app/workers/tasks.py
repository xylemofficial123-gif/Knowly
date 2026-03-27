import logging
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def run_decision_extraction(self):
    try:
        logger.info("Starting nightly decision extraction")
        from app.services.decision_extractor import run_extraction_on_all_chunks

        run_extraction_on_all_chunks()
        logger.info("Decision extraction complete")
    except Exception as e:
        logger.error(f"Decision extraction failed: {e}")
        raise self.retry(exc=e, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def sync_clickup(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if settings and "clickup" not in (settings.enabled_sources or []):
            logger.info("ClickUp sync skipped (disabled in settings)")
            return 0

        logger.info("Starting hourly ClickUp sync")
        from app.services.clickup_ingestion import ingest_all_clickup

        count = ingest_all_clickup()
        logger.info(f"ClickUp sync complete: {count} tasks")
        return count
    except Exception as e:
        logger.error(f"ClickUp sync failed: {e}")
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def sync_meet_transcripts(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if settings and "meet" not in (settings.enabled_sources or []):
            logger.info("Meet transcript sync skipped (disabled in settings)")
            return 0

        logger.info("Starting sync for Meet transcripts")
        from app.services.meet_ingestion import ingest_drive_transcripts

        count = ingest_drive_transcripts()
        logger.info(f"Meet sync complete: {count} transcripts")
        return count
    except Exception as e:
        logger.error(f"Meet transcript sync failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def ingest_slack_message(self, message: dict, channel_id: str):
    from app.services.settings_service import is_source_enabled
    if not is_source_enabled("slack"):
        logger.info(f"Slack message ingestion skipped (source disabled)")
        return

    try:
        from app.services.slack_ingestion import ingest_message

        ingest_message(message, channel_id)
    except Exception as e:
        logger.error(f"Slack message ingestion failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def process_relitigation_check(self, message_text: str, slack_user_id: str):
    try:
        from app.services.relitigation_detector import (
            find_similar_decisions,
            send_relitigation_alert,
        )

        matches = find_similar_decisions(message_text)
        if matches:
            send_relitigation_alert(slack_user_id, message_text, matches)
    except Exception as e:
        logger.error(f"Re-litigation check failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def process_decision_extraction_for_message(self, text: str, chunk_id: str, source_url: str, slack_user_id: str):
    try:
        from app.services.decision_extractor import extract_decisions_from_text
        from app.services.ghost_docs import send_ghost_doc_prompt

        decisions = extract_decisions_from_text(text)
        for dec in decisions:
            confidence = dec.get("confidence", 0)
            if confidence >= 0.75 and slack_user_id:
                send_ghost_doc_prompt(slack_user_id, dec, chunk_id, source_url)
    except Exception as e:
        logger.error(f"Decision extraction for message failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def sync_drive(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if settings and "drive" not in (settings.enabled_sources or []):
            logger.info("Drive sync skipped (disabled in settings)")
            return 0

        logger.info("Starting background Drive sync")
        from app.services.drive_ingestion import ingest_all_drive

        # Pass folder IDs from DB if they exist
        folder_ids = settings.google_drive_folder_ids if settings else None
        count = ingest_all_drive(folder_ids=folder_ids)
        logger.info(f"Drive sync complete: {count} files")
        return count
    except Exception as e:
        logger.error(f"Drive sync failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def sync_calendar(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if settings and "calendar" not in (settings.enabled_sources or []):
            logger.info("Calendar sync skipped (disabled in settings)")
            return 0

        logger.info("Starting background calendar sync")
        from app.services.calendar_sync import sync_calendar as run_calendar_sync

        count = run_calendar_sync()
        logger.info(f"Calendar sync complete: {count} events")
        return count
    except Exception as e:
        logger.error(f"Calendar sync failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def sync_slack(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        from app.core.config import settings as app_settings

        gs = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if gs and "slack" not in (gs.enabled_sources or []):
            logger.info("Slack sync skipped (disabled in settings)")
            return 0

        if not app_settings.SLACK_BOT_TOKEN:
            logger.info("Slack sync skipped (no bot token configured)")
            return 0

        logger.info("Starting nightly Slack backfill")
        from app.services.slack_ingestion import backfill_all_channels

        count = backfill_all_channels()
        logger.info(f"Slack sync complete: {count} messages ingested")
        return count
    except Exception as e:
        logger.error(f"Slack sync failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def reingest_clickup_task(self, task_id: str, space_id: str = "", list_id: str = ""):
    from app.services.settings_service import is_source_enabled
    if not is_source_enabled("clickup"):
        logger.info(f"ClickUp task re-ingestion skipped for {task_id} (source disabled)")
        return

    try:
        import requests
        from app.services.clickup_ingestion import ingest_task, _headers, BASE_URL

        resp = requests.get(f"{BASE_URL}/task/{task_id}", headers=_headers())
        resp.raise_for_status()
        task = resp.json()
        ingest_task(task, space_id, list_id)
        logger.info(f"Re-ingested ClickUp task {task_id}")
    except Exception as e:
        logger.error(f"ClickUp task re-ingestion failed: {e}")
        raise self.retry(exc=e, countdown=120)

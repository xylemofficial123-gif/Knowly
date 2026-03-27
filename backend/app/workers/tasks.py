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


@celery_app.task(bind=True, max_retries=2)
def process_guardian_check(
    self,
    text: str,
    user_email: str,
    trigger_source: str,
    source_id: str = "",
    source_url: str = "",
    slack_channel_id: str = "",
    slack_thread_ts: str = "",
    clickup_task_id: str = "",
):
    """
    Run a Guardian check on `text` and deliver an in-context alert if matches found.
    Logs the result to guardian_alerts regardless of outcome.
    """
    from app.agents.guardian import (
        GuardianAgent,
        deliver_slack_alert,
        deliver_clickup_comment,
    )
    from app.core.database import SessionLocal
    from app.models import GuardianAlert

    db = SessionLocal()
    try:
        agent = GuardianAgent()
        result = agent.check(text, user_email, trigger_source, source_id, source_url)

        status = "suppressed"
        if result.has_match:
            # Attempt delivery
            delivered = False
            if trigger_source == "slack" and slack_channel_id and slack_thread_ts:
                delivered = deliver_slack_alert(result, slack_channel_id, slack_thread_ts)
            elif trigger_source == "clickup" and clickup_task_id:
                delivered = deliver_clickup_comment(result, clickup_task_id)
            status = "sent" if delivered else "pending"

        # Persist the alert (or suppression record) for audit
        alert = GuardianAlert(
            trigger_source=trigger_source,
            source_id=source_id or None,
            source_url=source_url or None,
            user_email=user_email,
            text_snippet=text[:500],
            match_count=str(len(result.matches)),
            highest_score=result.highest_score,
            alert_status=status,
            matches_json=[
                {
                    "source": m.source,
                    "title": m.title,
                    "url": m.url,
                    "date": m.date,
                    "preview": m.preview,
                    "score": m.score,
                }
                for m in result.matches
            ],
        )
        db.add(alert)
        db.commit()
        logger.info(
            f"Guardian check complete: source={trigger_source}, "
            f"match={result.has_match}, status={status}, alert_id={alert.id}"
        )
        return {"has_match": result.has_match, "status": status, "alert_id": str(alert.id)}

    except Exception as e:
        db.rollback()
        logger.error(f"Guardian check failed: {e}")
        raise self.retry(exc=e, countdown=60)
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

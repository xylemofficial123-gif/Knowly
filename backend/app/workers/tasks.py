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

        from app.services.meet_ingestion import ingest_drive_transcripts

        user_emails = _get_all_google_user_emails(db)
        if not user_emails:
            logger.info("Meet sync: no Google connections found")
            return 0

        total = 0
        for user_email in user_emails:
            logger.info(f"Starting Meet sync for user={user_email}")
            try:
                count = ingest_drive_transcripts(user_email=user_email)
                logger.info(f"Meet sync complete for user={user_email}: {count} transcripts")
                total += count
            except Exception as e:
                logger.error(f"Meet sync failed for user={user_email}: {e}")
        return total
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


def _get_all_google_user_emails(db) -> list[str]:
    """Return Xylem user emails with a Google connection — filtered to admins
    and team leads only. Members' meetings are not ingested as canonical
    company knowledge (privacy default). Defense in depth: even if a member
    somehow has a connection in the DB (e.g., role was downgraded after they
    connected), their data is now ignored on every sync cycle.
    """
    from app.models import OAuthConnection, User, GroupMembership
    from sqlalchemy import func
    conns = db.query(OAuthConnection).filter(OAuthConnection.id.like("google:%")).all()
    candidate_emails = [c.id[len("google:"):] for c in conns if c.id.startswith("google:")]

    if not candidate_emails:
        # Legacy single "google" connection has no email scope — keep working
        # for older installs but log so the operator knows to migrate.
        legacy = db.query(OAuthConnection).filter(OAuthConnection.id == "google").first()
        if legacy:
            logger.info("Using legacy 'google' connection (pre-multi-user)")
            return [None]
        return []

    # Filter to admins + group_admins (workspace role) + per-group group_admins
    allowed: list[str] = []
    for email in candidate_emails:
        em = email.strip().lower()
        u = db.query(User).filter(func.lower(User.email) == em).first()
        if u and u.role in ("admin", "group_admin"):
            allowed.append(email)
            continue
        is_group_lead = (
            db.query(GroupMembership)
            .filter(
                func.lower(GroupMembership.user_email) == em,
                GroupMembership.role == "group_admin",
            )
            .first()
        )
        if is_group_lead:
            allowed.append(email)
        else:
            logger.info(f"Skipping Google sync for {email} (not admin/group_admin)")

    return allowed


@celery_app.task(bind=True, max_retries=3)
def sync_drive(self):
    db = SessionLocal()
    try:
        from app.models import GlobalSettings
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if settings and "drive" not in (settings.enabled_sources or []):
            logger.info("Drive sync skipped (disabled in settings)")
            return 0

        from app.services.drive_ingestion import ingest_all_drive
        folder_ids = settings.google_drive_folder_ids if settings else None

        user_emails = _get_all_google_user_emails(db)
        if not user_emails:
            logger.info("Drive sync: no Google connections found")
            return 0

        total = 0
        for user_email in user_emails:
            logger.info(f"Starting Drive sync for user={user_email}")
            try:
                count = ingest_all_drive(folder_ids=folder_ids, user_email=user_email)
                logger.info(f"Drive sync complete for user={user_email}: {count} files")
                total += count
            except Exception as e:
                logger.error(f"Drive sync failed for user={user_email}: {e}")
        return total
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

        from app.services.calendar_sync import sync_calendar as run_calendar_sync

        user_emails = _get_all_google_user_emails(db)
        if not user_emails:
            logger.info("Calendar sync: no Google connections found")
            return 0

        total = 0
        for user_email in user_emails:
            logger.info(f"Starting Calendar sync for user={user_email}")
            try:
                count = run_calendar_sync(user_email=user_email)
                logger.info(f"Calendar sync complete for user={user_email}: {count} events")
                total += count
            except Exception as e:
                logger.error(f"Calendar sync failed for user={user_email}: {e}")
        return total
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
    from app.services.drift_detector import check_drift
    from app.core.database import SessionLocal
    from app.models import GuardianAlert

    db = SessionLocal()
    try:
        agent = GuardianAgent()
        result = agent.check(text, user_email, trigger_source, source_id, source_url)

        # Drift detection: check if content contradicts active decisions
        drift_result = check_drift(text, user_email)

        status = "suppressed"
        if result.has_match or drift_result.has_drift:
            # Combine alert text if both triggered
            combined_alert = result.alert_text if result.has_match else ""
            if drift_result.has_drift:
                if combined_alert:
                    combined_alert += "\n\n"
                combined_alert += drift_result.alert_text
            # Patch combined text onto result for delivery
            if combined_alert and not result.has_match:
                result.has_match = True
                result.alert_text = combined_alert
            elif combined_alert:
                result.alert_text = combined_alert

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


@celery_app.task
def probe_llm_env():
    """Run on the Celery worker; reports which keys the worker can see + a
    live LLM call. Used by /api/admin/env-check to diagnose Railway env-var
    scoping mismatches."""
    from app.core.config import settings

    keys_present = {
        # LLM
        "gemini": bool(settings.GEMINI_API_KEY),
        "groq": bool(settings.GROQ_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
        # Slack — needed for ghost docs, re-litigation alerts, Guardian thread replies
        "slack_bot_token": bool(settings.SLACK_BOT_TOKEN),
        # Google — needed for Drive/Meet/Calendar background sync
        "google_client_id": bool(settings.GOOGLE_CLIENT_ID),
        "google_client_secret": bool(settings.GOOGLE_CLIENT_SECRET),
        # Infrastructure
        "database_url": bool(settings.DATABASE_URL),
        "redis_url": bool(settings.REDIS_URL),
        "qdrant_url": bool(settings.QDRANT_URL),
    }
    ping = {"ok": False, "error": None, "response_preview": None}
    try:
        from app.services.llm import generate
        out = generate("Reply with one word: OK")
        ping["ok"] = True
        ping["response_preview"] = (out or "")[:60]
    except Exception as e:
        ping["error"] = f"{type(e).__name__}: {e}"[:300]

    # Live Slack auth check — confirms the bot token actually works
    slack_check = {"ok": False, "error": None, "team": None, "user": None}
    if keys_present["slack_bot_token"]:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=settings.SLACK_BOT_TOKEN)
            r = client.auth_test()
            if r.get("ok"):
                slack_check["ok"] = True
                slack_check["team"] = r.get("team")
                slack_check["user"] = r.get("user")
            else:
                slack_check["error"] = str(r)[:200]
        except Exception as e:
            slack_check["error"] = f"{type(e).__name__}: {e}"[:300]

    return {"keys_present": keys_present, "live_call": ping, "slack_check": slack_check}


@celery_app.task(bind=True, max_retries=2)
def extract_entities_for_document(self, document_id: str):
    """Build the entity graph for a freshly-ingested document.

    Runs in the background after chunk_and_store completes so the user-facing
    ingest call returns immediately. Best-effort — failures are logged but not
    re-raised aggressively (entity graph is enrichment, not core ingestion).
    """
    try:
        from app.services.entity_extractor import process_document_entities
        written = process_document_entities(document_id)
        logger.info(f"Entity graph for {document_id}: {written} mentions written")
        return written
    except Exception as e:
        logger.error(f"Entity extraction failed for doc {document_id}: {e}")
        # One retry for transient LLM/db blips, then give up — don't block the queue
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, max_retries=3)
def reingest_clickup_task(self, task_id: str, space_id: str = "", list_id: str = ""):
    from app.services.settings_service import is_source_enabled
    if not is_source_enabled("clickup"):
        logger.info(f"ClickUp task re-ingestion skipped for {task_id} (source disabled)")
        return

    try:
        import requests
        from app.services.clickup_ingestion import ingest_task, _headers, BASE_URL, get_list_member_emails, get_space_member_emails

        resp = requests.get(f"{BASE_URL}/task/{task_id}", headers=_headers())
        resp.raise_for_status()
        task = resp.json()

        # Resolve ACL from list/space members
        resolved_list_id = list_id or (task.get("list", {}).get("id", "") if isinstance(task.get("list"), dict) else "")
        resolved_space_id = space_id or (task.get("space", {}).get("id", "") if isinstance(task.get("space"), dict) else "")
        acl = []
        if resolved_list_id:
            acl = get_list_member_emails(resolved_list_id)
        if not acl and resolved_space_id:
            acl = get_space_member_emails(resolved_space_id)
        if not acl:
            acl = ["public"]

        ingest_task(task, acl)
        logger.info(f"Re-ingested ClickUp task {task_id}")
    except Exception as e:
        logger.error(f"ClickUp task re-ingestion failed: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, max_retries=2)
def sweep_decision_drift(self, similarity_threshold: float = 0.78, max_pairs_to_check: int = 80):
    """Walk active decisions, flag pairs that are similar AND contradictory.

    Per-write reversal detection (in decision_extractor.check_decision_reversal)
    only catches contradictions when a NEW decision arrives. This sweep catches
    cases where two decisions drifted apart over time, neither explicitly
    reversing the other — e.g. one says "weekly oncall", another says
    "biweekly oncall", extracted weeks apart.

    Two-stage filter to keep LLM cost bounded:
      1. Embed each active decision's text. Pairwise cosine; keep pairs above
         `similarity_threshold` (default 0.78).
      2. For each high-similarity pair, ask the LLM "do these contradict each
         other?". Only "yes" answers become DecisionDriftAlert rows.

    `max_pairs_to_check` caps the LLM cost for any one sweep. Defaults to 80
    high-similarity pairs which is plenty for any active log under ~100
    decisions and burns about 80 LLM calls.
    """
    from app.models import DecisionRecord, DecisionDriftAlert
    from app.services.embeddings import embed_text
    from app.services.llm import generate
    import math
    from sqlalchemy import or_

    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    db = SessionLocal()
    try:
        decisions = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.status == "active")
            .all()
        )
        if len(decisions) < 2:
            logger.info("Drift sweep: <2 active decisions, nothing to compare")
            return {"checked_pairs": 0, "alerts_created": 0}

        logger.info(f"Drift sweep: embedding {len(decisions)} active decisions")
        embeddings: dict[str, list[float]] = {}
        for d in decisions:
            text = (d.decision or "") + ". " + (d.rationale or "")
            try:
                embeddings[str(d.id)] = embed_text(text)
            except Exception as e:
                logger.warning(f"Embedding failed for decision {d.id}: {e}")

        # Pairwise — only retain pairs above threshold and not already alerted.
        pairs = []
        ids = list(embeddings.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = _cosine(embeddings[ids[i]], embeddings[ids[j]])
                if sim >= similarity_threshold:
                    pairs.append((ids[i], ids[j], sim))
        pairs.sort(key=lambda x: x[2], reverse=True)
        pairs = pairs[:max_pairs_to_check]

        logger.info(f"Drift sweep: {len(pairs)} pairs above similarity {similarity_threshold}")

        # Skip pairs we already have an alert for (in either order).
        decision_by_id = {str(d.id): d for d in decisions}
        existing_alerts = db.query(DecisionDriftAlert).all()
        seen_pairs = {
            tuple(sorted([str(a.decision_a_id), str(a.decision_b_id)]))
            for a in existing_alerts
        }

        alerts_created = 0
        for a_id, b_id, sim in pairs:
            key = tuple(sorted([a_id, b_id]))
            if key in seen_pairs:
                continue

            d_a = decision_by_id[a_id]
            d_b = decision_by_id[b_id]
            prompt = (
                "You judge whether two company DECISIONS contradict each other. "
                "Reply 'yes' ONLY if both decisions answer the SAME governance "
                "question with MUTUALLY EXCLUSIVE answers — i.e. acting on one "
                "would violate the other.\n\n"
                "Reply 'no' for everything else, including:\n"
                "- Independent facts about the same event or topic "
                "(e.g. 'Alice attends meeting X' vs 'Bob attends meeting X' — "
                "both can be true at the same time).\n"
                "- Two decisions about different aspects of one project "
                "(e.g. 'use Postgres' vs 'use Redis for caching' — both compatible).\n"
                "- One decision refining the scope of another "
                "(e.g. 'require 2 approvals' vs 'exempt config-only changes' — "
                "the second narrows the first, not contradicts).\n"
                "- Calendar attendance, action item assignment, document "
                "ownership, meeting-minute extracts — these are facts, not "
                "governance decisions, so they cannot contradict.\n\n"
                "Reply 'yes' for clear governance contradictions like:\n"
                "- 'weekly on-call rotation' vs 'bi-weekly on-call rotation' "
                "(answers the question of on-call cadence).\n"
                "- 'annual-only contracts' vs 'add monthly billing tier' "
                "(answers the question of billing structure).\n"
                "- 'use Stripe as payment provider' vs 'use Razorpay as "
                "payment provider' (answers the question of vendor).\n\n"
                f"Decision A: {d_a.decision}\nRationale: {d_a.rationale or 'n/a'}\n\n"
                f"Decision B: {d_b.decision}\nRationale: {d_b.rationale or 'n/a'}\n\n"
                "Reply with strict JSON only, no markdown: "
                '{"contradicts": "yes" | "no", "reason": "<one short sentence>"}'
            )
            try:
                raw = generate(prompt, max_tokens=200)
            except Exception as e:
                logger.warning(f"LLM contradiction check failed for {a_id}/{b_id}: {e}")
                continue

            verdict = "unknown"
            reason = ""
            try:
                import json, re
                m = re.search(r"\{.*\}", raw, re.S)
                if m:
                    parsed = json.loads(m.group(0))
                    verdict = (parsed.get("contradicts") or "unknown").lower().strip()
                    reason = (parsed.get("reason") or "").strip()[:500]
            except Exception:
                pass

            if verdict != "yes":
                continue

            try:
                alert = DecisionDriftAlert(
                    decision_a_id=d_a.id,
                    decision_b_id=d_b.id,
                    similarity=round(float(sim), 4),
                    contradicts="yes",
                    reasoning=reason or None,
                    status="open",
                )
                db.add(alert)
                db.commit()
                alerts_created += 1
                seen_pairs.add(key)
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to insert drift alert for {a_id}/{b_id}: {e}")

        logger.info(
            f"Drift sweep complete: pairs={len(pairs)} alerts_created={alerts_created}"
        )
        return {"checked_pairs": len(pairs), "alerts_created": alerts_created}
    except Exception as e:
        logger.error(f"sweep_decision_drift failed: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()

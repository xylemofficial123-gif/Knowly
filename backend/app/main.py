import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import create_tables, run_migrations
from app.services.embeddings import ensure_collection
from app.api.oracle import router as oracle_router
from app.api.admin import router as admin_router
from app.api.transcripts import router as transcripts_router
from app.api.ingestion import router as ingestion_router
from app.api.users import router as users_router
from app.api.guardian import router as guardian_router
from app.api.oauth import router as oauth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Slack Bolt App (only if token configured) ---
slack_handler = None

if settings.SLACK_BOT_TOKEN:
    from slack_bolt import App as SlackApp
    from slack_bolt.adapter.fastapi import SlackRequestHandler

    slack_app = SlackApp(
        token=settings.SLACK_BOT_TOKEN,
        signing_secret=settings.SLACK_SIGNING_SECRET,
        token_verification_enabled=bool(settings.SLACK_SIGNING_SECRET),
    )

    @slack_app.error
    def global_error_handler(error, body, logger):
        import traceback, os
        tb = traceback.format_exc()
        logger.exception(f"Slack Bolt error: {error}")
        logger.error(f"Request body: {body}")
        # Write to file so we can read it even without terminal access
        with open("/tmp/slack_bolt_error.log", "a") as f:
            f.write(f"\n=== ERROR ===\n{error}\n{tb}\nbody={body}\n")

    @slack_app.event("message")
    def handle_message(event, say):
        from app.services.settings_service import is_source_enabled
        if not is_source_enabled("slack"):
            return

        from app.workers.tasks import (
            ingest_slack_message,
            process_relitigation_check,
            process_decision_extraction_for_message,
        )

        channel_id = event.get("channel", "")
        text = event.get("text", "")
        user = event.get("user", "")

        if event.get("bot_id"):
            return
        if not text:
            return
        if channel_id in settings.no_index_channels:
            return

        ingest_slack_message.delay(event, channel_id)

        source_id = f"slack:{channel_id}:{event.get('ts', '')}"
        source_url = f"https://slack.com/archives/{channel_id}/p{event.get('ts', '').replace('.', '')}"

        if len(text.split()) > 20:
            process_relitigation_check.delay(text, user)

        process_decision_extraction_for_message.delay(text, source_id, source_url, user)

        # Guardian: check if topic was discussed before across all sources
        if len(text.split()) >= 15:
            from app.workers.tasks import process_guardian_check
            # Resolve Slack user ID → email for ACL (best-effort)
            user_email = ""
            try:
                from slack_sdk import WebClient
                wc = WebClient(token=settings.SLACK_BOT_TOKEN)
                info = wc.users_info(user=user)
                user_email = info.get("user", {}).get("profile", {}).get("email", "")
            except Exception:
                pass
            process_guardian_check.delay(
                text,
                user_email,
                "slack",
                source_id,
                source_url,
                slack_channel_id=channel_id,
                slack_thread_ts=event.get("ts", ""),
            )

    @slack_app.command("/timeline")
    def handle_timeline(ack, command, respond):
        ack()
        project_name = command.get("text", "").strip()
        if not project_name:
            respond("Usage: `/timeline [project name]`")
            return

        from app.services.timeline import get_project_timeline

        events = get_project_timeline(project_name, user_email="")

        if not events:
            respond(f"No timeline found for *{project_name}*")
            return

        blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"Timeline: {project_name}"}}]
        for evt in events[:10]:
            date_str = evt.get("date", "Unknown date")
            evt_type = evt.get("type", "event")
            title = evt.get("title", "")
            detail = evt.get("detail", "")[:120]
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{date_str}* — _{evt_type}_\n*{title}*\n{detail}",
                    },
                }
            )
            blocks.append({"type": "divider"})

        respond(blocks=blocks)

    @slack_app.command("/define")
    def handle_define(ack, command, respond):
        ack()
        term = command.get("text", "").strip()
        if not term:
            respond("Usage: `/define [term]`")
            return

        from app.services.acronym_buster import bust_acronym

        result = bust_acronym(term)
        respond(result)

    @slack_app.command("/oracle")
    def handle_oracle(ack, command):
        # Return HTTP 200 to Slack immediately — handler must not block
        ack()

        question = command.get("text", "").strip()
        response_url = command.get("response_url", "")
        user_id = command.get("user_id", "")

        if not question or not response_url:
            return

        # All slow work happens in a background thread.
        # We post directly to response_url (valid 30 min) — never use respond() here
        # because that would block the handler and delay the HTTP 200.
        import threading
        import requests

        def _run():
            import requests as req
            from app.services.oracle import ask_oracle
            from slack_sdk import WebClient

            # Immediately post a "thinking" message so the user sees feedback
            req.post(response_url, json={
                "text": "🔍 Searching the knowledge base…",
                "response_type": "ephemeral",
            }, timeout=5)

            user_email = ""
            try:
                client = WebClient(token=settings.SLACK_BOT_TOKEN)
                user_info = client.users_info(user=user_id)
                user_email = user_info.get("user", {}).get("profile", {}).get("email", "")
            except Exception:
                pass

            if not user_email:
                user_email = "demo@yourcompany.com"

            try:
                result = ask_oracle(question, user_email)
                answer = result.get("answer", "No answer found.")
                citations = result.get("citations", [])

                citation_text = ""
                if citations:
                    citation_text = "\n\n*Sources:*\n"
                    for i, c in enumerate(citations, 1):
                        source = c.get("source", "unknown")
                        display = c.get("display", "")
                        url = c.get("url", "")
                        if url:
                            citation_text += f"{i}. <{url}|{display}> ({source})\n"
                        else:
                            citation_text += f"{i}. {display} ({source})\n"

                req.post(response_url, json={
                    "text": f"{answer}{citation_text}",
                    "response_type": "in_channel",
                    "replace_original": False,
                }, timeout=10)

            except Exception as e:
                logger.error(f"/oracle background error: {e}")
                req.post(response_url, json={
                    "text": "❌ Something went wrong fetching the answer. Please try again.",
                    "response_type": "ephemeral",
                }, timeout=5)

        threading.Thread(target=_run, daemon=True).start()

    @slack_app.command("/history")
    def handle_history(ack, command, respond):
        ack()
        project_name = command.get("text", "").strip()
        if not project_name:
            respond("Usage: `/history <project>`\nExample: `/history mobile-app`")
            return

        from app.services.timeline import get_project_timeline

        events = get_project_timeline(project_name, user_email="")

        if not events:
            respond(f"No history found for *{project_name}*")
            return

        blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"History: {project_name}"}}]
        for evt in events[:10]:
            date_str = evt.get("date", "Unknown date")
            evt_type = evt.get("type", "event")
            title = evt.get("title", "")
            detail = evt.get("detail", "")[:120]
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{date_str}* — _{evt_type}_\n*{title}*\n{detail}",
                    },
                }
            )
            blocks.append({"type": "divider"})

        respond(blocks=blocks)

    @slack_app.command("/decision")
    def handle_decision(ack, command, respond):
        ack()
        text = command.get("text", "").strip()
        if not text:
            respond("Usage: `/decision <decision text>`\nExample: `/decision Use Redis instead of Memcached for caching`")
            return

        import datetime
        from app.core.database import SessionLocal
        from app.models import DecisionRecord

        user_id = command.get("user_id", "")

        db = SessionLocal()
        try:
            record = DecisionRecord(
                decision=text,
                rationale="Manually recorded via /decision command",
                options_considered=[],
                status="active",
                source_chunk_ids=[],
                participants=[user_id],
                decided_at=datetime.datetime.utcnow(),
            )
            db.add(record)
            db.commit()
            respond(f"Decision recorded: *{text}*")
        except Exception as e:
            db.rollback()
            respond(f"Failed to record decision: {e}")
        finally:
            db.close()

    @slack_app.action("ghost_doc_approve")
    def handle_ghost_approve(ack, body, action):
        ack()
        from app.services.ghost_docs import handle_ghost_doc_approve

        user_id = body.get("user", {}).get("id", "")
        handle_ghost_doc_approve(action, user_id)

    @slack_app.action("ghost_doc_reject")
    def handle_ghost_reject(ack, body, action):
        ack()
        from app.services.ghost_docs import handle_ghost_doc_reject

        user_id = body.get("user", {}).get("id", "")
        handle_ghost_doc_reject(action, user_id)

    slack_handler = SlackRequestHandler(slack_app)
    logger.info("Slack bot initialized")
else:
    logger.info("SLACK_BOT_TOKEN not set — Slack bot disabled")


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Knowledge Agent API...")
    create_tables()
    run_migrations()
    ensure_collection()
    yield
    logger.info("Shutting down Knowledge Agent API...")


app = FastAPI(title="Knowledge Agent API", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://xylem-memory.vercel.app",
    *([o.strip() for o in settings.EXTRA_CORS_ORIGINS.split(",") if o.strip()] if hasattr(settings, "EXTRA_CORS_ORIGINS") and settings.EXTRA_CORS_ORIGINS else []),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(oracle_router)
app.include_router(admin_router)
app.include_router(transcripts_router)
app.include_router(ingestion_router)
app.include_router(users_router)
app.include_router(guardian_router)
app.include_router(oauth_router)


# Slack endpoints (only if bot configured)
@app.post("/slack/events")
async def slack_events(request: Request):
    if not slack_handler:
        return JSONResponse(status_code=503, content={"error": "Slack bot not configured"})
    return await slack_handler.handle(request)


@app.post("/slack/commands")
async def slack_commands(request: Request):
    if not slack_handler:
        return JSONResponse(status_code=503, content={"error": "Slack bot not configured"})
    try:
        return await slack_handler.handle(request)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"/slack/commands exception: {e}\n{tb}")
        with open("/tmp/slack_commands_error.log", "a") as f:
            f.write(f"\n=== COMMANDS ERROR ===\n{e}\n{tb}\n")
        return JSONResponse(status_code=200, content={"text": "Error processing command"})


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    if not slack_handler:
        return JSONResponse(status_code=503, content={"error": "Slack bot not configured"})
    return await slack_handler.handle(request)


# ClickUp webhook
@app.post("/api/clickup/webhook")
async def clickup_webhook(request: Request):
    from app.services.settings_service import is_source_enabled
    if not is_source_enabled("clickup"):
        return {"status": "ignored", "reason": "source disabled"}

    from app.workers.tasks import reingest_clickup_task

    try:
        body = await request.json()
        event = body.get("event", "")
        task_id = body.get("task_id", "")

        if event in ("taskCreated", "taskUpdated", "taskCommentPosted") and task_id:
            reingest_clickup_task.delay(task_id)

            # Guardian: check new/updated task description for prior discussions
            task_text = body.get("history_items", [{}])[0].get("after", {}).get("value", "")
            if not task_text:
                task_text = body.get("task", {}).get("name", "")
            if task_text and len(task_text.split()) >= 15:
                from app.workers.tasks import process_guardian_check
                source_id = f"clickup:{task_id}"
                source_url = f"https://app.clickup.com/t/{task_id}"
                process_guardian_check.delay(
                    task_text,
                    "",   # no user email from ClickUp webhook payload by default
                    "clickup",
                    source_id,
                    source_url,
                    clickup_task_id=task_id,
                )
            return {"status": "accepted"}

        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"ClickUp webhook error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
def health():
    return {"status": "ok"}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

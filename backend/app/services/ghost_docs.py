import logging
import json
import datetime

from slack_sdk import WebClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import DecisionRecord, Chunk
from app.services.llm import generate

logger = logging.getLogger(__name__)


def _slack_user_id_to_email(user_id: str) -> str:
    if not user_id or not settings.SLACK_BOT_TOKEN:
        return ""
    try:
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        resp = client.users_info(user=user_id)
        if resp.get("ok"):
            return (resp["user"].get("profile", {}) or {}).get("email", "") or ""
    except Exception as e:
        logger.warning(f"Slack users.info failed for {user_id}: {e}")
    return ""


def slack_email_to_user_id(email: str) -> str:
    """Reverse lookup: email → Slack user ID. Used when firing ghost-doc prompts
    from non-Slack ingestion paths (e.g. Meet transcripts) where we know the
    decision owner's email but need their Slack ID to DM them."""
    if not email or not settings.SLACK_BOT_TOKEN:
        return ""
    try:
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        resp = client.users_lookupByEmail(email=email)
        if resp.get("ok"):
            return resp["user"].get("id", "") or ""
    except Exception as e:
        logger.warning(f"Slack users.lookupByEmail failed for {email}: {e}")
    return ""


def send_ghost_doc_prompt(slack_user_id: str, decision: dict, chunk_id: str, source_url: str):
    client = WebClient(token=settings.SLACK_BOT_TOKEN)

    prompt = f"""Write a brief Slack message asking someone to confirm if this is an official decision that should be recorded.

Decision: {decision['decision']}
Rationale: {decision.get('rationale', 'Not specified')}

Keep it to 2 sentences. Be conversational."""

    try:
        intro_text = generate(prompt)
    except Exception:
        intro_text = "It looks like a decision was made. Should we record it officially?"

    callback_data = json.dumps(
        {
            "chunk_id": chunk_id,
            "decision": decision["decision"],
            "rationale": decision.get("rationale", ""),
            "options": decision.get("options_considered", []),
            # ACL override: when the prompt is fired from a path where chunk.acl
            # isn't reliable yet (e.g. a Meet transcript still being ingested),
            # the caller can pre-compute the ACL and embed it here.
            "acl": decision.get("acl_override") or [],
        }
    )

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"\U0001f4dd *Ghost Documentation Detected*\n\n{intro_text}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Decision:* {decision['decision']}\n*Rationale:* {decision.get('rationale', 'N/A')}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Yes, record it"},
                    "style": "primary",
                    "action_id": "ghost_doc_approve",
                    "value": callback_data,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "No, not a decision"},
                    "style": "danger",
                    "action_id": "ghost_doc_reject",
                    "value": callback_data,
                },
            ],
        },
    ]

    try:
        client.chat_postMessage(channel=slack_user_id, text="Ghost Documentation prompt", blocks=blocks)
        logger.info(f"Sent ghost doc prompt to {slack_user_id}")
    except Exception as e:
        logger.error(f"Failed to send ghost doc prompt: {e}")


def handle_ghost_doc_approve(payload: dict, user_id: str):
    data = json.loads(payload["value"])
    client = WebClient(token=settings.SLACK_BOT_TOKEN)
    db: Session = SessionLocal()

    try:
        chunk = db.query(Chunk).filter(Chunk.id == data["chunk_id"]).first()
        acl = data.get("acl") or (list(chunk.acl) if chunk and chunk.acl else [])

        # Resolve Slack user_id → email so participants stays consistent with the
        # email-based ACL/RBAC system used elsewhere. Fall back to the raw id if
        # lookup fails (e.g. token missing) so we don't silently drop authorship.
        participant = _slack_user_id_to_email(user_id) or user_id

        record = DecisionRecord(
            decision=data["decision"],
            rationale=data.get("rationale", ""),
            options_considered=data.get("options", []),
            status="active",
            source_chunk_ids=[data["chunk_id"]] if data.get("chunk_id") else [],
            participants=[participant],
            acl=acl,
            decided_at=chunk.created_at if chunk else datetime.datetime.utcnow(),
        )
        db.add(record)
        db.commit()

        client.chat_postMessage(
            channel=user_id,
            text=f"Decision recorded: *{data['decision']}*",
        )
        logger.info(f"Ghost doc approved by {user_id}: {data['decision'][:60]}")
    except Exception as e:
        db.rollback()
        logger.error(f"Ghost doc approve failed: {e}")
    finally:
        db.close()


def handle_ghost_doc_reject(payload: dict, user_id: str):
    client = WebClient(token=settings.SLACK_BOT_TOKEN)
    data = json.loads(payload["value"])

    try:
        client.chat_postMessage(
            channel=user_id,
            text=f"Got it — not recording: _{data['decision']}_",
        )
        logger.info(f"Ghost doc rejected by {user_id}: {data['decision'][:60]}")
    except Exception as e:
        logger.error(f"Ghost doc reject failed: {e}")

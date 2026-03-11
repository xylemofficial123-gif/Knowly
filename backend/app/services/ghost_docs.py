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

        record = DecisionRecord(
            decision=data["decision"],
            rationale=data.get("rationale", ""),
            options_considered=data.get("options", []),
            status="active",
            source_chunk_ids=[data["chunk_id"]],
            participants=[user_id],
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

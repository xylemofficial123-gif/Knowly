import logging
import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import DecisionRecord
from app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

THRESHOLD = settings.RELITIGATION_THRESHOLD


def find_similar_decisions(message_text: str) -> list[dict]:
    if len(message_text.split()) <= 20:
        return []

    db: Session = SessionLocal()
    try:
        query_vector = embed_text(message_text)

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=180)
        active_decisions = (
            db.query(DecisionRecord)
            .filter(
                DecisionRecord.status == "active",
                DecisionRecord.decided_at >= cutoff,
            )
            .all()
        )

        if not active_decisions:
            return []

        matches = []
        for decision in active_decisions:
            decision_vector = embed_text(decision.decision)
            dot = sum(a * b for a, b in zip(query_vector, decision_vector))
            norm_q = sum(a * a for a in query_vector) ** 0.5
            norm_d = sum(a * a for a in decision_vector) ** 0.5
            if norm_q == 0 or norm_d == 0:
                continue
            similarity = dot / (norm_q * norm_d)

            if similarity >= THRESHOLD:
                matches.append(
                    {
                        "decision_id": str(decision.id),
                        "decision": decision.decision,
                        "rationale": decision.rationale,
                        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
                        "similarity": round(similarity, 3),
                        "source_chunk_ids": decision.source_chunk_ids,
                    }
                )

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    except Exception as e:
        logger.error(f"Re-litigation detection failed: {e}")
        return []
    finally:
        db.close()


def send_relitigation_alert(slack_user_id: str, message_text: str, matches: list[dict]):
    from slack_sdk import WebClient
    import anthropic

    client = WebClient(token=settings.SLACK_BOT_TOKEN)
    anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    for match in matches[:3]:
        prompt = f"""Write a brief, friendly Slack DM alerting someone that they may be re-discussing a settled decision.

Decision that was already made: {match['decision']}
Rationale: {match['rationale']}
Date decided: {match['decided_at']}

Keep it to 2-3 sentences. Be helpful, not condescending. Include the original decision and rationale."""

        try:
            response = anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            alert_text = response.content[0].text

            client.chat_postMessage(
                channel=slack_user_id,
                text=f"\U0001f504 *Re-litigation Alert*\n\n{alert_text}",
            )
            logger.info(f"Sent re-litigation alert to {slack_user_id}")
        except Exception as e:
            logger.error(f"Failed to send re-litigation alert: {e}")

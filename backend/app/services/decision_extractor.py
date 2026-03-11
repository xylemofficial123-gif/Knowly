import json
import logging
import datetime

import anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Chunk, DecisionRecord
from app.models.review_queue import ReviewQueueItem

logger = logging.getLogger(__name__)

anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

DECISION_EXTRACTION_PROMPT = """You are an expert at identifying decisions in workplace communication.

EXPLICIT DECISIONS: "We decided to...", "Going with X because...", "Final call: Y", "Agreed: Z"
IMPLICIT DECISIONS: proposal + agreement emoji (👍 ✅ +1), "yeah/agreed/sounds good/lgtm" after a suggestion,
                    a debate that ends with one position adopted, someone acting on a suggestion

For each decision found, return JSON:
{
  "decisions": [
    {
      "decision": "one clear sentence of what was decided",
      "rationale": "reasons given or implied",
      "options_considered": ["alternative 1", "alternative 2"],
      "confidence": 0.0-1.0,
      "decision_type": "explicit" or "implicit",
      "trigger_phrase": "exact words or emoji that signal the decision"
    }
  ]
}

If no decisions: {"decisions": []}
Return ONLY valid JSON. No explanation. No markdown fences.

Text: {text}"""


def extract_decisions_from_text(text: str) -> list[dict]:
    if not text or len(text.split()) < 10:
        return []

    prompt = DECISION_EXTRACTION_PROMPT.format(text=text)

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        return result.get("decisions", [])
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Decision extraction failed: {e}")
        return []


def process_decision(decision: dict, chunk: Chunk, db: Session):
    confidence = decision.get("confidence", 0)

    if confidence >= 0.75:
        record = DecisionRecord(
            decision=decision["decision"],
            rationale=decision.get("rationale", ""),
            options_considered=decision.get("options_considered", []),
            status="active",
            source_chunk_ids=[str(chunk.id)],
            participants=[],
            decided_at=chunk.created_at or datetime.datetime.utcnow(),
        )
        db.add(record)
        logger.info(f"Saved DecisionRecord: {decision['decision'][:60]}...")
        return "decision_record"

    elif confidence >= 0.5:
        item = ReviewQueueItem(
            raw_text=chunk.text[:2000],
            proposed_decision=decision["decision"],
            proposed_rationale=decision.get("rationale", ""),
            confidence=confidence,
            decision_type=decision.get("decision_type", "implicit"),
            trigger_phrase=decision.get("trigger_phrase", ""),
            source_chunk_id=str(chunk.id),
            source_url=chunk.source_url or "",
            status="pending",
        )
        db.add(item)
        logger.info(f"Saved ReviewQueueItem: {decision['decision'][:60]}...")
        return "review_queue"

    return "discarded"


def run_extraction_on_all_chunks():
    db: Session = SessionLocal()
    try:
        chunks = db.query(Chunk).all()
        processed = 0
        decisions_found = 0

        for chunk in chunks:
            if not chunk.text or len(chunk.text.split()) < 10:
                continue

            decisions = extract_decisions_from_text(chunk.text)
            for dec in decisions:
                process_decision(dec, chunk, db)
                decisions_found += 1
            processed += 1

            if processed % 50 == 0:
                db.commit()
                logger.info(f"Processed {processed} chunks, found {decisions_found} decisions")

        db.commit()
        logger.info(
            f"Decision extraction complete: {processed} chunks processed, {decisions_found} decisions found"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Decision extraction failed: {e}")
        raise
    finally:
        db.close()

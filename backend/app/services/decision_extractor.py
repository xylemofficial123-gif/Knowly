import json
import logging
import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Chunk, DecisionRecord
from app.models.review_queue import ReviewQueueItem
from app.services.llm import generate
from app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

DECISION_EXTRACTION_PROMPT = """You are an expert at identifying decisions in workplace communication.

EXPLICIT DECISIONS: "We decided to...", "Going with X because...", "Final call: Y", "Agreed: Z"
IMPLICIT DECISIONS: proposal + agreement emoji, "yeah/agreed/sounds good/lgtm" after a suggestion,
                    a debate that ends with one position adopted, someone acting on a suggestion

For each decision found, return JSON:
{{
  "decisions": [
    {{
      "decision": "one clear sentence of what was decided",
      "rationale": "reasons given or implied",
      "options_considered": ["alternative 1", "alternative 2"],
      "confidence": 0.0-1.0,
      "decision_type": "explicit" or "implicit",
      "trigger_phrase": "exact words or emoji that signal the decision"
    }}
  ]
}}

If no decisions: {{"decisions": []}}
Return ONLY valid JSON. No explanation. No markdown fences.

Text: {text}"""


def extract_decisions_from_text(text: str) -> list[dict]:
    if not text or len(text.split()) < 10:
        return []

    prompt = DECISION_EXTRACTION_PROMPT.format(text=text)

    try:
        raw = generate(prompt).strip()

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


def check_decision_reversal(new_decision_text: str, db: Session) -> Optional[DecisionRecord]:
    """Check if a new decision contradicts an existing active decision.

    Uses semantic similarity (≥0.80) + LLM confirmation to detect reversals.
    Returns the superseded decision if found, None otherwise.
    """
    query_vector = embed_text(new_decision_text)

    active_decisions = (
        db.query(DecisionRecord)
        .filter(DecisionRecord.status == "active")
        .all()
    )

    if not active_decisions:
        return None

    # Find semantically similar active decisions
    candidates = []
    for d in active_decisions:
        d_vec = embed_text(d.decision)
        dot = sum(a * b for a, b in zip(query_vector, d_vec))
        norm_q = sum(a * a for a in query_vector) ** 0.5
        norm_d = sum(a * a for a in d_vec) ** 0.5
        if norm_q > 0 and norm_d > 0:
            sim = dot / (norm_q * norm_d)
            if sim >= 0.80:
                candidates.append((d, sim))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    top_match, top_sim = candidates[0]

    # LLM confirmation: is this actually a reversal or just a related decision?
    confirm_prompt = (
        f"Does the NEW decision contradict or reverse the OLD decision? "
        f"Answer ONLY 'yes' or 'no'.\n\n"
        f"OLD decision: {top_match.decision}\n"
        f"NEW decision: {new_decision_text}\n\n"
        f"Answer:"
    )
    try:
        answer = generate(confirm_prompt, max_tokens=8).strip().lower()
        if "yes" in answer:
            logger.info(
                f"Reversal detected (sim={top_sim:.3f}): "
                f"'{new_decision_text[:60]}' reverses '{top_match.decision[:60]}'"
            )
            return top_match
    except Exception as e:
        logger.warning(f"Reversal LLM check failed: {e}")

    return None


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
        db.flush()  # Get record.id before reversal check

        # Check if this new decision reverses an existing one
        reversed_decision = check_decision_reversal(decision["decision"], db)
        if reversed_decision:
            reversed_decision.status = "superseded"
            reversed_decision.superseded_by = record.id
            reversed_decision.superseded_at = datetime.datetime.utcnow()
            reversed_decision.reversal_reason = (
                f"Superseded by new decision: {decision['decision'][:200]}"
            )
            logger.info(
                f"Marked decision {reversed_decision.id} as superseded by {record.id}"
            )

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

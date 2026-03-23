"""
Meet Discrepancy Detection

When a new meeting is ingested, this service compares the new meeting's
decisions against all existing active DecisionRecords to detect:

  1. CONTRADICTIONS  – the new meeting reverses/contradicts a past decision
  2. UPDATES         – the new meeting refines or adds to a past decision
  3. RECONFIRMATIONS – the same decision is made again (healthy alignment)

The flow:
  new meeting decisions
    → embed each decision text
    → vector similarity search against active DecisionRecords
    → for pairs with similarity ≥ threshold: ask LLM to classify
    → return structured discrepancy report

This report is appended to the meeting's enriched text so agents can
surface it in answers.
"""

import logging
from dataclasses import dataclass, field

from app.services.llm import generate

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70  # lower than re-litigation threshold (0.82) to catch related decisions
DISCREPANCY_PROMPT = """You are an expert analyst comparing two organizational decisions.

Past Decision: {past_decision}
Context: {past_context}

New Decision (from meeting "{meeting_title}"): {new_decision}

Classify the relationship:
- CONTRADICTION: The new decision directly conflicts with or reverses the past decision
- UPDATE: The new decision refines, extends, or partially changes the past decision
- RECONFIRMATION: The new decision reaffirms the past decision (same conclusion)
- UNRELATED: The decisions are about different things (the similarity was coincidental)

Return ONLY a JSON object like:
{{
  "relationship": "CONTRADICTION",
  "explanation": "one sentence explaining why",
  "severity": "high|medium|low"
}}

No markdown. No explanation outside JSON."""


@dataclass
class Discrepancy:
    relationship: str        # CONTRADICTION | UPDATE | RECONFIRMATION | UNRELATED
    new_decision: str
    past_decision: str
    past_decision_id: str
    explanation: str
    severity: str            # high | medium | low


@dataclass
class DiscrepancyReport:
    meeting_title: str
    contradictions: list[Discrepancy] = field(default_factory=list)
    updates: list[Discrepancy] = field(default_factory=list)
    reconfirmations: list[Discrepancy] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.contradictions or self.updates)

    def to_text(self) -> str:
        if not self.has_issues and not self.reconfirmations:
            return ""

        parts = ["=== DECISION DISCREPANCY ANALYSIS ==="]

        if self.contradictions:
            parts.append(f"\n[!] CONTRADICTIONS DETECTED ({len(self.contradictions)}):")
            for d in self.contradictions:
                parts.append(f"  • NEW: {d.new_decision}")
                parts.append(f"    CONTRADICTS: {d.past_decision}")
                parts.append(f"    Reason: {d.explanation} [Severity: {d.severity}]")

        if self.updates:
            parts.append(f"\n[~] DECISION UPDATES ({len(self.updates)}):")
            for d in self.updates:
                parts.append(f"  • NEW: {d.new_decision}")
                parts.append(f"    UPDATES: {d.past_decision}")
                parts.append(f"    Reason: {d.explanation}")

        if self.reconfirmations:
            parts.append(f"\n[✓] RECONFIRMATIONS ({len(self.reconfirmations)}):")
            for d in self.reconfirmations:
                parts.append(f"  • {d.new_decision}")

        return "\n".join(parts)


def _embed_text(text: str) -> list[float]:
    from app.services.embeddings import _get_model
    model = _get_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _classify_relationship(
    new_decision: str,
    past_decision: str,
    past_context: str,
    meeting_title: str,
) -> dict:
    """Ask the LLM to classify the relationship between two decisions."""
    import json

    prompt = DISCREPANCY_PROMPT.format(
        past_decision=past_decision,
        past_context=past_context or "No additional context",
        new_decision=new_decision,
        meeting_title=meeting_title,
    )
    try:
        raw = generate(prompt).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Failed to classify decision relationship: {e}")
        return {"relationship": "UNRELATED", "explanation": "Classification failed", "severity": "low"}


def detect_discrepancies(
    new_decisions: list[dict],
    meeting_title: str,
) -> DiscrepancyReport:
    """
    Compare new_decisions (from a just-ingested meeting) against existing
    active DecisionRecords and return a DiscrepancyReport.

    new_decisions: list of {"decision": str, "who": str, "context": str}
    """
    report = DiscrepancyReport(meeting_title=meeting_title)

    if not new_decisions:
        return report

    # Load existing active decisions
    try:
        from app.core.database import SessionLocal
        from app.models import DecisionRecord

        db = SessionLocal()
        try:
            active_decisions = (
                db.query(DecisionRecord)
                .filter(DecisionRecord.status == "active")
                .all()
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to load active decisions for discrepancy check: {e}")
        return report

    if not active_decisions:
        logger.info("No active decisions to compare against — skipping discrepancy check")
        return report

    logger.info(
        f"Checking {len(new_decisions)} new decisions against {len(active_decisions)} existing decisions"
    )

    # Pre-embed all existing decisions (batch for efficiency)
    try:
        past_embeddings = []
        for dec in active_decisions:
            emb = _embed_text(dec.decision)
            past_embeddings.append(emb)
    except Exception as e:
        logger.error(f"Failed to embed past decisions: {e}")
        return report

    # Compare each new decision against all past ones
    for new_dec in new_decisions:
        new_text = new_dec.get("decision", "")
        if not new_text:
            continue

        try:
            new_emb = _embed_text(new_text)
        except Exception as e:
            logger.warning(f"Could not embed new decision: {e}")
            continue

        for past_dec, past_emb in zip(active_decisions, past_embeddings):
            sim = _cosine_similarity(new_emb, past_emb)
            if sim < SIMILARITY_THRESHOLD:
                continue

            # High enough similarity — ask LLM to classify
            classification = _classify_relationship(
                new_decision=new_text,
                past_decision=past_dec.decision,
                past_context=past_dec.rationale or "",
                meeting_title=meeting_title,
            )

            relationship = classification.get("relationship", "UNRELATED")
            if relationship == "UNRELATED":
                continue

            discrepancy = Discrepancy(
                relationship=relationship,
                new_decision=new_text,
                past_decision=past_dec.decision,
                past_decision_id=str(past_dec.id),
                explanation=classification.get("explanation", ""),
                severity=classification.get("severity", "medium"),
            )

            if relationship == "CONTRADICTION":
                report.contradictions.append(discrepancy)
                logger.warning(
                    f"CONTRADICTION detected: new='{new_text[:80]}' vs past='{past_dec.decision[:80]}'"
                )
            elif relationship == "UPDATE":
                report.updates.append(discrepancy)
                logger.info(f"UPDATE detected: '{new_text[:80]}'")
            elif relationship == "RECONFIRMATION":
                report.reconfirmations.append(discrepancy)

    return report

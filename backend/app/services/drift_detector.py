"""
Drift Detector — flags when new content contradicts active recorded decisions.

Called alongside the Guardian Agent check.  When a Slack message, ClickUp task,
or Drive doc is ingested, we embed the text and compare against all active
DecisionRecords.  If high semantic similarity is found, an LLM classifies the
relationship as ALIGNED, CONTRADICTS, or UNRELATED.  Contradictions are surfaced
as drift alerts.
"""
import logging
from dataclasses import dataclass, field

from app.core.database import SessionLocal
from app.models import DecisionRecord
from app.services.embeddings import embed_text
from app.services.llm import generate

logger = logging.getLogger(__name__)

# Minimum cosine similarity between new text and a decision to warrant LLM check
DRIFT_SIMILARITY_THRESHOLD = 0.72

# Maximum decisions to check via LLM per trigger
MAX_LLM_CHECKS = 5


@dataclass
class DriftMatch:
    decision_id: str
    decision_text: str
    rationale: str
    decided_at: str
    similarity: float
    classification: str  # CONTRADICTS | ALIGNED | UNRELATED


@dataclass
class DriftResult:
    has_drift: bool = False
    alert_text: str = ""
    matches: list[DriftMatch] = field(default_factory=list)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_CLASSIFY_PROMPT = """You are a decision consistency checker. A team member just wrote something new.
Compare it against a previously recorded company decision and classify the relationship.

New content (first 500 chars):
{content}

Recorded decision:
- Decision: {decision}
- Rationale: {rationale}
- Decided on: {decided_at}

Classify as exactly one of:
- CONTRADICTS: The new content directly contradicts or goes against the recorded decision.
- ALIGNED: The new content is consistent with or supports the recorded decision.
- UNRELATED: The new content is on a similar topic but does not conflict.

Return ONLY one word: CONTRADICTS, ALIGNED, or UNRELATED."""


def check_drift(text: str, user_email: str = "") -> DriftResult:
    """Check if `text` contradicts any active decision.

    Returns DriftResult with has_drift=True and formatted alert if contradictions found.
    """
    if len(text.split()) < 10:
        return DriftResult()

    text_vec = embed_text(text[:4000])

    db = SessionLocal()
    try:
        decisions = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.status == "active")
            .all()
        )
        if not decisions:
            return DriftResult()

        # Score all decisions by similarity
        candidates = []
        for d in decisions:
            d_vec = embed_text(d.decision)
            sim = _cosine_similarity(text_vec, d_vec)
            if sim >= DRIFT_SIMILARITY_THRESHOLD:
                candidates.append((d, sim))

        if not candidates:
            return DriftResult()

        # Sort by similarity, check top N via LLM
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[:MAX_LLM_CHECKS]

        contradictions: list[DriftMatch] = []

        for d, sim in candidates:
            decided_at = d.decided_at.strftime("%d/%m/%Y") if d.decided_at else "unknown"
            prompt = _CLASSIFY_PROMPT.format(
                content=text[:500],
                decision=d.decision,
                rationale=d.rationale or "N/A",
                decided_at=decided_at,
            )
            try:
                classification = generate(prompt, max_tokens=20).strip().upper()
                # Normalize
                if "CONTRADICT" in classification:
                    classification = "CONTRADICTS"
                elif "ALIGNED" in classification:
                    classification = "ALIGNED"
                else:
                    classification = "UNRELATED"
            except Exception as e:
                logger.warning(f"Drift LLM classification failed: {e}")
                classification = "UNRELATED"

            if classification == "CONTRADICTS":
                contradictions.append(DriftMatch(
                    decision_id=str(d.id),
                    decision_text=d.decision,
                    rationale=d.rationale or "",
                    decided_at=decided_at,
                    similarity=round(sim, 3),
                    classification=classification,
                ))

        if not contradictions:
            return DriftResult()

        # Build alert text
        alert_lines = [
            "⚠️ *Drift detected — this may contradict a recorded decision:*",
        ]
        for m in contradictions:
            alert_lines.append(
                f"• *Decision ({m.decided_at}):* {m.decision_text[:200]}"
            )
            if m.rationale:
                alert_lines.append(f"  _Rationale: {m.rationale[:150]}_")
        alert_lines.append(
            "Consider reviewing whether the recorded decision should be updated or if this is an oversight."
        )

        return DriftResult(
            has_drift=True,
            alert_text="\n".join(alert_lines),
            matches=contradictions,
        )

    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        return DriftResult()
    finally:
        db.close()

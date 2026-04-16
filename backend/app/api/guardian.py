"""
Guardian Agent API

POST /api/guardian/check   — manually trigger a check (testing / Drive webhooks)
GET  /api/guardian/alerts  — paginated alert log for the admin panel
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.core.timezone import format_ist_date
from app.models import GuardianAlert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/guardian", tags=["guardian"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class GuardianCheckRequest(BaseModel):
    text: str
    user_email: str = ""
    trigger_source: str = "manual"   # slack | clickup | drive | manual
    source_id: str = ""
    source_url: str = ""


class GuardianCheckResponse(BaseModel):
    has_match: bool
    alert_text: str = ""
    matches: list[dict] = []
    highest_score: float = 0.0
    alert_id: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/check", response_model=GuardianCheckResponse)
def check_guardian(req: GuardianCheckRequest):
    """
    Synchronously run a Guardian check and return the result.
    Useful for manual testing and Drive webhook integrations.
    Also persists a GuardianAlert record.
    """
    from app.agents.guardian import GuardianAgent

    agent = GuardianAgent()
    result = agent.check(
        text=req.text,
        user_email=req.user_email,
        trigger_source=req.trigger_source,
        source_id=req.source_id,
        source_url=req.source_url,
    )

    alert_id = None
    db = SessionLocal()
    try:
        alert = GuardianAlert(
            trigger_source=req.trigger_source,
            source_id=req.source_id or None,
            source_url=req.source_url or None,
            user_email=req.user_email,
            text_snippet=req.text[:500],
            match_count=str(len(result.matches)),
            highest_score=result.highest_score,
            alert_status="sent" if result.has_match else "suppressed",
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
        alert_id = str(alert.id)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist GuardianAlert: {e}")
    finally:
        db.close()

    return GuardianCheckResponse(
        has_match=result.has_match,
        alert_text=result.alert_text,
        matches=[
            {
                "source": m.source,
                "title": m.title,
                "url": m.url,
                "date": m.date,
                "preview": m.preview,
                "score": m.score,
                "chunk_type": m.chunk_type,
            }
            for m in result.matches
        ],
        highest_score=result.highest_score,
        alert_id=alert_id,
    )


class DriftCheckRequest(BaseModel):
    text: str
    user_email: str = ""


@router.post("/drift-check")
def check_drift_endpoint(req: DriftCheckRequest):
    """Manually check if text contradicts any active decision."""
    from app.services.drift_detector import check_drift

    result = check_drift(req.text, req.user_email)
    return {
        "has_drift": result.has_drift,
        "alert_text": result.alert_text,
        "matches": [
            {
                "decision_id": m.decision_id,
                "decision_text": m.decision_text,
                "rationale": m.rationale,
                "decided_at": m.decided_at,
                "similarity": m.similarity,
                "classification": m.classification,
            }
            for m in result.matches
        ],
    }


@router.get("/alerts")
def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    trigger_source: Optional[str] = None,
    has_match: Optional[bool] = None,
):
    """
    Return paginated Guardian alert log for the admin panel.
    Filters: trigger_source (slack/clickup/drive/manual), has_match (true = matched).
    """
    db = SessionLocal()
    try:
        q = db.query(GuardianAlert).order_by(GuardianAlert.created_at.desc())

        if trigger_source:
            q = q.filter(GuardianAlert.trigger_source == trigger_source)
        if has_match is True:
            q = q.filter(GuardianAlert.alert_status != "suppressed")
        elif has_match is False:
            q = q.filter(GuardianAlert.alert_status == "suppressed")

        total = q.count()
        alerts = q.offset(offset).limit(limit).all()

        rows = []
        for a in alerts:
            rows.append({
                "id": str(a.id),
                "trigger_source": a.trigger_source,
                "source_id": a.source_id,
                "source_url": a.source_url,
                "user_email": a.user_email,
                "text_snippet": a.text_snippet,
                "match_count": a.match_count,
                "highest_score": a.highest_score,
                "alert_status": a.alert_status,
                "matches": a.matches_json or [],
                "created_at": format_ist_date(a.created_at) if a.created_at else "",
            })

        return {"total": total, "alerts": rows}
    finally:
        db.close()

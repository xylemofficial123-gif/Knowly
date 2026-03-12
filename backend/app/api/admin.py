import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, case
import logging

from app.core.database import SessionLocal
from app.models import AuditLog, DecisionRecord, AnswerFeedback
from app.models.review_queue import ReviewQueueItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-log")
def get_audit_log(limit: int = 50, offset: int = 0):
    db = SessionLocal()
    try:
        logs = (
            db.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "entries": [
                {
                    "id": str(log.id),
                    "user_email": log.user_email or "",
                    "query": log.query or "",
                    "result_count": log.result_count or "0",
                    "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                }
                for log in logs
            ],
            "total": db.query(AuditLog).count(),
        }
    finally:
        db.close()


@router.get("/review-queue")
def get_review_queue(status: str = "pending", limit: int = 50):
    db = SessionLocal()
    try:
        items = (
            db.query(ReviewQueueItem)
            .filter(ReviewQueueItem.status == status)
            .order_by(ReviewQueueItem.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": str(item.id),
                    "proposed_decision": item.proposed_decision or "",
                    "proposed_rationale": item.proposed_rationale or "",
                    "confidence": item.confidence or 0.0,
                    "decision_type": item.decision_type or "",
                    "trigger_phrase": item.trigger_phrase or "",
                    "source_url": item.source_url or "",
                    "status": item.status or "pending",
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                }
                for item in items
            ]
        }
    finally:
        db.close()


@router.post("/review-queue/{item_id}/approve")
def approve_review(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found")

        if item.status != "pending":
            raise HTTPException(status_code=400, detail=f"Item already {item.status}")

        record = DecisionRecord(
            decision=item.proposed_decision,
            rationale=item.proposed_rationale,
            options_considered=[],
            status="active",
            source_chunk_ids=[item.source_chunk_id] if item.source_chunk_id else [],
            participants=[],
            decided_at=item.created_at or datetime.datetime.utcnow(),
        )
        db.add(record)
        item.status = "approved"
        db.commit()

        return {"status": "approved", "decision_id": str(record.id)}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Approve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/review-queue/{item_id}/reject")
def reject_review(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found")

        if item.status != "pending":
            raise HTTPException(status_code=400, detail=f"Item already {item.status}")

        item.status = "rejected"
        db.commit()

        return {"status": "rejected"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Reject failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# --- Feedback ---

class FeedbackRequest(BaseModel):
    audit_log_id: str = ""
    session_id: str = ""
    user_email: str = ""
    query: str = ""
    rating: str  # "helpful" or "not_helpful"
    comment: str = ""
    agent: str = ""
    query_type: str = ""
    confidence: float = 0.0


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    db = SessionLocal()
    try:
        feedback = AnswerFeedback(
            audit_log_id=req.audit_log_id if req.audit_log_id else None,
            session_id=req.session_id,
            user_email=req.user_email,
            query=req.query,
            rating=req.rating,
            comment=req.comment,
            agent=req.agent,
            query_type=req.query_type,
            confidence=req.confidence,
        )
        db.add(feedback)
        db.commit()
        return {"status": "ok", "id": str(feedback.id)}
    except Exception as e:
        db.rollback()
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/feedback")
def get_feedback(limit: int = 50):
    db = SessionLocal()
    try:
        items = (
            db.query(AnswerFeedback)
            .order_by(AnswerFeedback.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": str(f.id),
                    "query": f.query or "",
                    "rating": f.rating or "",
                    "comment": f.comment or "",
                    "agent": f.agent or "",
                    "query_type": f.query_type or "",
                    "confidence": f.confidence or 0.0,
                    "user_email": f.user_email or "",
                    "created_at": f.created_at.isoformat() if f.created_at else "",
                }
                for f in items
            ],
            "total": db.query(AnswerFeedback).count(),
        }
    finally:
        db.close()


# --- Metrics ---

@router.get("/metrics")
def get_metrics():
    db = SessionLocal()
    try:
        total_queries = db.query(AuditLog).count()

        week_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        queries_this_week = db.query(AuditLog).filter(AuditLog.timestamp >= week_ago).count()

        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        queries_today = db.query(AuditLog).filter(AuditLog.timestamp >= today_start).count()

        avg_confidence = db.query(func.avg(AuditLog.confidence)).scalar() or 0.0
        avg_response_time = db.query(func.avg(AuditLog.response_time_ms)).scalar() or 0.0

        # Agent usage breakdown
        agent_counts = (
            db.query(AuditLog.agent, func.count(AuditLog.id))
            .filter(AuditLog.agent.isnot(None))
            .group_by(AuditLog.agent)
            .all()
        )
        agent_usage = {agent: count for agent, count in agent_counts}

        # Query type breakdown
        type_counts = (
            db.query(AuditLog.query_type, func.count(AuditLog.id))
            .filter(AuditLog.query_type.isnot(None))
            .group_by(AuditLog.query_type)
            .all()
        )
        query_type_usage = {qtype: count for qtype, count in type_counts}

        # Feedback stats
        total_feedback = db.query(AnswerFeedback).count()
        helpful_count = db.query(AnswerFeedback).filter(AnswerFeedback.rating == "helpful").count()
        not_helpful_count = db.query(AnswerFeedback).filter(AnswerFeedback.rating == "not_helpful").count()
        helpfulness_rate = (helpful_count / total_feedback * 100) if total_feedback > 0 else 0.0

        unique_users = db.query(func.count(func.distinct(AuditLog.user_email))).scalar() or 0

        # Daily query counts (last 7 days)
        daily_counts = (
            db.query(
                func.date(AuditLog.timestamp).label("date"),
                func.count(AuditLog.id).label("count"),
            )
            .filter(AuditLog.timestamp >= week_ago)
            .group_by(func.date(AuditLog.timestamp))
            .order_by(func.date(AuditLog.timestamp))
            .all()
        )
        daily_usage = [{"date": str(d.date), "count": d.count} for d in daily_counts]

        return {
            "overview": {
                "total_queries": total_queries,
                "queries_today": queries_today,
                "queries_this_week": queries_this_week,
                "unique_users": unique_users,
                "avg_confidence": round(avg_confidence, 2),
                "avg_response_time_ms": round(avg_response_time, 0),
            },
            "feedback": {
                "total": total_feedback,
                "helpful": helpful_count,
                "not_helpful": not_helpful_count,
                "helpfulness_rate": round(helpfulness_rate, 1),
            },
            "agent_usage": agent_usage,
            "query_type_usage": query_type_usage,
            "daily_usage": daily_usage,
        }
    finally:
        db.close()

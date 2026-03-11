import datetime
from fastapi import APIRouter, HTTPException
import logging

from app.core.database import SessionLocal
from app.models import AuditLog, DecisionRecord
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

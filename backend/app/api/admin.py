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
        db.flush()

        # Check if this reverses an existing decision
        from app.services.decision_extractor import check_decision_reversal
        reversed_decision = check_decision_reversal(item.proposed_decision, db)
        reversal_info = None
        if reversed_decision:
            reversed_decision.status = "superseded"
            reversed_decision.superseded_by = record.id
            reversed_decision.superseded_at = datetime.datetime.utcnow()
            reversed_decision.reversal_reason = (
                f"Superseded by new decision: {item.proposed_decision[:200]}"
            )
            reversal_info = {
                "reversed_decision_id": str(reversed_decision.id),
                "reversed_decision": reversed_decision.decision,
            }

        item.status = "approved"
        db.commit()

        result = {"status": "approved", "decision_id": str(record.id)}
        if reversal_info:
            result["reversal"] = reversal_info
        return result
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

        # Update chunk feedback scores in Qdrant
        if req.audit_log_id:
            try:
                audit_log = db.query(AuditLog).filter(
                    AuditLog.id == req.audit_log_id
                ).first()
                if audit_log and audit_log.chunks_returned:
                    import json
                    chunk_ids = json.loads(audit_log.chunks_returned)
                    if chunk_ids:
                        from app.services.embeddings import update_chunk_feedback
                        update_chunk_feedback(chunk_ids, req.rating)
                        logger.info(f"Updated feedback scores for {len(chunk_ids)} chunks ({req.rating})")
            except Exception as e:
                logger.warning(f"Chunk feedback update failed (non-critical): {e}")

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


# --- Decisions ---

@router.get("/decisions")
def get_decisions(status: str = "all", limit: int = 50):
    """List decisions with reversal chain info."""
    db = SessionLocal()
    try:
        query = db.query(DecisionRecord).order_by(DecisionRecord.decided_at.desc())
        if status != "all":
            query = query.filter(DecisionRecord.status == status)
        decisions = query.limit(limit).all()

        return {
            "items": [
                {
                    "id": str(d.id),
                    "decision": d.decision or "",
                    "rationale": d.rationale or "",
                    "status": d.status or "active",
                    "decided_at": d.decided_at.isoformat() if d.decided_at else "",
                    "created_at": d.created_at.isoformat() if d.created_at else "",
                    "superseded_by": str(d.superseded_by) if d.superseded_by else None,
                    "superseded_at": d.superseded_at.isoformat() if d.superseded_at else None,
                    "reversal_reason": d.reversal_reason or None,
                }
                for d in decisions
            ],
            "total_active": db.query(DecisionRecord).filter(DecisionRecord.status == "active").count(),
            "total_superseded": db.query(DecisionRecord).filter(DecisionRecord.status == "superseded").count(),
        }
    finally:
        db.close()


@router.get("/decisions/{decision_id}/history")
def get_decision_history(decision_id: str):
    """Get full reversal chain for a decision (both predecessors and successors)."""
    db = SessionLocal()
    try:
        decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        chain = []

        # Walk backwards — find what this decision superseded
        current = decision
        predecessors = []
        visited = {str(current.id)}
        while True:
            # Find the decision that this one superseded
            predecessor = (
                db.query(DecisionRecord)
                .filter(DecisionRecord.superseded_by == current.id)
                .first()
            )
            if not predecessor or str(predecessor.id) in visited:
                break
            visited.add(str(predecessor.id))
            predecessors.append(predecessor)
            current = predecessor

        # Walk forwards — find what superseded this decision
        current = decision
        successors = []
        while current.superseded_by and str(current.superseded_by) not in visited:
            visited.add(str(current.superseded_by))
            successor = db.query(DecisionRecord).filter(
                DecisionRecord.id == current.superseded_by
            ).first()
            if not successor:
                break
            successors.append(successor)
            current = successor

        # Build timeline: oldest first
        chain = list(reversed(predecessors)) + [decision] + successors

        return {
            "decision_id": decision_id,
            "chain": [
                {
                    "id": str(d.id),
                    "decision": d.decision or "",
                    "rationale": d.rationale or "",
                    "status": d.status or "",
                    "decided_at": d.decided_at.isoformat() if d.decided_at else "",
                    "superseded_at": d.superseded_at.isoformat() if d.superseded_at else None,
                    "reversal_reason": d.reversal_reason or None,
                    "is_current": d.status == "active",
                }
                for d in chain
            ],
        }
    finally:
        db.close()


class ReversalRequest(BaseModel):
    new_decision: str
    rationale: str
    reason: str = ""


@router.post("/decisions/{decision_id}/reverse")
def reverse_decision(decision_id: str, req: ReversalRequest):
    """Manually reverse a decision — creates a new active decision and marks the old one as superseded."""
    db = SessionLocal()
    try:
        old_decision = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not old_decision:
            raise HTTPException(status_code=404, detail="Decision not found")
        if old_decision.status != "active":
            raise HTTPException(status_code=400, detail=f"Decision is already {old_decision.status}")

        # Create new decision
        new_record = DecisionRecord(
            decision=req.new_decision,
            rationale=req.rationale,
            options_considered=[old_decision.decision],
            status="active",
            source_chunk_ids=old_decision.source_chunk_ids or [],
            participants=old_decision.participants or [],
            decided_at=datetime.datetime.utcnow(),
        )
        db.add(new_record)
        db.flush()

        # Supersede old decision
        old_decision.status = "superseded"
        old_decision.superseded_by = new_record.id
        old_decision.superseded_at = datetime.datetime.utcnow()
        old_decision.reversal_reason = req.reason or f"Reversed: {req.new_decision[:200]}"

        db.commit()
        return {
            "status": "reversed",
            "old_decision_id": str(old_decision.id),
            "new_decision_id": str(new_record.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Decision reversal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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

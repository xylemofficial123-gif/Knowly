import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import func, case
import logging
from typing import Optional, List

from app.core.database import SessionLocal
from app.core.auth import get_current_user_email
from app.models import AuditLog, DecisionRecord, AnswerFeedback, GlobalSettings, Document, Chunk, ExclusionRule
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

        # Inherit ACL from the source chunk if we have one. Reviewer-approved
        # items without a source chunk are admin-curated → mark public.
        source_acl: list = []
        if item.source_chunk_id:
            src_chunk = db.query(Chunk).filter(Chunk.id == item.source_chunk_id).first()
            if src_chunk and src_chunk.acl:
                source_acl = list(src_chunk.acl)
        if not source_acl:
            source_acl = ["public"]

        record = DecisionRecord(
            decision=item.proposed_decision,
            rationale=item.proposed_rationale,
            options_considered=[],
            status="active",
            source_chunk_ids=[item.source_chunk_id] if item.source_chunk_id else [],
            participants=[],
            acl=source_acl,
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
def get_decisions(
    status: str = "all",
    limit: int = 50,
    user_email: str = "",
    actor_email: str = Depends(get_current_user_email),
):
    """List decisions with reversal chain info.

    The decision log is reachable from the user-facing sidebar, so ACL-filter
    by `user_email` when provided. Admins (per acl.user_can_see_chunk) bypass
    the filter automatically.

    Each decision is enriched with a derived `visibility` tag and a `groups`
    list (id+name) so the UI can show which team(s) a decision belongs to.
    """
    from app.core.acl import user_can_see_chunk, get_user_role
    from app.models import Group

    def _classify(acl: list) -> tuple[str, list[str]]:
        """Return (visibility_label, group_uuids) from a chunk-style ACL list.

        visibility ∈ {"public", "group", "private"}.  group_uuids contains
        every "group:<uuid>" entry so the caller can look up names.
        """
        if not acl or "public" in acl:
            return "public", []
        gids = [e[len("group:"):] for e in acl if isinstance(e, str) and e.startswith("group:")]
        if gids:
            return "group", gids
        return "private", []

    db = SessionLocal()
    try:
        actor_role = get_user_role(actor_email)
        effective_user = actor_email
        if user_email and user_email.lower() != actor_email.lower():
            if actor_role != "admin":
                raise HTTPException(status_code=403, detail="Only admins can query another user's visibility")
            effective_user = user_email

        query = db.query(DecisionRecord).order_by(DecisionRecord.decided_at.desc())
        if status != "all":
            query = query.filter(DecisionRecord.status == status)
        decisions = query.limit(limit * 2).all()
        decisions = [d for d in decisions if user_can_see_chunk(effective_user, list(d.acl or []))]
        decisions = decisions[:limit]

        # Resolve every group_uuid mentioned across the visible decisions in
        # one query so we can attach human-readable names to each card.
        all_group_ids: set[str] = set()
        derived: dict[str, tuple[str, list[str]]] = {}
        for d in decisions:
            visibility, gids = _classify(list(d.acl or []))
            derived[str(d.id)] = (visibility, gids)
            all_group_ids.update(gids)

        group_name_by_id: dict[str, str] = {}
        if all_group_ids:
            try:
                rows = db.query(Group).filter(Group.id.in_(list(all_group_ids))).all()
                group_name_by_id = {str(g.id): g.name for g in rows}
            except Exception as e:
                logger.warning(f"Group name lookup failed in /decisions: {e}")

        items = []
        for d in decisions:
            visibility, gids = derived[str(d.id)]
            items.append({
                "id": str(d.id),
                "decision": d.decision or "",
                "rationale": d.rationale or "",
                "status": d.status or "active",
                "decided_at": d.decided_at.isoformat() if d.decided_at else "",
                "created_at": d.created_at.isoformat() if d.created_at else "",
                "superseded_by": str(d.superseded_by) if d.superseded_by else None,
                "superseded_at": d.superseded_at.isoformat() if d.superseded_at else None,
                "reversal_reason": d.reversal_reason or None,
                "visibility": visibility,
                "groups": [
                    {"id": gid, "name": group_name_by_id.get(gid, "Unknown group")}
                    for gid in gids
                ],
            })

        return {
            "items": items,
            "total_active": db.query(DecisionRecord).filter(DecisionRecord.status == "active").count(),
            "total_superseded": db.query(DecisionRecord).filter(DecisionRecord.status == "superseded").count(),
        }
    finally:
        db.close()


@router.get("/visibility/documents")
def get_visible_documents(
    limit: int = 200,
    query: str = "",
    user_email: str = "",
    actor_email: str = Depends(get_current_user_email),
):
    """Debug helper: list documents visible to a user after ACL filtering.

    - Non-admins can only inspect themselves.
    - Admins can inspect another user via `user_email`.
    """
    from app.core.acl import user_can_see_chunk, get_user_role

    db = SessionLocal()
    try:
        actor_role = get_user_role(actor_email)
        effective_user = actor_email
        if user_email and user_email.lower() != actor_email.lower():
            if actor_role != "admin":
                raise HTTPException(status_code=403, detail="Only admins can query another user's visibility")
            effective_user = user_email

        docs_all = db.query(Document).order_by(Document.updated_at.desc()).all()
        visible = [d for d in docs_all if user_can_see_chunk(effective_user, list(d.acl or []))]

        q = query.strip().lower()
        if q:
            filtered = []
            for d in visible:
                title = (d.title or "").lower()
                content = (d.content or "")[:4000].lower()
                source_id = (d.source_id or "").lower()
                if q in title or q in content or q in source_id:
                    filtered.append(d)
            visible = filtered

        visible = visible[: max(1, min(limit, 1000))]
        doc_ids = [d.id for d in visible]

        chunk_counts = {}
        if doc_ids:
            rows = (
                db.query(Chunk.document_id, func.count(Chunk.id))
                .filter(Chunk.document_id.in_(doc_ids))
                .group_by(Chunk.document_id)
                .all()
            )
            chunk_counts = {row[0]: int(row[1]) for row in rows}

        by_source = {}
        items = []
        for d in visible:
            by_source[d.source] = by_source.get(d.source, 0) + 1
            items.append(
                {
                    "document_id": str(d.id),
                    "title": d.title or "(untitled)",
                    "source": d.source or "unknown",
                    "source_id": d.source_id or "",
                    "url": d.url or "",
                    "acl": list(d.acl or []),
                    "chunk_count": chunk_counts.get(d.id, 0),
                    "updated_at": d.updated_at.isoformat() if d.updated_at else "",
                }
            )

        return {
            "effective_user": effective_user,
            "query": q,
            "total_visible_documents": len(visible),
            "by_source": by_source,
            "documents": items,
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

        # Create new decision — inherit ACL from the decision being reversed so
        # the new record has the same audience as the original.
        new_record = DecisionRecord(
            decision=req.new_decision,
            rationale=req.rationale,
            options_considered=[old_decision.decision],
            status="active",
            source_chunk_ids=old_decision.source_chunk_ids or [],
            participants=old_decision.participants or [],
            acl=list(old_decision.acl or []) or ["public"],
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

        # ── Deflection Rate (PRD success metric) ──────────────────────────
        # Two signals contribute:
        #  1) Guardian Agent — real-time Slack/ClickUp re-litigation catches.
        #  2) Decision Drift Sweep — periodic detection of contradictory
        #     active decisions across the entire log.
        # Both qualify as "the system surfacing prior context the team would
        # otherwise miss" — exactly what the PRD calls deflection. Combining
        # them gives a meaningful rate even when real-time Slack traffic is
        # light (which it usually is at small scale).
        from app.models import GuardianAlert, DecisionDriftAlert
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        guardian_total = (
            db.query(GuardianAlert)
            .filter(GuardianAlert.created_at >= thirty_days_ago)
            .count()
        )
        # match_count is stored as a string ("0", "1", ...). Anything other
        # than "0" or null means we found prior context.
        guardian_with_matches = (
            db.query(GuardianAlert)
            .filter(
                GuardianAlert.created_at >= thirty_days_ago,
                GuardianAlert.match_count.isnot(None),
                GuardianAlert.match_count != "0",
                GuardianAlert.match_count != "",
            )
            .count()
        )

        drift_alerts_total = (
            db.query(DecisionDriftAlert)
            .filter(DecisionDriftAlert.detected_at >= thirty_days_ago)
            .count()
        )
        drift_alerts_caught = (
            db.query(DecisionDriftAlert)
            .filter(
                DecisionDriftAlert.detected_at >= thirty_days_ago,
                DecisionDriftAlert.contradicts == "yes",
            )
            .count()
        )

        catches = guardian_with_matches + drift_alerts_caught
        # Denominator: every event we evaluated. Floor at 1 so we don't
        # divide by zero when there's been no Slack traffic AND no drift.
        opportunities = max(guardian_total + drift_alerts_total, 1)
        deflection_rate = (catches / opportunities * 100)

        # ── Decision Adherence (PRD success metric) ───────────────────────
        # PRD: "Frequency with which the team sticks to recorded decisions
        # vs. unintentionally drifting." Adherence = active decisions /
        # total decisions; reversals indicate drift over time.
        total_decisions_count = db.query(DecisionRecord).count()
        active_decisions = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.status == "active")
            .count()
        )
        recently_reversed = (
            db.query(DecisionRecord)
            .filter(
                DecisionRecord.superseded_at.isnot(None),
                DecisionRecord.superseded_at >= thirty_days_ago,
            )
            .count()
        )
        adherence_rate = (
            (active_decisions / total_decisions_count * 100)
            if total_decisions_count > 0 else 100.0
        )

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
            # PRD success metrics — last 30 days
            "deflection": {
                "rate": round(deflection_rate, 1),
                "checks_total": opportunities,
                "matches_found": catches,
                "guardian_checks": guardian_total,
                "guardian_matches": guardian_with_matches,
                "drift_checks": drift_alerts_total,
                "drift_caught": drift_alerts_caught,
                "window_days": 30,
            },
            "adherence": {
                "rate": round(adherence_rate, 1),
                "total_decisions": total_decisions_count,
                "active_decisions": active_decisions,
                "reversed_last_30d": recently_reversed,
            },
            "agent_usage": agent_usage,
            "query_type_usage": query_type_usage,
            "daily_usage": daily_usage,
        }
    finally:
        db.close()
# --- Global Settings ---

class SettingsUpdate(BaseModel):
    enabled_sources: Optional[List[str]] = None
    google_drive_folder_ids: Optional[List[str]] = None


@router.get("/settings")
def get_settings():
    db = SessionLocal()
    try:
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not settings:
            # Create default if not exists
            settings = GlobalSettings(
                id="default",
                enabled_sources=["drive"],
                google_drive_folder_ids=[]
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return {
            "enabled_sources": settings.enabled_sources,
            "google_drive_folder_ids": settings.google_drive_folder_ids,
        }
    finally:
        db.close()


@router.patch("/settings")
def update_settings(req: SettingsUpdate):
    db = SessionLocal()
    try:
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not settings:
            settings = GlobalSettings(id="default")
            db.add(settings)
        
        if req.enabled_sources is not None:
            settings.enabled_sources = req.enabled_sources
        if req.google_drive_folder_ids is not None:
            settings.google_drive_folder_ids = req.google_drive_folder_ids
            
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        logger.error(f"Update settings failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/graph")
def get_graph_data(actor_email: str = Depends(get_current_user_email)):
    """Return knowledge graph data: source breakdown, project clusters, people, recent docs."""
    import re
    from app.core.acl import user_can_see_chunk
    db = SessionLocal()
    try:
        docs_all = db.query(Document).all()
        visible_docs = [d for d in docs_all if user_can_see_chunk(actor_email, list(d.acl or []))]

        # Source node counts
        source_counter: dict[str, int] = {}
        for d in visible_docs:
            source_counter[d.source] = source_counter.get(d.source, 0) + 1
        sources = [{"id": s, "count": c} for s, c in source_counter.items()]

        # Derive project clusters from non-calendar doc titles only
        clusterable_docs = [
            (d.title, d.source, d.url, d.created_at)
            for d in visible_docs
            if d.source not in ("calendar",)
        ]
        project_map: dict = {}
        for title, source, url, created_at in clusterable_docs:
            if not title:
                continue
            # Extract project name: first word before underscore, dash, or space — must be meaningful (len >= 3)
            match = re.match(r"^([A-Za-z]{3,})", re.sub(r"[\-_ ].*", "", title))
            raw = match.group(1) if match else "Other"
            # Capitalise consistently
            project = raw.capitalize()
            if project not in project_map:
                project_map[project] = {"name": project, "count": 0, "sources": set(), "docs": []}
            project_map[project]["count"] += 1
            project_map[project]["sources"].add(source)
            if len(project_map[project]["docs"]) < 5:
                project_map[project]["docs"].append({
                    "title": title,
                    "source": source,
                    "url": url or "",
                })
        clusters = [
            {**v, "sources": list(v["sources"])}
            for v in sorted(project_map.values(), key=lambda x: -x["count"])
        ]

        # People: collect unique emails from Document ACL lists
        people_count: dict = {}
        for d in visible_docs:
            acl = d.acl
            if not acl:
                continue
            for entry in acl:
                if "@" in str(entry) and entry not in ("public",):
                    people_count[entry] = people_count.get(entry, 0) + 1
        people = [{"email": e, "doc_count": c} for e, c in sorted(people_count.items(), key=lambda x: -x[1])[:20]]

        # Recent 10 docs
        recent = sorted(
            visible_docs,
            key=lambda d: d.created_at or datetime.datetime.min,
            reverse=True,
        )[:10]
        recent_docs = [{"title": d.title, "source": d.source, "url": d.url or "", "created_at": d.created_at.isoformat() if d.created_at else ""} for d in recent]

        # Totals
        total_docs = len(visible_docs)
        visible_doc_ids = {d.id for d in visible_docs}
        total_chunks = db.query(Chunk).filter(Chunk.document_id.in_(visible_doc_ids)).count() if visible_doc_ids else 0
        # Decisions are globally derived; ACL-filtered decision graph can be added later.
        total_decisions = db.query(DecisionRecord).count()

        # Entity graph — the cross-source connective tissue. Built by
        # process_document_entities (one LLM call per ingested doc + gazetteer).
        # ACL filter: only count mentions whose chunk lives in a doc this user can see.
        from app.models import Entity, EntityMention, EntityCooccurrence
        entity_rows = []
        entity_links: list = []
        try:
            entities_all = db.query(Entity).all()
            mentions_for_visible = (
                db.query(EntityMention)
                .filter(EntityMention.document_id.in_(visible_doc_ids))
                .all()
                if visible_doc_ids else []
            )

            # Aggregate per entity: mention count + source breakdown + top docs
            agg: dict = {}
            doc_lookup = {d.id: d for d in visible_docs}
            for m in mentions_for_visible:
                bucket = agg.setdefault(
                    m.entity_id,
                    {"mention_count": 0, "sources": {}, "doc_ids": set()},
                )
                bucket["mention_count"] += 1
                src = m.source or "unknown"
                bucket["sources"][src] = bucket["sources"].get(src, 0) + 1
                if m.document_id is not None:
                    bucket["doc_ids"].add(m.document_id)

            for ent in entities_all:
                stats = agg.get(ent.id)
                if not stats:
                    continue
                top_docs = []
                for doc_id in list(stats["doc_ids"])[:5]:
                    d = doc_lookup.get(doc_id)
                    if d:
                        top_docs.append({"title": d.title or "(untitled)", "source": d.source, "url": d.url or ""})
                entity_rows.append({
                    "id": str(ent.id),
                    "canonical_name": ent.canonical_name,
                    "entity_type": ent.entity_type,
                    "aliases": list(ent.aliases or []),
                    "mention_count": stats["mention_count"],
                    "source_count": len(stats["sources"]),
                    "sources": [{"id": s, "count": c} for s, c in sorted(stats["sources"].items(), key=lambda x: -x[1])],
                    "top_docs": top_docs,
                })
            # Sort: most-cross-source first, then most-mentioned
            entity_rows.sort(key=lambda e: (-e["source_count"], -e["mention_count"]))
            entity_rows = entity_rows[:60]

            # Entity-to-entity edges — only between entities the user can see.
            visible_entity_ids = {row["id"] for row in entity_rows}
            if visible_entity_ids:
                edges = (
                    db.query(EntityCooccurrence)
                    .order_by(EntityCooccurrence.weight.desc())
                    .limit(400)
                    .all()
                )
                for e in edges:
                    a_id = str(e.entity_a_id)
                    b_id = str(e.entity_b_id)
                    if a_id in visible_entity_ids and b_id in visible_entity_ids:
                        entity_links.append({"source": a_id, "target": b_id, "weight": float(e.weight or 0)})
                # Cap to top 200 by weight after filtering for visibility
                entity_links.sort(key=lambda x: -x["weight"])
                entity_links = entity_links[:200]
        except Exception as e:
            logger.warning(f"Entity graph aggregation failed: {e}")
            entity_rows = []
            entity_links = []

        return {
            "totals": {"docs": total_docs, "chunks": total_chunks, "decisions": total_decisions},
            "sources": sources,
            "clusters": clusters,
            "people": people,
            "recent_docs": recent_docs,
            "entities": entity_rows,
            "entity_links": entity_links,
        }
    finally:
        db.close()


@router.post("/decisions/extract")
def trigger_decision_extraction():
    """Run decision extraction over all ingested chunks."""
    try:
        from app.services.decision_extractor import run_extraction_on_all_chunks
        run_extraction_on_all_chunks()
        db = SessionLocal()
        count = db.query(DecisionRecord).count()
        db.close()
        return {"status": "ok", "decisions_total": count}
    except Exception as e:
        logger.error(f"Decision extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Exclusion Rules (No-Index Zones) ---

VALID_EXCLUSION_SOURCES = {"drive", "slack", "clickup"}


class ExclusionRuleRequest(BaseModel):
    source_type: str  # drive | slack | clickup
    identifier: str   # folder ID, channel ID, space ID
    name: str = ""    # human-readable label
    reason: str = ""


@router.get("/exclusion-rules")
def list_exclusion_rules():
    db = SessionLocal()
    try:
        rules = db.query(ExclusionRule).order_by(ExclusionRule.created_at.desc()).all()
        return {
            "rules": [
                {
                    "id": str(r.id),
                    "source_type": r.source_type,
                    "identifier": r.identifier,
                    "name": r.name or "",
                    "reason": r.reason or "",
                    "created_by": r.created_by or "",
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rules
            ]
        }
    finally:
        db.close()


@router.post("/exclusion-rules")
def create_exclusion_rule(req: ExclusionRuleRequest):
    if req.source_type not in VALID_EXCLUSION_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"source_type must be one of: {', '.join(VALID_EXCLUSION_SOURCES)}",
        )
    db = SessionLocal()
    try:
        existing = (
            db.query(ExclusionRule)
            .filter(
                ExclusionRule.source_type == req.source_type,
                ExclusionRule.identifier == req.identifier,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="This exclusion rule already exists")

        rule = ExclusionRule(
            source_type=req.source_type,
            identifier=req.identifier,
            name=req.name,
            reason=req.reason,
        )
        db.add(rule)
        db.commit()
        return {"status": "created", "id": str(rule.id)}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create exclusion rule failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/exclusion-rules/{rule_id}")
def delete_exclusion_rule(rule_id: str):
    db = SessionLocal()
    try:
        rule = db.query(ExclusionRule).filter(ExclusionRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Exclusion rule not found")
        db.delete(rule)
        db.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete exclusion rule failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


VALID_SOURCES = {"drive", "meet", "calendar", "slack", "clickup", "upload"}

@router.delete("/clear-source/{source}")
def clear_source(source: str):
    """Delete all ingested data for a given source (drive, meet, calendar, slack, clickup, upload)."""
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source. Must be one of: {', '.join(VALID_SOURCES)}")

    db = SessionLocal()
    try:
        # Collect document IDs for this source
        docs = db.query(Document).filter(Document.source == source).all()
        doc_ids = [d.id for d in docs]
        embedding_ids = []

        # Collect embedding_ids from chunks before deleting
        if doc_ids:
            chunks = db.query(Chunk).filter(Chunk.document_id.in_(doc_ids)).all()
            embedding_ids = [c.embedding_id for c in chunks if c.embedding_id]
            # Delete chunks
            db.query(Chunk).filter(Chunk.document_id.in_(doc_ids)).delete(synchronize_session=False)
            # Delete documents
            db.query(Document).filter(Document.source == source).delete(synchronize_session=False)

        db.commit()

        # Delete vectors from Qdrant
        qdrant_deleted = 0
        if embedding_ids:
            try:
                from app.services.embeddings import qdrant, COLLECTION
                from qdrant_client.models import PointIdsList
                qdrant.delete(
                    collection_name=COLLECTION,
                    points_selector=PointIdsList(points=embedding_ids),
                )
                qdrant_deleted = len(embedding_ids)
            except Exception as e:
                logger.warning(f"Qdrant deletion partial/failed: {e}")

        logger.info(f"Cleared source={source}: {len(doc_ids)} docs, {len(embedding_ids)} vectors")
        return {
            "status": "ok",
            "source": source,
            "docs_deleted": len(doc_ids),
            "vectors_deleted": qdrant_deleted,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Clear source failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ── Backfill endpoints ────────────────────────────────────────────────────────
# After deploying entity-graph + version-awareness changes, existing docs in
# prod still need their entities extracted and (for Slack/ClickUp) their
# doc_status recomputed. These endpoints walk existing data and apply the new
# logic. Admin-only — these are heavy operations.

from app.core.auth import require_admin


class GhostDocTestRequest(BaseModel):
    email: str
    decision: Optional[str] = "Test decision: deprecate the legacy authentication module"
    rationale: Optional[str] = "It's a synthetic test from /api/admin/test-ghost-doc"


@router.post("/test-ghost-doc")
def test_ghost_doc(req: GhostDocTestRequest, actor: str = Depends(require_admin)):
    """Synthetic end-to-end test of the Meet → Slack ghost-documentation pipeline.

    Walks the same code path as a real Meet ingestion would:
      1. Resolve `email` → Slack user ID via users.lookupByEmail
      2. Fire `send_ghost_doc_prompt` with a fake decision

    Returns each step's success/failure so you can pinpoint what's broken
    (token missing, email not in workspace, etc.) without waiting 30+ min
    for a real Meet sync cycle.
    """
    result = {
        "input_email": req.email,
        "step_1_slack_lookup": {"ok": False, "slack_user_id": None, "error": None},
        "step_2_send_dm": {"ok": False, "error": None},
        "overall": "FAIL",
    }
    try:
        from app.services.ghost_docs import slack_email_to_user_id, send_ghost_doc_prompt
    except Exception as e:
        result["step_1_slack_lookup"]["error"] = f"import failed: {e}"
        return result

    # Step 1: email → Slack user ID
    try:
        slack_id = slack_email_to_user_id(req.email)
        if slack_id:
            result["step_1_slack_lookup"]["ok"] = True
            result["step_1_slack_lookup"]["slack_user_id"] = slack_id
        else:
            result["step_1_slack_lookup"]["error"] = (
                "Slack returned no user — either SLACK_BOT_TOKEN is missing/invalid "
                "on the API service, or the email is not a member of the Slack workspace."
            )
            return result
    except Exception as e:
        result["step_1_slack_lookup"]["error"] = f"{type(e).__name__}: {e}"[:300]
        return result

    # Step 2: send the DM with a fake decision
    fake_decision = {
        "decision": req.decision,
        "rationale": req.rationale,
        "options_considered": ["Option A (test)", "Option B (test)"],
        "acl_override": ["public"],
    }
    try:
        send_ghost_doc_prompt(
            slack_id,
            fake_decision,
            chunk_id="test-ghost-doc-synthetic",
            source_url="https://example.com/synthetic-test",
        )
        result["step_2_send_dm"]["ok"] = True
        result["overall"] = "PASS"
        return result
    except Exception as e:
        result["step_2_send_dm"]["error"] = f"{type(e).__name__}: {e}"[:300]
        return result


@router.get("/env-check")
def env_check(actor: str = Depends(require_admin)):
    """Diagnose which LLM keys are visible on each Railway service.

    Reports:
    - backend: which keys this API service sees
    - worker:  which keys the Celery worker sees, plus result of a live
               generate() call (so we know if keys *work*, not just exist)

    Without this it's painful to figure out which service is missing
    a var, since Railway scopes env vars per-service.
    """
    from app.core.config import settings as app_settings
    from app.workers.tasks import probe_llm_env

    backend = {
        "gemini": bool(app_settings.GEMINI_API_KEY),
        "groq": bool(app_settings.GROQ_API_KEY),
        "openrouter": bool(app_settings.OPENROUTER_API_KEY),
    }

    worker = {"error": None}
    try:
        result = probe_llm_env.apply_async()
        worker = result.get(timeout=15)
    except Exception as e:
        worker = {"error": f"{type(e).__name__}: {e}"[:300]}

    return {"backend": backend, "worker": worker}


@router.post("/backfill/entities")
def backfill_entities(actor: str = Depends(require_admin)):
    """Queue entity-graph extraction for every existing document.

    The actual work runs in Celery (`extract_entities_for_document`), one task
    per document. This endpoint just enqueues — returns immediately. Watch
    Celery logs for progress.
    """
    from app.workers.tasks import extract_entities_for_document
    db = SessionLocal()
    try:
        doc_ids = [str(d.id) for d in db.query(Document.id).all()]
        for doc_id in doc_ids:
            try:
                extract_entities_for_document.delay(doc_id)
            except Exception as e:
                logger.warning(f"Could not queue entity extraction for {doc_id}: {e}")
        logger.info(f"Backfill: queued entity extraction for {len(doc_ids)} docs (actor={actor})")
        return {"status": "queued", "documents_queued": len(doc_ids)}
    finally:
        db.close()


@router.post("/backfill/doc-status")
def backfill_doc_status(actor: str = Depends(require_admin)):
    """Recompute doc_status for existing Slack + ClickUp documents.

    Drive already gets doc_status at ingestion via title/content heuristics —
    skipped here to avoid clobbering. Slack: re-runs phrase regex on stored
    content (pinned-state was lost at ingestion, so pinned messages need
    re-ingestion to be detected as finalized). ClickUp: parses the "Status: X"
    line that ingestion injects into the document body.

    Updates both Document.doc_status and the Qdrant payload of every chunk in
    the doc so search ranking picks up the new label.
    """
    from app.services.slack_ingestion import _detect_slack_doc_status
    from app.services.clickup_ingestion import _map_clickup_status
    from app.services.embeddings import qdrant, COLLECTION
    import re as _re

    db = SessionLocal()
    counts = {"slack": 0, "clickup": 0, "skipped": 0, "qdrant_updated": 0}
    try:
        docs = db.query(Document).filter(Document.source.in_(("slack", "clickup"))).all()
        for d in docs:
            content = d.content or ""
            new_status = "unknown"
            if d.source == "slack":
                # We no longer have the original msg dict — pinned state can't be
                # recovered, but the phrase regex still works on the stored text.
                new_status = _detect_slack_doc_status({}, content)
            elif d.source == "clickup":
                # Ingestion writes "Status: <task status>" into the body.
                m = _re.search(r"^Status:\s*(.+)$", content, _re.MULTILINE)
                raw_status = m.group(1).strip() if m else ""
                new_status = _map_clickup_status(raw_status)

            if new_status == d.doc_status:
                counts["skipped"] += 1
                continue

            d.doc_status = new_status
            counts[d.source] += 1

            # Update Qdrant payload for every chunk in this doc
            chunks = db.query(Chunk).filter(Chunk.document_id == d.id).all()
            for c in chunks:
                if not c.embedding_id:
                    continue
                try:
                    qdrant.set_payload(
                        collection_name=COLLECTION,
                        payload={"doc_status": new_status},
                        points=[c.embedding_id],
                    )
                    counts["qdrant_updated"] += 1
                except Exception as e:
                    logger.debug(f"Qdrant payload update failed for {c.embedding_id}: {e}")

        db.commit()
        logger.info(f"Backfill doc-status: {counts} (actor={actor})")
        return {"status": "ok", **counts}
    except Exception as e:
        db.rollback()
        logger.error(f"Backfill doc-status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ── Cache management ────────────────────────────────────────────────────────


@router.post("/cache/clear")
def clear_query_cache(actor: str = Depends(require_admin)):
    """Drop every cached response. Use after seeding demo data or
    when a stale answer is shown."""
    from app.services import query_cache
    cleared = query_cache.clear()
    return {"cleared": cleared}


# ── Demo seeding ────────────────────────────────────────────────────────────


@router.post("/seed-demo-data")
def seed_demo_data(actor: str = Depends(require_admin)):
    """Insert curated demo decisions + supporting chunks so the Oracle has
    rich, citation-quality answers on stage. Idempotent — re-running upserts.

    Each entry produces:
      1. A Document + Chunks (visible to Oracle retrieval, ACL=public)
      2. A DecisionRecord (visible in /decisions UI)

    All seed rows are tagged with source_id starting "demo:" so they can be
    cleared via /api/admin/clear-source/demo (well, "demo" is treated as
    a regular source name).
    """
    from app.services.chunker import chunk_and_store
    from app.core.timezone import now_utc
    import datetime as _dt

    seeds = [
        {
            "slug": "stripe-vs-adyen",
            "decision": "Use Stripe over Adyen as the payment provider",
            "rationale": "Better developer velocity and clearer pricing for India transactions",
            "options": ["Adyen", "Razorpay"],
            "decided_at": _dt.datetime(2026, 4, 30, 23, 5, 0),
            "title": "Decision: Stripe over Adyen — payment provider",
            "text": (
                "After three weeks of evaluation, we're going with Stripe over Adyen as our payment provider. "
                "Reasons: Stripe's developer velocity is unmatched (test mode + clear docs cut our integration estimate from 3 weeks to 1), "
                "their India pricing is transparent (2.9% + INR 3 vs Adyen's variable interchange-plus model that needed a sales call), "
                "and their support tier covers our volume without an enterprise contract. "
                "Razorpay was also evaluated but their international card support is limited. "
                "Decision owners: Krithin (eng), Sachin (product). Effective date: 30/04/2026."
            ),
        },
        {
            "slug": "postgres-vs-mongo",
            "decision": "Use Postgres over MongoDB for the user service",
            "rationale": "Strong schema guarantees + native JSON columns avoid losing the flexibility argument",
            "options": ["MongoDB", "DynamoDB"],
            "decided_at": _dt.datetime(2026, 3, 12, 16, 0, 0),
            "title": "Decision: Postgres over MongoDB — user service database",
            "text": (
                "We're standardising on Postgres for the user service. MongoDB was the alternative, "
                "and DynamoDB was briefly considered. Reasons for Postgres: (a) strict relational guarantees "
                "for billing-adjacent data we cannot afford to lose, (b) JSONB columns give us most of Mongo's "
                "schema flexibility without giving up transactions, (c) team has 6+ years of operational "
                "experience with Postgres vs zero with Mongo at scale. The flexibility argument for Mongo "
                "didn't survive when we measured it against JSONB. Decided 12/03/2026."
            ),
        },
        {
            "slug": "clickup-over-asana",
            "decision": "Adopt ClickUp over Asana as the company project tracker",
            "rationale": "Better support for nested sprint hierarchies and a free tier sufficient for our team size",
            "options": ["Asana", "Linear", "Jira"],
            "decided_at": _dt.datetime(2026, 2, 18, 14, 30, 0),
            "title": "Decision: ClickUp project tracker",
            "text": (
                "Project tracker decision: ClickUp wins. Asana was the runner-up. Linear was rejected because "
                "it forced an engineering-only workflow that doesn't fit ops/marketing. Jira was rejected on "
                "cost and onboarding pain. ClickUp's nested sprints handle our 'epic → sprint → task → subtask' "
                "structure without workarounds, and the free tier covers our headcount today. Migration window: "
                "Feb 18 → Mar 5 2026."
            ),
        },
        {
            "slug": "two-week-sprint-cadence",
            "decision": "Use 2-week sprint cadence for engineering",
            "rationale": "1-week is too short for stable estimation; 4-week loses momentum",
            "options": ["1-week sprints", "4-week sprints"],
            "decided_at": _dt.datetime(2026, 4, 12, 11, 0, 0),
            "title": "Decision: Engineering sprint cadence",
            "text": (
                "Engineering will run 2-week sprints starting 15/04/2026. We considered 1-week sprints "
                "(rejected — too much overhead, ceremony eats focus time) and 4-week sprints (rejected — "
                "too much drift before correction). Two weeks is the cadence that matches the team's natural "
                "rhythm and ClickUp's default sprint folder pattern."
            ),
        },
        {
            "slug": "code-review-two-approvals",
            "decision": "Require 2 approvals for any merge to main",
            "rationale": "One reviewer missed a regression that broke prod last quarter; bus factor of 1 is too thin",
            "options": ["1 approval", "Conditional 1 approval for trivial PRs"],
            "decided_at": _dt.datetime(2026, 1, 28, 10, 0, 0),
            "title": "Decision: 2-approval merge policy",
            "text": (
                "Effective immediately, all merges to main require 2 approvals. The Q4 incident where a "
                "single approver missed a memory leak that took prod down for 47 minutes was the trigger. "
                "We considered keeping 1-approval for trivial PRs but the cognitive cost of deciding 'is "
                "this trivial?' isn't worth the time saved. Owner: Krithin."
            ),
        },
        {
            "slug": "weekly-oncall-rotation",
            "decision": "Run a weekly on-call rotation across the engineering team",
            "rationale": "Daily rotation is exhausting; bi-weekly leaves too much context-switching when handing off active incidents",
            "options": ["Daily rotation", "Bi-weekly rotation"],
            "decided_at": _dt.datetime(2026, 3, 5, 9, 30, 0),
            "title": "Decision: On-call cadence",
            "text": (
                "On-call will run a weekly rotation starting Monday 09:00 IST → following Monday 09:00 IST. "
                "Daily was rejected (no one builds context); bi-weekly was rejected (handoffs of active "
                "incidents become risky). Six engineers in the rotation; primary + secondary every week. "
                "Pager via PagerDuty. Decided 05/03/2026."
            ),
        },
        {
            "slug": "local-embeddings-vs-openai",
            "decision": "Use local fastembed (BAAI/bge-small) for embeddings instead of OpenAI's API",
            "rationale": "Free, sufficient for our query volume, and keeps source content from leaving our infra",
            "options": ["OpenAI text-embedding-3-small", "Cohere embed v3"],
            "decided_at": _dt.datetime(2026, 4, 2, 15, 45, 0),
            "title": "Decision: Local embeddings via fastembed",
            "text": (
                "Embeddings: we're using fastembed with BAAI/bge-small-en-v1.5 (384 dims) running locally "
                "on the API service. Alternatives considered: OpenAI text-embedding-3-small (rejected — sends "
                "every chunk of internal data to OpenAI), Cohere embed v3 (rejected — same data-sovereignty "
                "concern + paid). Local model is free, runs in ~80ms per chunk on CPU, and benchmarks within "
                "5% of the paid options on our retrieval test set. Decided 02/04/2026."
            ),
        },
        {
            "slug": "public-q4-roadmap",
            "decision": "Publish the Q4 2026 product roadmap publicly on the company blog",
            "rationale": "Customer transparency and recruiting signal; competitive risk is low for an early-stage product",
            "options": ["Customer-only roadmap", "Internal-only roadmap"],
            "decided_at": _dt.datetime(2026, 4, 25, 17, 0, 0),
            "title": "Decision: Public Q4 2026 roadmap",
            "text": (
                "We will publish the Q4 2026 product roadmap publicly on the company blog the first week of "
                "October. Considered: customer-only (rejected — recruiting and brand benefit comes from the "
                "*public* signal, not just customers seeing it) and internal-only (rejected — we lose the "
                "trust-building motion that worked well in Q2). Risk acknowledged: competitors will see it "
                "first. Mitigation: keep tactical details out, publish themes and sequencing only. "
                "Decided 25/04/2026."
            ),
        },
        # ── Deliberate drift seeds — give the drift-sweep something to surface
        # on stage. These are recorded as separate active decisions because the
        # per-write reversal check didn't catch them at extraction time (e.g.
        # different wording, different author, weeks apart). The periodic
        # sweep should flag them as contradicting the earlier active decisions
        # listed above.
        {
            "slug": "biweekly-oncall-pivot",
            "decision": "Move engineering on-call from weekly rotation to bi-weekly",
            "rationale": "Weekly cadence was burning out engineers; new joiners need more handoff time",
            "options": ["Keep weekly", "Monthly rotation"],
            "decided_at": _dt.datetime(2026, 5, 3, 11, 30, 0),
            "title": "Decision: Bi-weekly on-call cadence",
            "text": (
                "Reversing course on engineering on-call cadence: we're moving from the weekly rotation we "
                "set in March to a bi-weekly rotation. The weekly cadence didn't account for incident "
                "carry-over — engineers were starting their on-call week mid-incident from the previous "
                "rotation, which created handoff confusion and burnout. Two weeks gives enough buffer to "
                "fully resolve and document an incident before passing the pager. We considered monthly "
                "rotation but rejected it — too much context decays in a month. Decided 03/05/2026."
            ),
        },
        {
            "slug": "monthly-billing-smb",
            "group": "Orchard",
            "decision": "Add monthly billing tier for SMB customers",
            "rationale": "Self-serve trial conversion stalls at the annual-contract checkout for SMBs under 20 employees",
            "options": ["Quarterly billing", "Stay annual-only"],
            "decided_at": _dt.datetime(2026, 5, 4, 16, 0, 0),
            "title": "Decision: Monthly billing tier for SMB",
            "text": (
                "Adding a monthly billing option for the SMB segment. Self-serve trial-to-paid conversion "
                "data from the last 90 days shows we lose ~38% of qualified SMB trials at the annual-commit "
                "checkout step. A monthly tier at 1.2x the equivalent annual price gives the customer "
                "optionality and still nudges them toward annual over time. Mid-market and enterprise stay "
                "annual-only. Decided 04/05/2026."
            ),
        },
    ]

    # Project-scoped seeds. These create the appearance of three internal
    # projects (AI Labs / Sprout / Orchard), each with its own decisions
    # visible only to that project's group. Drives the Quick Onboarding UX
    # which renders one card per group and surfaces decisions when clicked.
    demo_groups_spec = [
        {"name": "AI Labs", "description": "AI/ML platform research — reasoning agents and embeddings"},
        {"name": "Sprout", "description": "Mobile-first consumer app — beta cohort"},
        {"name": "Orchard", "description": "B2B revenue, GTM strategy, and contract structure"},
    ]

    project_seeds = [
        # AI Labs
        {
            "slug": "claude-for-reasoning-agents",
            "group": "AI Labs",
            "decision": "Use Claude over GPT-4 for reasoning agents in AI Labs",
            "rationale": "Stronger tool-use accuracy and longer context window for multi-step reasoning",
            "options": ["GPT-4o", "Gemini 2.5 Pro"],
            "decided_at": _dt.datetime(2026, 4, 18, 14, 30, 0),
            "title": "AI Labs — Claude as primary reasoning model",
            "text": (
                "AI Labs is standardising on Claude as the default reasoning model for our agents. "
                "GPT-4o was the runner-up but lost on tool-use accuracy in our internal eval — Claude "
                "gets multi-step tool sequences right ~12% more often. Gemini 2.5 Pro was rejected on "
                "context-window stability under heavy tool fan-out. We'll keep Gemini in the free fallback "
                "tier for production, but R&D defaults to Claude. Decided 18/04/2026."
            ),
        },
        {
            "slug": "rag-over-finetuning",
            "group": "AI Labs",
            "decision": "Use RAG over fine-tuning for v1 of all knowledge agents",
            "rationale": "Avoid coupling product to one model vendor; fresh data without re-training",
            "options": ["Fine-tune Llama 3", "Hybrid"],
            "decided_at": _dt.datetime(2026, 3, 22, 11, 0, 0),
            "title": "AI Labs — RAG-first architecture",
            "text": (
                "Decision: All AI Labs agents will use retrieval-augmented generation in v1, not "
                "fine-tuned models. Fine-tuning Llama 3 was considered but rejected — it would lock the "
                "product to one model vendor and require re-training every time the underlying knowledge "
                "base changes. RAG keeps the model swappable and the data fresh. We may revisit fine-tuning "
                "for narrow tasks (entity extraction) once volume justifies it. Decided 22/03/2026."
            ),
        },
        {
            "slug": "ailabs-eval-harness",
            "group": "AI Labs",
            "decision": "Build an internal eval harness before shipping any agent to production",
            "rationale": "Vibes-based testing failed in Q1 — we shipped a regression that took 3 days to catch",
            "options": ["Manual testing", "External eval service"],
            "decided_at": _dt.datetime(2026, 5, 1, 9, 15, 0),
            "title": "AI Labs — Mandatory eval harness",
            "text": (
                "Effective immediately, no AI Labs agent ships to prod without passing an internal eval "
                "harness covering retrieval recall, citation accuracy, and refusal correctness. The Q1 "
                "regression — where an agent silently started fabricating decisions — wasn't caught for "
                "three days because we relied on vibes. External services like Promptfoo were considered "
                "but rejected for data-sovereignty reasons. We'll build it in-house. Owner: AI Labs eng lead."
            ),
        },
        # Sprout
        {
            "slug": "sprout-mobile-first",
            "group": "Sprout",
            "decision": "Build Sprout as mobile-first for v1, defer web to v2",
            "rationale": "Target audience checks the app 8+ times daily on mobile; web is rare",
            "options": ["Web-first", "Desktop app"],
            "decided_at": _dt.datetime(2026, 2, 28, 16, 45, 0),
            "title": "Sprout — Mobile-first product strategy",
            "text": (
                "Sprout will ship mobile-first. User research shows our target cohort (consumers ages "
                "18–34) opens the app 8–12 times per day on mobile and almost never on desktop. Web was "
                "considered for v1 but the resource cost of dual-platform was 2.5x and the engagement "
                "lift was estimated at <10%. Web ships in v2 once we hit 10K MAU. Decided 28/02/2026."
            ),
        },
        {
            "slug": "sprout-react-native",
            "group": "Sprout",
            "decision": "Use React Native instead of Flutter for Sprout's mobile app",
            "rationale": "Engineering team already has 4 years of JS/RN experience; library ecosystem is bigger",
            "options": ["Flutter", "Native iOS + Android (separate codebases)"],
            "decided_at": _dt.datetime(2026, 3, 8, 13, 0, 0),
            "title": "Sprout — React Native for v1",
            "text": (
                "Sprout's mobile codebase will be React Native. Flutter was a serious contender — its "
                "render performance is genuinely better — but our team has 4+ years of JS/RN experience "
                "and zero Dart. Going Flutter would have cost a quarter of ramp-up. Native iOS + Android "
                "in parallel was rejected on cost. We accept the marginal performance hit. Decided 08/03/2026."
            ),
        },
        {
            "slug": "sprout-beta-50-users",
            "group": "Sprout",
            "decision": "Closed beta is 50 hand-picked waitlist users; no public launch yet",
            "rationale": "Need tight feedback loop before scaling; risk of negative reviews from buggy v1",
            "options": ["100-user open beta", "Soft launch in single market"],
            "decided_at": _dt.datetime(2026, 4, 14, 18, 0, 0),
            "title": "Sprout — 50-user closed beta",
            "text": (
                "Sprout's beta cohort is 50 users hand-picked from the waitlist. We considered a 100-user "
                "open beta but rejected it — at 100 the feedback loop becomes too noisy to act on, and "
                "the risk of negative public reviews on a buggy v1 hurts long-term acquisition. Soft launch "
                "in a single market was also rejected — geography isn't the variable we want to control "
                "this round; usage intent is. Decided 14/04/2026."
            ),
        },
        # Orchard
        {
            "slug": "orchard-b2b-first",
            "group": "Orchard",
            "decision": "Orchard goes B2B-first; consumer is post-Series A",
            "rationale": "Higher LTV, shorter sales cycles via existing operator network, predictable revenue",
            "options": ["Consumer-first", "Marketplace"],
            "decided_at": _dt.datetime(2026, 1, 22, 10, 30, 0),
            "title": "Orchard — B2B-first GTM",
            "text": (
                "Orchard's go-to-market is B2B-first. Consumer was the alternative path but our existing "
                "operator network gives us a 10x faster B2B sales cycle, and the LTV math is dramatically "
                "better — average B2B deal is ~$24K ARR vs an estimated $90 LTV for consumer. We revisit "
                "consumer post-Series A when we have the cash to fund a real CAC budget. Decided 22/01/2026."
            ),
        },
        {
            "slug": "orchard-annual-only",
            "group": "Orchard",
            "decision": "Orchard contracts are annual only; no monthly billing",
            "rationale": "Predictable ARR; reduces churn-driven instability for early growth team",
            "options": ["Monthly billing", "Quarterly billing"],
            "decided_at": _dt.datetime(2026, 2, 11, 12, 0, 0),
            "title": "Orchard — Annual-only contracts",
            "text": (
                "Orchard sells annual contracts only. Monthly billing was considered for friction "
                "reduction but rejected — at our stage, predictable ARR matters more than top-of-funnel "
                "conversion rate. Monthly customers churn ~3x faster than annual, which would force us "
                "to over-invest in retention infrastructure we don't have yet. Quarterly was a compromise "
                "that wins neither argument. Decided 11/02/2026."
            ),
        },
        {
            "slug": "orchard-self-serve-smb",
            "group": "Orchard",
            "decision": "Self-serve trial for the SMB segment; sales-led for mid-market and up",
            "rationale": "Capture the long tail without sales overhead; protect AE bandwidth for higher-ACV deals",
            "options": ["Sales-led across all segments", "Self-serve across all segments"],
            "decided_at": _dt.datetime(2026, 4, 5, 15, 30, 0),
            "title": "Orchard — Hybrid sales motion",
            "text": (
                "Orchard's sales motion is split: SMB (<50 employees) self-serves with a 14-day trial; "
                "mid-market and enterprise are sales-led with named AEs. Pure sales-led was rejected — "
                "we'd miss the long tail and our AE team isn't big enough to cover SMB profitably. Pure "
                "self-serve was rejected — enterprise procurement requires human relationships at our "
                "ACV. The hybrid lets us capture both ends. Decided 05/04/2026."
            ),
        },
    ]

    db = SessionLocal()
    created = []
    upserted = []
    try:
        # Ensure demo groups exist (idempotent on name).
        from app.models import Group
        group_id_by_name: dict[str, str] = {}
        for g in demo_groups_spec:
            row = db.query(Group).filter(Group.name == g["name"]).first()
            if row:
                if g["description"] and not row.description:
                    row.description = g["description"]
            else:
                row = Group(
                    name=g["name"],
                    description=g["description"],
                    created_by_email=actor,
                )
                db.add(row)
                db.flush()
            group_id_by_name[g["name"]] = str(row.id)
        db.commit()

        all_seeds = seeds + project_seeds
        for seed in all_seeds:
            source_id = f"demo:{seed['slug']}"
            project_group = seed.get("group")
            if project_group and project_group in group_id_by_name:
                seed_acl = [f"group:{group_id_by_name[project_group]}"]
            else:
                seed_acl = ["public"]

            chunk_and_store(
                source="demo",
                source_id=source_id,
                text=seed["text"],
                url=f"https://demo.xylem.ai/decisions/{seed['slug']}",
                acl=seed_acl,
                title=seed["title"],
                doc_status="finalized",
            )

            existing = (
                db.query(DecisionRecord)
                .filter(DecisionRecord.decision == seed["decision"])
                .first()
            )
            if existing:
                existing.decision = seed["decision"]
                existing.rationale = seed["rationale"]
                existing.options_considered = seed["options"]
                existing.decided_at = seed["decided_at"]
                existing.acl = seed_acl
                existing.status = "active"
                upserted.append(seed["slug"])
            else:
                rec = DecisionRecord(
                    decision=seed["decision"],
                    rationale=seed["rationale"],
                    options_considered=seed["options"],
                    status="active",
                    source_chunk_ids=[source_id],
                    participants=[],
                    acl=seed_acl,
                    decided_at=seed["decided_at"],
                )
                db.add(rec)
                created.append(seed["slug"])
        db.commit()

        from app.services import query_cache
        query_cache.clear()

        return {
            "status": "ok",
            "created": created,
            "upserted": upserted,
            "total_seeds": len(all_seeds),
            "demo_groups": list(group_id_by_name.keys()),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"seed-demo-data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ── Decision drift sweep ─────────────────────────────────────────────────────


@router.post("/drift-sweep/run")
def run_drift_sweep(actor: str = Depends(require_admin)):
    """Trigger the decision-drift sweep synchronously and return the result.

    Useful for demos so the presenter doesn't have to wait for the 4-hour
    cron. Walks all active decisions, computes pairwise similarity, runs an
    LLM contradiction check on the high-similarity pairs, stores any 'yes'
    verdicts as DecisionDriftAlert rows.
    """
    try:
        from app.workers.tasks import sweep_decision_drift
        # Call .run(self=...) directly to execute in-process instead of
        # queueing onto the Celery worker. Avoids the per-service env-var
        # trap that bit us earlier.
        result = sweep_decision_drift.run()
        return {"status": "ok", **(result or {})}
    except Exception as e:
        logger.error(f"drift-sweep manual trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drift-sweep/alerts")
def list_drift_alerts(
    status: str = "open",
    limit: int = 50,
    actor: str = Depends(require_admin),
):
    """List drift alerts. status ∈ {open, acknowledged, resolved, all}."""
    from app.models import DecisionDriftAlert

    db = SessionLocal()
    try:
        query = db.query(DecisionDriftAlert).order_by(DecisionDriftAlert.detected_at.desc())
        if status != "all":
            query = query.filter(DecisionDriftAlert.status == status)
        alerts = query.limit(limit).all()

        # Hydrate decisions for display
        decision_ids: set = set()
        for a in alerts:
            decision_ids.add(a.decision_a_id)
            decision_ids.add(a.decision_b_id)
        decisions = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.id.in_(list(decision_ids)))
            .all() if decision_ids else []
        )
        d_by_id = {str(d.id): d for d in decisions}

        def _decision_brief(d):
            if not d:
                return None
            return {
                "id": str(d.id),
                "decision": d.decision or "",
                "rationale": d.rationale or "",
                "decided_at": d.decided_at.isoformat() if d.decided_at else "",
                "status": d.status or "active",
            }

        return {
            "alerts": [
                {
                    "id": str(a.id),
                    "similarity": a.similarity,
                    "contradicts": a.contradicts,
                    "reasoning": a.reasoning or "",
                    "status": a.status or "open",
                    "detected_at": a.detected_at.isoformat() if a.detected_at else "",
                    "decision_a": _decision_brief(d_by_id.get(str(a.decision_a_id))),
                    "decision_b": _decision_brief(d_by_id.get(str(a.decision_b_id))),
                }
                for a in alerts
            ]
        }
    finally:
        db.close()


class DriftAlertStatusUpdate(BaseModel):
    status: str  # acknowledged | resolved | open


@router.patch("/drift-sweep/alerts/{alert_id}")
def update_drift_alert(
    alert_id: str,
    body: DriftAlertStatusUpdate,
    actor: str = Depends(require_admin),
):
    """Mark a drift alert as acknowledged or resolved."""
    from app.models import DecisionDriftAlert

    if body.status not in ("open", "acknowledged", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")

    db = SessionLocal()
    try:
        alert = db.query(DecisionDriftAlert).filter(DecisionDriftAlert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.status = body.status
        if body.status == "resolved":
            alert.resolved_at = datetime.datetime.utcnow()
            alert.resolved_by = actor
        else:
            alert.resolved_at = None
            alert.resolved_by = None
        db.commit()
        return {"status": "ok", "alert_status": alert.status}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"update_drift_alert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/drift-sweep/alerts")
def clear_drift_alerts(actor: str = Depends(require_admin)):
    """Wipe every drift alert. Used when re-running the sweep with an
    improved contradiction prompt — old false-positive alerts get cleared
    so the next sweep starts from a clean slate."""
    from app.models import DecisionDriftAlert

    db = SessionLocal()
    try:
        n = db.query(DecisionDriftAlert).delete(synchronize_session=False)
        db.commit()
        return {"status": "ok", "deleted": n}
    except Exception as e:
        db.rollback()
        logger.error(f"clear_drift_alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/decisions/cleanup-noise")
def cleanup_noise_decisions(actor: str = Depends(require_admin)):
    """Delete decision records whose source chunks all came from a noisy source.

    "Noisy" sources (calendar, clickup) generate non-decisions that get
    mis-classified by the extractor — calendar events ("Alice attends X"),
    ClickUp tutorial copy ("Click the Invite button"), task descriptions
    framed as imperatives. These same sources are now in
    SKIP_SOURCES_FOR_DECISIONS at the extractor, so future ingests stay
    clean; this endpoint cleans the back-catalog.

    Implementation: pre-build a chunk_id → source map in ONE query so we
    don't run a join per decision (the per-loop join was hitting
    InFailedSqlTransaction when a chunk_id string didn't match the UUID
    column type and the failed sub-query left the connection broken).
    """
    from app.models import Chunk, Document
    from app.services.decision_extractor import SKIP_SOURCES_FOR_DECISIONS as NOISY_SOURCES

    db = SessionLocal()
    try:
        # One pass: every chunk → its parent Document.source.
        chunk_source_rows = (
            db.query(Chunk.id, Document.source)
            .join(Document, Chunk.document_id == Document.id)
            .all()
        )
        source_by_chunk_id: dict[str, str] = {
            str(cid): (src or "") for cid, src in chunk_source_rows
        }

        all_decisions = db.query(DecisionRecord).all()
        deleted_by_source: dict[str, int] = {}
        deleted_ids: list[str] = []
        for d in all_decisions:
            chunk_ids = [str(x) for x in (d.source_chunk_ids or [])]
            if not chunk_ids:
                continue
            sources = {
                source_by_chunk_id[cid]
                for cid in chunk_ids
                if cid in source_by_chunk_id
            }
            # Only nuke if EVERY resolvable source is noisy (and at least
            # one resolved — empty set means we can't tell, so leave alone).
            if sources and sources <= NOISY_SOURCES:
                deleted_ids.append(str(d.id))
                for s in sources:
                    deleted_by_source[s] = deleted_by_source.get(s, 0) + 1
                db.delete(d)
        db.commit()
        return {
            "status": "ok",
            "deleted": len(deleted_ids),
            "deleted_by_source": deleted_by_source,
            "ids": deleted_ids,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"cleanup-noise failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# Back-compat alias — older browser snippets / docs may still use the
# original endpoint name.
@router.delete("/decisions/calendar-cleanup")
def cleanup_calendar_decisions_alias(actor: str = Depends(require_admin)):
    return cleanup_noise_decisions(actor=actor)

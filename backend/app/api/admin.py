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
def get_decisions(status: str = "all", limit: int = 50, user_email: str = ""):
    """List decisions with reversal chain info.

    The decision log is reachable from the user-facing sidebar, so ACL-filter
    by `user_email` when provided. Admins (per acl.user_can_see_chunk) bypass
    the filter automatically.
    """
    from app.core.acl import user_can_see_chunk

    db = SessionLocal()
    try:
        query = db.query(DecisionRecord).order_by(DecisionRecord.decided_at.desc())
        if status != "all":
            query = query.filter(DecisionRecord.status == status)
        decisions = query.limit(limit * 2 if user_email else limit).all()

        if user_email:
            decisions = [d for d in decisions if user_can_see_chunk(user_email, list(d.acl or []))]
        decisions = decisions[:limit]

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
        # Every Slack/ClickUp message goes through the Guardian Agent which
        # asks "has this topic already been discussed?". A high match rate
        # means the system is actively surfacing prior context — that's the
        # "deflection" the PRD wants to measure.
        from app.models import GuardianAlert
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        guardian_total = (
            db.query(GuardianAlert)
            .filter(GuardianAlert.created_at >= thirty_days_ago)
            .count()
        )
        # match_count is stored as a string ("0", "1", "2", ...). Anything
        # other than "0" or null means we found prior context.
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
        deflection_rate = (
            (guardian_with_matches / guardian_total * 100) if guardian_total > 0 else 0.0
        )

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
                "checks_total": guardian_total,
                "matches_found": guardian_with_matches,
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

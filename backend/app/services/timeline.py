import logging
import datetime

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.acl import user_can_see_chunk
from app.models import Chunk, DecisionRecord, Document
from app.services.embeddings import embed_text, search_chunks

logger = logging.getLogger(__name__)


def get_project_timeline(project_name: str, user_email: str = "", max_events: int = 10) -> list[dict]:
    query = f"{project_name} decision"
    query_vector = embed_text(query)
    results = search_chunks(query_vector, limit=20)

    filtered = []
    for r in results:
        acl = r.payload.get("acl", [])
        if not user_email or user_can_see_chunk(user_email, acl):
            filtered.append(r)

    db: Session = SessionLocal()
    try:
        events = []

        decisions = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.decision.ilike(f"%{project_name}%"))
            .order_by(DecisionRecord.decided_at.desc())
            .limit(20)
            .all()
        )

        for dec in decisions:
            events.append(
                {
                    "date": dec.decided_at.isoformat() if dec.decided_at else "",
                    "type": "decision",
                    "title": dec.decision[:80],
                    "detail": (dec.rationale or "")[:120],
                    "sort_key": dec.decided_at or datetime.datetime.min,
                }
            )

        seen_docs = set()
        for r in filtered:
            doc_id = r.payload.get("document_id")
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)

            doc = db.query(Document).filter(Document.id == doc_id).first() if doc_id else None
            title = r.payload.get("title", "Document")
            source = r.payload.get("source", "unknown")
            url = r.payload.get("url", "")
            created = doc.created_at if doc else None

            events.append(
                {
                    "date": created.isoformat() if created else "",
                    "type": f"document ({source})",
                    "title": title[:80],
                    "detail": r.payload.get("text_preview", "")[:120],
                    "url": url,
                    "sort_key": created or datetime.datetime.min,
                }
            )

        events.sort(key=lambda x: x["sort_key"], reverse=True)
        for e in events:
            e.pop("sort_key", None)

        return events[:max_events]

    finally:
        db.close()

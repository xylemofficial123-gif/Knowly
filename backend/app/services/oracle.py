import hashlib
import json
import logging
import datetime
import re
from urllib.parse import quote
from collections import Counter
from typing import Optional

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.acl import user_can_see_chunk
from app.models import AuditLog, Document
from app.services.embeddings import embed_text, search_chunks
from app.services.llm import generate
from app.services.settings_service import get_enabled_sources

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

ORACLE_PROMPT = """You are the Knowledge Oracle for a startup. Answer questions about the company's history,
decisions, and rationale using ONLY the provided source documents.

Rules:
1. Only make claims directly supported by the provided sources.
2. After every claim, add a citation tag: [SOURCE_1], [SOURCE_2], etc.
3. If the answer is not in the sources, say exactly:
   "I cannot find a record of this in the company's documented history."
4. Never use outside knowledge. Never invent rationale.
5. Be concise but complete. Plain English only.
6. If sources conflict, note the conflict and cite both.

Question: {question}
{glossary}
Sources:
{sources}

Answer:"""


def _cache_key(question: str, user_email: str) -> str:
    enabled_sources = sorted(get_enabled_sources())
    sources_hash = hashlib.md5(",".join(enabled_sources).encode()).hexdigest()[:8]
    raw = f"{question.strip().lower()}:{user_email}:{sources_hash}"
    return f"oracle:{hashlib.md5(raw.encode()).hexdigest()}"


def _keyword_overlap(query: str, text: str) -> float:
    query_words = set(query.lower().split())
    text_words = Counter(text.lower().split())
    if not query_words:
        return 0.0
    matches = sum(1 for w in query_words if text_words.get(w, 0) > 0)
    return matches / len(query_words)


def _get_freshness(doc: Optional[Document]) -> float:
    if not doc:
        return 0.5
    return doc.freshness_score if doc.freshness_score else 0.5


def retrieve_chunks(question: str, user_email: str, top_k: int = 8):
    query_vector = embed_text(question)
    raw_results = search_chunks(query_vector, limit=top_k * 3)

    enabled_sources = get_enabled_sources()

    filtered = []
    for r in raw_results:
        # Check ACL
        acl = r.payload.get("acl", [])
        if not user_can_see_chunk(user_email, acl):
            continue
        
        # Check if source is enabled
        source = r.payload.get("source", "unknown")
        if source not in enabled_sources:
            continue
            
        filtered.append(r)

    scored = []
    for r in filtered:
        text_preview = r.payload.get("text_preview", "")
        kw_score = _keyword_overlap(question, text_preview)
        combined = 0.7 * r.score + 0.3 * kw_score
        # Version awareness: deprioritize draft documents
        doc_status = r.payload.get("doc_status", "unknown")
        if doc_status == "draft":
            combined *= 0.6
        elif doc_status == "in_review":
            combined *= 0.85
        scored.append((r, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def synthesise_answer(question: str, chunks_with_scores: list) -> dict:
    if not chunks_with_scores:
        from app.services.settings_service import get_enabled_sources
        enabled = get_enabled_sources()
        # Filter out 'upload' which is always present
        active_tech_sources = [s for s in enabled if s != "upload"]
        
        if not active_tech_sources:
            msg = "All knowledge ingestion sources are currently disabled. Please enable them in the 'Ingest Sources' settings to allow research across your company's platforms."
        else:
            msg = "I could not find any documented records in the currently enabled sources that address your query. You may need to refine your question or ensure the relevant documents have been ingested."
            
        return {
            "answer": msg,
            "citations": [],
            "chunks_used": [],
        }

    sources_text = ""
    citation_map = {}
    db: Session = SessionLocal()

    try:
        for i, (chunk, score) in enumerate(chunks_with_scores):
            label = f"SOURCE_{i + 1}"
            text_preview = chunk.payload.get("text_preview", "")
            source = chunk.payload.get("source", "unknown")
            url = chunk.payload.get("url", "")
            title = chunk.payload.get("title", "")
            source_id = chunk.payload.get("source_id", "")
            doc_id = chunk.payload.get("document_id")

            # Backward compatibility: old upload rows may have empty URL.
            if source == "upload" and not url and source_id:
                url = f"{settings.BACKEND_URL}/api/ingest/uploaded/{quote(source_id, safe='')}"

            freshness = 0.5
            if doc_id:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                freshness = _get_freshness(doc)

            sources_text += f"[{label}] (source: {source}, title: {title})\n{text_preview}\n\n"

            # Pull the first inline [mm:ss] marker out of meet chunks so the
            # citation card can say "Standup 14/02 at 14:32".
            meet_ts = None
            if source == "meet":
                m = re.search(r"\[(\d{1,2}(?::\d{2}){1,2})\]", text_preview or "")
                meet_ts = m.group(1) if m else None
            display = title or f"{source} document"
            if meet_ts:
                display = f"{display} at {meet_ts}"

            citation_map[label] = {
                "url": url,
                "source": source,
                "display": display,
                "timestamp": meet_ts,
                "excerpt": text_preview[:300],
                "freshness": freshness,
                "score": round(score, 3),
            }
    finally:
        db.close()

    # Acronym buster — auto-define internal jargon mentioned in the question.
    glossary_section = ""
    try:
        from app.services.acronym_buster import glossary_for_query
        glossary = glossary_for_query(question)
        if glossary:
            lines = ["", "Glossary (use these definitions when discussing the terms):"]
            for term, definition in glossary.items():
                lines.append(f"- {term}: {definition}")
            glossary_section = "\n".join(lines) + "\n"
    except Exception as e:
        logger.debug(f"Glossary lookup skipped: {e}")

    prompt = ORACLE_PROMPT.format(question=question, sources=sources_text, glossary=glossary_section)

    answer_text = generate(prompt)

    citations = []
    used_sources = set(re.findall(r"\[SOURCE_(\d+)\]", answer_text))
    for num in sorted(used_sources, key=int):
        label = f"SOURCE_{num}"
        if label in citation_map:
            citations.append(citation_map[label])

    chunk_ids = [str(c.id) for c, _ in chunks_with_scores]

    return {
        "answer": answer_text,
        "citations": citations,
        "chunks_used": chunk_ids,
    }


def ask_oracle(question: str, user_email: str) -> dict:
    cache_key = _cache_key(question, user_email)
    cached = redis_client.get(cache_key)
    if cached:
        logger.info(f"Cache hit for query: {question[:50]}...")
        return json.loads(cached)

    chunks_with_scores = retrieve_chunks(question, user_email)
    result = synthesise_answer(question, chunks_with_scores)

    db: Session = SessionLocal()
    try:
        log = AuditLog(
            user_email=user_email,
            query=question,
            chunks_returned=json.dumps(result["chunks_used"]),
            result_count=str(len(result["citations"])),
            timestamp=datetime.datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write audit log: {e}")
    finally:
        db.close()

    try:
        redis_client.setex(cache_key, 86400, json.dumps(result))
    except Exception as e:
        logger.warning(f"Failed to cache result: {e}")

    return result

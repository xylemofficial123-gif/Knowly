import hashlib
import json
import logging
import datetime
import re
from collections import Counter

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.acl import user_can_see_chunk
from app.models import AuditLog, Document
from app.services.embeddings import embed_text, search_chunks
from app.services.llm import generate

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

Sources:
{sources}

Answer:"""


def _cache_key(question: str, user_email: str) -> str:
    raw = f"{question.strip().lower()}:{user_email}"
    return f"oracle:{hashlib.md5(raw.encode()).hexdigest()}"


def _keyword_overlap(query: str, text: str) -> float:
    query_words = set(query.lower().split())
    text_words = Counter(text.lower().split())
    if not query_words:
        return 0.0
    matches = sum(1 for w in query_words if text_words.get(w, 0) > 0)
    return matches / len(query_words)


def _get_freshness(doc: Document | None) -> float:
    if not doc:
        return 0.5
    return doc.freshness_score if doc.freshness_score else 0.5


def retrieve_chunks(question: str, user_email: str, top_k: int = 8):
    query_vector = embed_text(question)
    raw_results = search_chunks(query_vector, limit=top_k * 3)

    filtered = []
    for r in raw_results:
        acl = r.payload.get("acl", [])
        if user_can_see_chunk(user_email, acl):
            filtered.append(r)

    scored = []
    for r in filtered:
        text_preview = r.payload.get("text_preview", "")
        kw_score = _keyword_overlap(question, text_preview)
        combined = 0.7 * r.score + 0.3 * kw_score
        scored.append((r, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def synthesise_answer(question: str, chunks_with_scores: list) -> dict:
    if not chunks_with_scores:
        return {
            "answer": "I cannot find a record of this in the company's documented history.",
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
            doc_id = chunk.payload.get("document_id")

            freshness = 0.5
            if doc_id:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                freshness = _get_freshness(doc)

            sources_text += f"[{label}] (source: {source}, title: {title})\n{text_preview}\n\n"

            citation_map[label] = {
                "url": url,
                "source": source,
                "display": title or f"{source} document",
                "excerpt": text_preview[:300],
                "freshness": freshness,
                "score": round(score, 3),
            }
    finally:
        db.close()

    prompt = ORACLE_PROMPT.format(question=question, sources=sources_text)

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

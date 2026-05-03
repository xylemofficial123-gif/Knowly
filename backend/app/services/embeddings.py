import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.config import settings
from app.core.timezone import parse_date_from_text, parse_iso

logger = logging.getLogger(__name__)

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
)
COLLECTION = "knowledge_chunks"

# Local embedding model — no API key needed, runs on CPU
# BAAI/bge-small-en-v1.5: 384 dims, fast, good quality
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

logger.info(f"Loading embedding model: {MODEL_NAME}")
_embedding_model = TextEmbedding(model_name=MODEL_NAME)
logger.info("Embedding model loaded")


def _get_model() -> TextEmbedding:
    """Return the shared embedding model (for use in other services)."""
    return _embedding_model


def ensure_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection '{COLLECTION}' (dim={EMBEDDING_DIM})")
    else:
        # Check if existing collection has wrong dimensions — recreate if so
        info = qdrant.get_collection(COLLECTION)
        existing_dim = info.config.params.vectors.size
        if existing_dim != EMBEDDING_DIM:
            logger.warning(
                f"Collection '{COLLECTION}' has dim={existing_dim}, need {EMBEDDING_DIM}. Recreating..."
            )
            qdrant.delete_collection(COLLECTION)
            qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            logger.info(f"Recreated collection '{COLLECTION}' (dim={EMBEDDING_DIM})")


def embed_text(text: str) -> list[float]:
    text = text[:8000]
    embeddings = list(_embedding_model.embed([text]))
    return embeddings[0].tolist()


def upsert_chunk(chunk_id: str, text: str, payload: dict):
    vector = embed_text(text)
    payload["text_preview"] = text[:2000]
    payload.setdefault("feedback_score", 0.0)
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=chunk_id, vector=vector, payload=payload)],
    )
    return chunk_id


def update_chunk_feedback(chunk_ids: list[str], rating: str):
    """Adjust feedback_score on chunks based on user feedback.

    'helpful' → +0.02 per vote, 'not_helpful' → -0.02 per vote.
    Score is clamped to [-0.2, 0.2] to prevent runaway boosting.
    """
    delta = 0.02 if rating == "helpful" else -0.02

    for chunk_id in chunk_ids:
        try:
            points = qdrant.retrieve(
                collection_name=COLLECTION,
                ids=[chunk_id],
                with_payload=True,
            )
            if not points:
                continue

            current_score = points[0].payload.get("feedback_score", 0.0)
            new_score = max(-0.2, min(0.2, current_score + delta))

            qdrant.set_payload(
                collection_name=COLLECTION,
                payload={"feedback_score": new_score},
                points=[chunk_id],
            )
        except Exception as e:
            logger.debug(f"Failed to update feedback for chunk {chunk_id}: {e}")


def _get_chunk_date(payload: dict) -> Optional[datetime]:
    """Extract the best available date from a chunk's payload.

    Priority: ingested_at → date parsed from title → None
    """
    dt = parse_iso(payload.get("ingested_at", ""))
    if dt:
        return dt
    return parse_date_from_text(payload.get("title", ""))


def fetch_chunks_by_ids(ids: List[str], base_score: float = 0.65) -> list:
    """Fetch Qdrant points by id, returning ScoredPoint-like objects so they
    plug into the same downstream re-ranking pipeline as ``search_chunks``
    results. Used by the entity-graph augmentation in the Research Agent."""
    if not ids:
        return []
    try:
        records = qdrant.retrieve(
            collection_name=COLLECTION,
            ids=ids,
            with_payload=True,
        )
    except Exception as e:
        logger.warning(f"fetch_chunks_by_ids failed: {e}")
        return []

    from types import SimpleNamespace
    return [
        SimpleNamespace(id=r.id, payload=r.payload, score=base_score)
        for r in records
    ]


def search_chunks(
    query_vector: list[float],
    limit: int = 24,
    freshness_weight: float = 0.0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list:
    """Search chunks by vector similarity with optional recency boost and date filtering.

    Args:
        freshness_weight: 0.0 = pure vector, higher = more recency bias (0.0–1.0).
        date_from: ISO date string (YYYY-MM-DD) — filter out chunks older than this.
        date_to: ISO date string (YYYY-MM-DD) — filter out chunks newer than this.
    """
    # Always fetch extra to allow re-ranking (feedback scores, freshness, date filters)
    needs_postprocessing = True
    fetch_limit = limit * 4

    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=fetch_limit,
        with_payload=True,
    )
    points = results.points

    # Parse date boundaries
    dt_from = parse_iso(f"{date_from}T00:00:00Z") if date_from else None
    dt_to = parse_iso(f"{date_to}T23:59:59Z") if date_to else None

    now = datetime.now(timezone.utc)
    filtered = []

    for p in points:
        chunk_date = _get_chunk_date(p.payload)

        # Apply date range filter if specified
        if dt_from or dt_to:
            if chunk_date:
                if dt_from and chunk_date < dt_from:
                    continue
                if dt_to and chunk_date > dt_to:
                    continue
            # If no date could be extracted, keep the chunk (don't filter it out)

        # Apply freshness re-ranking
        if freshness_weight > 0 and chunk_date:
            age_hours = max((now - chunk_date).total_seconds() / 3600, 0.1)
            # Decay: 1.0 for <1h old, ~0.7 for 1 day, ~0.5 for 3 days, ~0.3 for 7 days
            freshness = 1.0 / (1.0 + (age_hours / 24) ** 0.7)
            p.score = (1 - freshness_weight) * p.score + freshness_weight * freshness

        # Apply feedback score boost/penalty
        feedback_score = p.payload.get("feedback_score", 0.0)
        if feedback_score != 0.0:
            p.score = p.score + feedback_score

        # Context optimization: boost high-value chunk types
        # summary and decision chunks surface first; calendar context penalised
        chunk_type = p.payload.get("chunk_type", "full_text")
        if chunk_type == "summary":
            p.score += 0.12
        elif chunk_type == "decision":
            p.score += 0.10
        elif chunk_type == "action_item":
            p.score += 0.05

        filtered.append(p)

    # Re-sort by adjusted score
    filtered.sort(key=lambda p: p.score, reverse=True)

    return filtered[:limit]

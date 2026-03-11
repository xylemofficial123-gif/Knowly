import logging
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.config import settings

logger = logging.getLogger(__name__)

qdrant = QdrantClient(url=settings.QDRANT_URL)
COLLECTION = "knowledge_chunks"

# Local embedding model — no API key needed, runs on CPU
# BAAI/bge-small-en-v1.5: 384 dims, fast, good quality
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

logger.info(f"Loading embedding model: {MODEL_NAME}")
_embedding_model = TextEmbedding(model_name=MODEL_NAME)
logger.info("Embedding model loaded")


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
    payload["text_preview"] = text[:500]
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=chunk_id, vector=vector, payload=payload)],
    )
    return chunk_id


def search_chunks(query_vector: list[float], limit: int = 24) -> list:
    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    return results.points

from openai import OpenAI
from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

client = OpenAI(api_key=settings.OPENAI_API_KEY)
qdrant = QdrantClient(url=settings.QDRANT_URL)
COLLECTION = 'knowledge_chunks'
EMBEDDING_DIM = 3072   # text-embedding-3-large dimension

def ensure_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
        )

def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        input=text,
        model='text-embedding-3-large'
    )
    return response.data[0].embedding

def upsert_chunk(chunk_id: str, text: str, metadata: dict):
    vector = embed_text(text)
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=chunk_id,
            vector=vector,
            payload=metadata
        )]
    )
    return chunk_id
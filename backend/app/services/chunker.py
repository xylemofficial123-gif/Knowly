import uuid
import logging
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.timezone import now_utc
from app.models import Document, Chunk
from app.services.embeddings import upsert_chunk
from app.services.entity_extractor import extract_entities

logger = logging.getLogger(__name__)


def split_into_chunks(text: str, max_tokens: int = 400, overlap: int = 40) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunk = " ".join(words[start : start + max_tokens])
        if chunk.strip():
            chunks.append(chunk)
        start += max_tokens - overlap
    return chunks


def chunk_and_store(
    source: str,
    source_id: str,
    text: str,
    url: str,
    acl: list,
    title: str = "",
    slack_user_id: str = "",
    extra_metadata: dict = None,
    chunk_type: str = "full_text",
    doc_status: str = "unknown",
):
    db: Session = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.source_id == source_id).first()
        if existing:
            existing.content = text
            existing.title = title
            existing.url = url
            existing.acl = acl
            existing.updated_at = now_utc()
            existing.doc_status = doc_status
            db.commit()
            doc_id = existing.id
            old_chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).all()
            for oc in old_chunks:
                db.delete(oc)
            db.commit()
        else:
            doc_id = uuid.uuid4()
            document = Document(
                id=doc_id,
                source=source,
                source_id=source_id,
                title=title,
                content=text,
                url=url,
                acl=acl,
                doc_status=doc_status,
            )
            db.add(document)
            db.commit()

        chunks = split_into_chunks(text)
        chunk_ids = []

        for i, chunk_text in enumerate(chunks):
            chunk_id = uuid.uuid4()
            embedding_id = str(chunk_id)

            entities = extract_entities(chunk_text)

            payload = {
                "source": source,
                "source_id": source_id,
                "document_id": str(doc_id),
                "url": url,
                "acl": acl,
                "entities": entities,
                "title": title,
                "chunk_type": chunk_type,
                "doc_status": doc_status,
                "ingested_at": now_utc().isoformat(),
            }
            if extra_metadata:
                payload.update(extra_metadata)
            upsert_chunk(embedding_id, chunk_text, payload)

            chunk = Chunk(
                id=chunk_id,
                document_id=doc_id,
                text=chunk_text,
                chunk_index=str(i),
                embedding_id=embedding_id,
                acl=acl,
                source_url=url,
                slack_user_id=slack_user_id,
                chunk_type=chunk_type,
            )
            db.add(chunk)
            chunk_ids.append(str(chunk_id))

        db.commit()
        logger.info(f"Stored {len(chunks)} chunks for document {source_id}")
        return chunk_ids

    except Exception as e:
        db.rollback()
        logger.error(f"Error in chunk_and_store for {source_id}: {e}")
        raise
    finally:
        db.close()

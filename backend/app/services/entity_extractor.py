import re
import logging

logger = logging.getLogger(__name__)


def extract_entities(text: str) -> dict:
    entities = {
        "people": [],
        "urls": [],
        "emails": [],
        "projects": [],
    }

    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    entities["emails"] = list(set(emails))

    urls = re.findall(r"https?://[^\s<>\"']+", text)
    entities["urls"] = list(set(urls))

    mentions = re.findall(r"<@([A-Z0-9]+)>", text)
    entities["people"] = list(set(mentions))

    projects = re.findall(r"(?:Project|project|PROJ)[:\s]+([A-Za-z][A-Za-z0-9\s\-]{2,30})", text)
    entities["projects"] = list(set(p.strip() for p in projects))

    return entities


def tag_all_chunks():
    from app.core.database import SessionLocal
    from app.models import Chunk

    db = SessionLocal()
    try:
        chunks = db.query(Chunk).all()
        for chunk in chunks:
            if chunk.text:
                extract_entities(chunk.text)
        logger.info(f"Tagged {len(chunks)} chunks with entities")
    finally:
        db.close()

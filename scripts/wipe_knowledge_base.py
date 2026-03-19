import sys
import os
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import SessionLocal, engine
from app.models import Base, Document, Chunk
from app.services.embeddings import qdrant, COLLECTION, ensure_collection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def wipe_data():
    # 1. Clear Postgres
    db = SessionLocal()
    try:
        logger.info("Clearing Postgres tables (chunks, documents)...")
        db.query(Chunk).delete()
        db.query(Document).delete()
        db.commit()
        logger.info("Postgres tables cleared.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear Postgres: {e}")
        return
    finally:
        db.close()

    # 2. Clear Qdrant
    try:
        logger.info(f"Recreating Qdrant collection '{COLLECTION}'...")
        qdrant.delete_collection(COLLECTION)
        ensure_collection()
        logger.info("Qdrant collection cleared and recreated.")
    except Exception as e:
        logger.error(f"Failed to clear Qdrant: {e}")

if __name__ == "__main__":
    confirm = input("This will DELETE ALL ingested documents and chunks. Are you sure? (y/N): ")
    if confirm.lower() == 'y':
        wipe_data()
        print("\nKnowledge base wiped successfully.")
    else:
        print("\nWipe cancelled.")

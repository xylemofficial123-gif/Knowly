#!/usr/bin/env python
"""Backfill all Google Drive documents into the knowledge base."""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.core.database import create_tables
    from app.services.embeddings import ensure_collection
    from app.services.drive_ingestion import ingest_all_drive

    logger.info("Initializing database tables...")
    create_tables()

    logger.info("Ensuring Qdrant collection exists...")
    ensure_collection()

    logger.info("Starting Google Drive backfill...")
    total = ingest_all_drive()
    logger.info(f"Backfill complete: {total} files ingested")


if __name__ == "__main__":
    main()

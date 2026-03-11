#!/usr/bin/env python
"""Backfill all Slack channels into the knowledge base."""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.core.database import create_tables
    from app.services.embeddings import ensure_collection
    from app.services.slack_ingestion import backfill_all_channels

    logger.info("Initializing database tables...")
    create_tables()

    logger.info("Ensuring Qdrant collection exists...")
    ensure_collection()

    logger.info("Starting Slack backfill...")
    total = backfill_all_channels()
    logger.info(f"Backfill complete: {total} messages ingested")


if __name__ == "__main__":
    main()

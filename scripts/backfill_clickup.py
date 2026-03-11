#!/usr/bin/env python
"""Backfill all ClickUp tasks into the knowledge base."""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.core.config import settings
    from app.core.database import create_tables
    from app.services.embeddings import ensure_collection
    from app.services.clickup_ingestion import ingest_all_clickup

    logger.info("Initializing database tables...")
    create_tables()

    logger.info("Ensuring Qdrant collection exists...")
    ensure_collection()

    team_id = settings.CLICKUP_TEAM_ID
    if not team_id:
        logger.error("CLICKUP_TEAM_ID not set. Set it in .env or as environment variable.")
        sys.exit(1)

    logger.info(f"Starting ClickUp backfill for team {team_id}...")
    total = ingest_all_clickup(team_id)
    logger.info(f"Backfill complete: {total} tasks ingested")


if __name__ == "__main__":
    main()

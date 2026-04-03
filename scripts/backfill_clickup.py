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

    # Prefer OAuth connection team_id, fall back to env var
    from app.core.token_store import get_connection
    conn = get_connection("clickup")
    team_id = (conn.team_id if conn else None) or settings.CLICKUP_TEAM_ID
    if not team_id:
        logger.error("No ClickUp team ID found. Connect via OAuth in the UI or set CLICKUP_TEAM_ID in .env.")
        sys.exit(1)

    logger.info(f"Starting ClickUp backfill for team {team_id}...")
    total = ingest_all_clickup(team_id)
    logger.info(f"Backfill complete: {total} tasks ingested")


if __name__ == "__main__":
    main()

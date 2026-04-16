"""Exclusion service — checks whether a source identifier is excluded (no-index zone)."""
import logging
from app.core.database import SessionLocal
from app.models import ExclusionRule

logger = logging.getLogger(__name__)

# In-memory cache to avoid DB hits on every message.  Refreshed on each sync cycle.
_cache: dict[str, set[str]] = {}


def refresh_cache():
    """Reload exclusion rules from DB into memory."""
    global _cache
    db = SessionLocal()
    try:
        rules = db.query(ExclusionRule).all()
        new_cache: dict[str, set[str]] = {}
        for r in rules:
            new_cache.setdefault(r.source_type, set()).add(r.identifier)
        _cache = new_cache
        logger.info(f"Exclusion cache refreshed: {sum(len(v) for v in _cache.values())} rules")
    except Exception as e:
        logger.warning(f"Failed to refresh exclusion cache: {e}")
    finally:
        db.close()


def is_excluded(source_type: str, identifier: str) -> bool:
    """Check if a specific source identifier is in a no-index zone.

    Args:
        source_type: "drive" | "slack" | "clickup"
        identifier:  folder ID, channel ID, space ID, etc.
    """
    # Lazy-load cache on first call
    if not _cache:
        refresh_cache()
    return identifier in _cache.get(source_type, set())


def get_excluded_ids(source_type: str) -> set[str]:
    """Return all excluded identifiers for a given source type."""
    if not _cache:
        refresh_cache()
    return _cache.get(source_type, set())

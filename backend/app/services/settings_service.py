import logging
from app.core.database import SessionLocal
from app.models import GlobalSettings

logger = logging.getLogger(__name__)

def is_source_enabled(source_name: str) -> bool:
    """
    Check if a specific ingestion source is enabled in the global settings.
    Possible sources: 'drive', 'calendar', 'slack', 'meet', 'clickup'
    """
    db = SessionLocal()
    try:
        gs = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not gs:
            # Default to True for Drive if settings haven't been initialized yet
            return source_name == "drive"
        
        enabled = source_name in (gs.enabled_sources or [])
        if not enabled:
            logger.info(f"Source '{source_name}' is currently disabled in GlobalSettings.")
        return enabled
    except Exception as e:
        logger.error(f"Error checking enabled source '{source_name}': {e}")
        return False
    finally:
        db.close()

def get_enabled_sources() -> list[str]:
    """
    Returns a list of all currently enabled ingestion sources.
    Always includes 'upload' as it's a manual source.
    """
    db = SessionLocal()
    try:
        gs = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not gs:
            return ["drive", "upload"]
        enabled = gs.enabled_sources or []
        if "upload" not in enabled:
            enabled.append("upload")
        return enabled
    except Exception as e:
        logger.error(f"Error fetching enabled sources: {e}")
        return ["drive", "upload"]
    finally:
        db.close()

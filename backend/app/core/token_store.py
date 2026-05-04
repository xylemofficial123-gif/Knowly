"""
Thin wrapper around OAuthConnection for reading/writing integration tokens.
"""
import logging
from typing import Optional

from app.core.database import SessionLocal
from app.models import OAuthConnection

logger = logging.getLogger(__name__)


def get_connection(provider: str) -> Optional[OAuthConnection]:
    db = SessionLocal()
    try:
        return db.query(OAuthConnection).filter(OAuthConnection.id == provider).first()
    except Exception as e:
        logger.error(f"token_store: failed to fetch {provider} connection: {e}")
        return None
    finally:
        db.close()


def get_latest_slack_connection(workspace_id: str = "") -> Optional[OAuthConnection]:
    """Return the most recent Slack OAuth connection.

    If workspace_id is provided, prefer a matching workspace installation.
    """
    db = SessionLocal()
    try:
        q = db.query(OAuthConnection).filter(
            OAuthConnection.id.like("slack:%")
        )
        if workspace_id:
            by_workspace = q.filter(OAuthConnection.workspace_id == workspace_id) \
                            .order_by(OAuthConnection.updated_at.desc(), OAuthConnection.connected_at.desc()) \
                            .first()
            if by_workspace:
                return by_workspace
        conn = q.order_by(OAuthConnection.updated_at.desc(), OAuthConnection.connected_at.desc()).first()
        if conn:
            return conn
        return db.query(OAuthConnection).filter(
            OAuthConnection.id == "slack"
        ).first()
    except Exception as e:
        logger.error(f"token_store: failed to fetch latest slack connection: {e}")
        return None
    finally:
        db.close()


def get_token(provider: str) -> Optional[str]:
    conn = get_connection(provider)
    return conn.access_token if conn else None


def save_connection(provider: str, access_token: str, **kwargs) -> OAuthConnection:
    """Create or update the OAuth connection row for the given provider."""
    import datetime
    db = SessionLocal()
    try:
        conn = db.query(OAuthConnection).filter(OAuthConnection.id == provider).first()
        if conn:
            conn.access_token = access_token
            conn.updated_at = datetime.datetime.utcnow()
            for k, v in kwargs.items():
                if hasattr(conn, k):
                    setattr(conn, k, v)
        else:
            conn = OAuthConnection(id=provider, access_token=access_token, **kwargs)
            db.add(conn)
        db.commit()
        db.refresh(conn)
        logger.info(f"token_store: saved {provider} connection")
        return conn
    except Exception as e:
        db.rollback()
        logger.error(f"token_store: failed to save {provider} connection: {e}")
        raise
    finally:
        db.close()


def delete_connection(provider: str) -> bool:
    db = SessionLocal()
    try:
        conn = db.query(OAuthConnection).filter(OAuthConnection.id == provider).first()
        if conn:
            db.delete(conn)
            db.commit()
            logger.info(f"token_store: deleted {provider} connection")
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"token_store: failed to delete {provider} connection: {e}")
        return False
    finally:
        db.close()

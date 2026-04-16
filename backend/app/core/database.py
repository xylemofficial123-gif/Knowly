from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.models import Base

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)


def run_migrations():
    """Apply incremental schema changes that create_all won't handle (new columns on existing tables)."""
    migrations = [
        "ALTER TABLE oauth_connections ADD COLUMN IF NOT EXISTS refresh_token TEXT",
        "ALTER TABLE oauth_connections ADD COLUMN IF NOT EXISTS connected_email VARCHAR",
        "ALTER TABLE oauth_connections ADD COLUMN IF NOT EXISTS bot_user_id VARCHAR",
        "ALTER TABLE oauth_connections ADD COLUMN IF NOT EXISTS workspace_id VARCHAR",
        "ALTER TABLE oauth_connections ADD COLUMN IF NOT EXISTS connected_by VARCHAR",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_status VARCHAR DEFAULT 'unknown'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Migration skipped: {e}")
        conn.commit()

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import SessionLocal, engine
from app.models import Base, GlobalSettings

def init_settings():
    # 1. Create tables
    Base.metadata.create_all(bind=engine)
    print("Tables created/verified.")

    # 2. Insert default settings if missing
    db = SessionLocal()
    try:
        settings = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not settings:
            settings = GlobalSettings(
                id="default",
                enabled_sources=["drive"],
                google_drive_folder_ids=[]
            )
            db.add(settings)
            db.commit()
            print("Default settings initialized (Drive enabled, others disabled).")
        else:
            print("Settings already exist.")
    finally:
        db.close()

if __name__ == "__main__":
    init_settings()

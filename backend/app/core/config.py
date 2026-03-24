import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Root of the backend folder
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/knowledge_agent"
    REDIS_URL: str = "redis://localhost:6379"
    QDRANT_URL: str = "http://localhost:6333"

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_CLIENT_SECRET: str = ""

    CLICKUP_API_KEY: str = ""
    CLICKUP_TEAM_ID: str = ""

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_TRANSCRIPTS_FOLDER_ID: str = ""
    GOOGLE_DRIVE_FOLDER_IDS: str = ""

    OPENROUTER_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    CLERK_SECRET_KEY: str = ""
    BYPASS_ACL: bool = False
    EXTRA_CORS_ORIGINS: str = ""

    NO_INDEX_CHANNEL_IDS: str = ""
    RELITIGATION_THRESHOLD: float = 0.82

    class Config:
        env_file = str(ENV_FILE)

    @property
    def no_index_channels(self) -> list[str]:
        if not self.NO_INDEX_CHANNEL_IDS:
            return []
        return [c.strip() for c in self.NO_INDEX_CHANNEL_IDS.split(",") if c.strip()]

    @property
    def google_drive_folder_ids(self) -> list[str]:
        if not self.GOOGLE_DRIVE_FOLDER_IDS:
            return []
        return [f.strip() for f in self.GOOGLE_DRIVE_FOLDER_IDS.split(",") if f.strip()]


settings = Settings()

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    QDRANT_URL: str
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str = ''
    CLERK_SECRET_KEY: str = ''
    SLACK_BOT_TOKEN: str = ''
    SLACK_SIGNING_SECRET: str = ''

    class Config:
        env_file = '.env'

settings = Settings()
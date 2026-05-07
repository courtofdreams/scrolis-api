
import logging
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    TWITTER_CUSTOMER_KEY: str
    TWITTER_SECRET_KEY: str
    TWITTER_BEARER_TOKEN: str
    TWITTER_CLIENT_SECRET: str
    TWITTER_CLIENT_ID: str
    TWITTER_REDIRECT_URI: str
    REDDIT_CLIENT_ID: str
    REDDIT_CLIENT_SECRET: str
    REDDIT_USERNAME: str
    REDDIT_PASSWORD: str
    REDDIT_REDIRECT_URI: str
    DATABASE_URL: str
    SECRET_KEY: str
    MONGO_URI: str
    class Config:
        env_file = ".env"


settings = Settings()
logging.info("[Settings] loaded successfully.")
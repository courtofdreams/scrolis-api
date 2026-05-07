import logging
import os

from service.MongoDBService import MongoDBService
from service.TwitterXAPIService import TwitterXAPIService

from config import settings
from service.AnalysisService import AnalysisService
from service.RedditService import RedditService

logger = logging.getLogger(__name__)

logger.info("Initializing services...")

twitter_api_service = TwitterXAPIService(
    customer_key=settings.TWITTER_CUSTOMER_KEY,
    secret_key=settings.TWITTER_SECRET_KEY,
    bearer_token=settings.TWITTER_BEARER_TOKEN,
    client_id=settings.TWITTER_CLIENT_ID,
    client_secret=settings.TWITTER_CLIENT_SECRET,
    redirect_uri=settings.TWITTER_REDIRECT_URI,
)

reddit_api_service = RedditService(
    client_id=settings.REDDIT_CLIENT_ID,
    client_secret=settings.REDDIT_CLIENT_SECRET,
    redirect_uri=settings.REDDIT_REDIRECT_URI,
    user_agent=os.getenv("REDDIT_USER_AGENT", "MyApp/1.0"),
)


mongo_db_service = MongoDBService(
    uri=settings.MONGO_URI
)

analysis_service = AnalysisService(openai_api_key=settings.OPENAI_API_KEY)

logger.info("Services initialized successfully.")
import logging
import os
from datetime import datetime, timedelta
from urllib import response
from api.models.requests import TwitterExchangeRequest
from config import settings
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from service.db import get_db
from service.models.authentication import SocialCredentials, User
from .security import require_login
from service.app_services import twitter_api_service

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

@router.get("/twitter/search/tweets/all")
async def search_tweets(    
    query: str,
    pagination_token: Optional[str] = None
):
    logger.info(f"Searching tweets for query: {query}")
    tweets = twitter_api_service.search_all(query, pagination_token)
    parsed_tweets = twitter_api_service.parse_tweet_data(tweets)
    meta_data = tweets["meta"]
    return {"query": query, "tweets": parsed_tweets, "meta": meta_data}


# sort_order can be 'recency' or 'relevancy'

@router.get("/twitter/search/tweets/recent",
            summary="Search Recent Tweets",
            description="Search recent tweets matching a query using Twitter X API., exclude retweets and only English language.")
async def search_recent_tweets(
    query: str,
    sort_order: str = 'recency',
    pagination_token: Optional[str] = None
):
    logger.info(f"Searching recent tweets for query: {query}")
    tweets = twitter_api_service.search_recent(query, sort_order, pagination_token)
    parsed_tweets = twitter_api_service.parse_tweet_data(tweets)
    meta_data = tweets["meta"]
    return {"query": query, "tweets": parsed_tweets, "meta": meta_data}


@router.get("/twitter/search/tweets/user_timeline/debug",
            summary="Search User Timeline Tweets",
            description="Search tweets from a specific user timeline matching a query using Twitter X API., exclude retweets and only English language.")
async def get_user_timeline_debug(
    access_token: str,
    user_id: str,
    pagination_token: Optional[str] = None
):
    tweets = twitter_api_service.get_timeline(access_token, user_id, pagination_token)
    with open("tweets.json", "w") as file:
        file.write(str(tweets))
    parsed_tweets = twitter_api_service.parse_tweet_data(tweets)
    meta_data = tweets["meta"]
    return {"tweets": parsed_tweets, "meta": meta_data}

@router.get("/twitter/search/tweets/user_timeline/{user_id}",
            summary="Search User Timeline Tweets",
            description="Search tweets from a specific user timeline matching a query using Twitter X API., exclude retweets and only English language.")
async def get_user_timeline(
    user_id: str,
    pagination_token: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    access_token = credentials.credentials
    tweets = twitter_api_service.get_timeline(access_token, user_id, pagination_token)
    parsed_tweets = twitter_api_service.parse_tweet_data(tweets)
    meta_data = tweets["meta"]
    return {"tweets": parsed_tweets, "meta": meta_data}

@router.post("/twitter/auth/exchange",
            summary="Exchange Authorization Code for Access Token",
            description="Exchange the authorization code for an access token.")
async def exchange_token(
    payload: TwitterExchangeRequest,
    current_user: User = Depends(require_login),
    db = Depends(get_db),
):
    tokens = twitter_api_service.exchange_code_for_token(payload.callback_url, payload.code_verifier, payload.code_challenge)
    if "error" in tokens:
        raise HTTPException(status_code=400, detail="Twitter token exchange failed")

    access_token = tokens.get("access_token")
    refresh_access_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="Twitter access token was not returned")

    twitter_user_info = twitter_api_service.get_user_info(access_token)
    twitter_user_data = getattr(twitter_user_info, "data", twitter_user_info)
    twitter_user_id = None

    if isinstance(twitter_user_data, dict):
        twitter_user_id = twitter_user_data.get("id")
    else:
        twitter_user_id = getattr(twitter_user_data, "id", None)

    social_credentials = (
        db.query(SocialCredentials)
        .filter(SocialCredentials.user_id == current_user.id)
        .first()
    )

    if not social_credentials:
        social_credentials = SocialCredentials(user_id=current_user.id)

    social_credentials.twitter_access_token = access_token
    social_credentials.twitter_refresh_token = refresh_access_token
    social_credentials.twitter_user_id = twitter_user_id
    social_credentials.twitter_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    db.add(social_credentials)
    db.commit()

    return {
        "access_token": access_token,
        "twitter_user_info": twitter_user_info,
    }

@router.get("/twitter/auth/refresh", summary="Refresh Access Token", description="Refresh the access token using the refresh token.")
async def refresh_access_token(
    refresh_token: str
):
    token_data = twitter_api_service.refresh_access_token(refresh_token)
    
    return {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),  # may be rotated
        "token_type": token_data.get("token_type"),
        "expires_in": token_data.get("expires_in"),
        "scope": token_data.get("scope"),
    }

@router.get("/twitter/me", summary="Get Authenticated User Info", description="Get information about the authenticated user using the access token.")
async def get_authenticated_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    access_token = credentials.credentials
    response = twitter_api_service.get_user_info(access_token)
    print(f"Authenticated user info response: {response}")
    return response


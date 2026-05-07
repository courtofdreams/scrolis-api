import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from service.app_services import reddit_api_service
from service.db import get_db
from service.models.authentication import SocialCredentials, User
from .security import require_login

from api.models.requests import RedditMeRequest

router = APIRouter()
logger = logging.getLogger(__name__)
DEEP_LINK_SCHEME = "myapp"  # Replace with your app's custom URL scheme

# Temporary in-memory state store (use Redis in production)
state_store: dict[str, bool] = {}




@router.get("/reddit/search/posts", 
            summary="Search Reddit Posts",
            description="Search Reddit posts by query and return parsed results.")
async def search_reddit(    
    query: str,
    subreddit: Optional[str] = None,
    sort: str = "relevance",
    time_filter: str = "all",
    limit: int = 25,
    after: Optional[str] = None,
):
    logger.info(f"Searching reddit for query: {query}")
    reddit_data = reddit_api_service.search_posts(
        query=query,
        subreddit=subreddit,
        sort=sort,
        time_filter=time_filter,
        limit=limit,
        after=after,
    )
    if "error" in reddit_data:
        logger.error(reddit_data["error"])
        return reddit_data

    parsed_posts = reddit_api_service.parse_reddit_data(reddit_data)
    return {
        "query": query,
        "subreddit": subreddit,
        "sort": sort,
        "time_filter": time_filter,
        "limit": limit,
        "posts": parsed_posts,
        "count": len(parsed_posts),
        "raw": reddit_data,
    }



@router.get("/reddit/auth/exchange")
def reddit_login():
    """
    Called by the app to get the Reddit authorization URL.
    Returns a URL the app should open in a browser/WebView.
    """
    state = secrets.token_urlsafe(32)
    state_store[state] = True  # Mark state as valid
    return reddit_api_service.build_auth_url(state)


@router.post("/reddit/me")
def reddit_me(
    payload: RedditMeRequest,
    current_user: User = Depends(require_login),
    db=Depends(get_db),
):
    """
    Get the authenticated user's Reddit username.
    """
    print(f"Received Reddit access token: {payload.reddit_access_token}")  # Debug print statement
    
    data = reddit_api_service.get_user_info(payload.reddit_access_token)
    if "error" in data:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from Reddit")

    reddit_username = data.get("name")

    social_credentials = (
        db.query(SocialCredentials)
        .filter(SocialCredentials.user_id == current_user.id)
        .first()
    )

    if not social_credentials:
        social_credentials = SocialCredentials(user_id=current_user.id)

    social_credentials.reddit_access_token = payload.reddit_access_token
    social_credentials.reddit_refresh_token = payload.refresh_token
    social_credentials.reddit_token_expires_at = datetime.utcnow() + timedelta(seconds=payload.expires_in)
    social_credentials.reddit_username = reddit_username
    current_user.need_to_connected_social = False

    db.add(social_credentials)
    db.commit()

    return {"username": reddit_username}

@router.get("/reddit/auth/callback")
async def reddit_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: str = Query(None),
):
    """
    Reddit redirects here after user authorizes.
    Exchanges the code for access + refresh tokens,
    then deep-links back to the React Native app.
    """
    if error:
        return RedirectResponse(f"{DEEP_LINK_SCHEME}://auth/error?error={error}")

    # Validate state to prevent CSRF
    if state not in state_store:
        return RedirectResponse(f"{DEEP_LINK_SCHEME}://auth/error?error=invalid_state")
    del state_store[state]

    token_data = await reddit_api_service.exchange_code_for_token(code)
    print(f"Token exchange response: {token_data}")  # Debug print statement
    if "error" in token_data:
        return RedirectResponse(f"{DEEP_LINK_SCHEME}://auth/error?error=token_exchange_failed")
    access_token = token_data.get("access_token")
    print(f"Reddit Access token obtained: {access_token}")  # Debug print statement
    
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    # Deep-link back to the React Native app with tokens
    from urllib.parse import urlencode
    params = urlencode({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
    })
    return RedirectResponse(f"{DEEP_LINK_SCHEME}://reddit-callback?{params}")

@router.get("/reddit/timeline")
async def get_best_posts(
    access_token: str,
    username: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    count: int = 0,
    limit: int = 25,
    show: Optional[str] = None,
    sr_detail: bool = False,
):
    """
    Call Reddit GET /best listing endpoint.

    Args:
        access_token: Reddit OAuth access token
        after: fullname of a thing, e.g. 't3_abc123'
        before: fullname of a thing
        count: number of items already seen
        limit: max number of items (max 100)
        show: optional 'all'
        sr_detail: whether to expand subreddit details

    Returns:
        Parsed JSON response from Reddit
    """

    if after and before:
        raise ValueError("Use only one of 'after' or 'before', not both.")
    return reddit_api_service.get_best_posts(
        access_token=access_token,
        username=username,
        after=after,
        before=before,
        count=count,
        limit=limit,
        show=show,
        sr_detail=sr_detail,
    )
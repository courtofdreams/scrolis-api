from asyncio.log import logger
import json

from api.models.requests import DifferentPerspectiveRequest
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from service.db import get_db
from service.models.authentication import SocialCredentials, User
from .security import require_login
from service.app_services import analysis_service, reddit_api_service, twitter_api_service, mongo_db_service
from datetime import datetime, timedelta


router = APIRouter()

def combine_historical_and_current_topics(historical_data, current_data):
    category_counts = {}
    total_topics = 0

    for item in historical_data:
        for category_item in item.get("categories", []):
            category = category_item.get("category", "Unknown")
            count = category_item.get("count", 0)

            category_counts[category] = category_counts.get(category, 0) + count
            total_topics += count

    current_topics = current_data.get("topicsDigest", {}).get("topics", [])

    for topic in current_topics:
        category = topic.get("category", "Unknown")

        category_counts[category] = category_counts.get(category, 0) + 1
        total_topics += 1

    if total_topics == 0:
        return []

    result = []

    for category, count in category_counts.items():
        result.append({
            "category": category,
            "count": count,
            "percentage": round((count / total_topics) * 100),
        })

    result.sort(key=lambda x: x["percentage"], reverse=True)

    return result

def get_valid_x_access_token(db, user_id):
    """Return a valid Twitter access token, refreshing it when needed."""


    credentials = (
        db.query(SocialCredentials)
        .filter(SocialCredentials.user_id == user_id)
        .first()
    )

    if not credentials:
        raise Exception("Twitter credentials not found")

    now = datetime.utcnow()


    if credentials.twitter_token_expires_at and credentials.twitter_token_expires_at > now:
        return credentials.twitter_access_token

    if not credentials.twitter_refresh_token:
        raise Exception("Twitter refresh token not found")

    token_data = twitter_api_service.refresh_access_token(credentials.twitter_refresh_token)
    if "error" in token_data:
        raise Exception(token_data["error"])

    access_token = token_data.get("access_token")
    if not access_token:
        raise Exception("Twitter access token was not returned")

    credentials.twitter_access_token = access_token
    credentials.twitter_refresh_token = token_data.get("refresh_token", credentials.twitter_refresh_token)

    expires_in = token_data.get("expires_in")
    if expires_in is not None:
        credentials.twitter_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    db.add(credentials)
    db.commit()
    db.refresh(credentials)

    return credentials.twitter_access_token


def get_valid_reddit_access_token(db, user_id):
    """Return a valid Reddit access token, refreshing it when needed."""

    credentials = (
        db.query(SocialCredentials)
        .filter(SocialCredentials.user_id == user_id)
        .first()
    )

    if not credentials:
        raise Exception("Reddit credentials not found")

    now = datetime.utcnow()

    if credentials.reddit_token_expires_at and credentials.reddit_token_expires_at > now:
        return credentials.reddit_access_token

    if not credentials.reddit_refresh_token:
        raise Exception("Reddit refresh token not found")

    token_data = reddit_api_service.refresh_access_token(credentials.reddit_refresh_token)
    if "error" in token_data:
        raise Exception(token_data["error"])

    access_token = token_data.get("access_token")
    if not access_token:
        raise Exception("Reddit access token was not returned")

    credentials.reddit_access_token = access_token
    credentials.reddit_refresh_token = token_data.get("refresh_token", credentials.reddit_refresh_token)

    expires_in = token_data.get("expires_in")
    if expires_in is not None:
        credentials.reddit_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    db.add(credentials)
    db.commit()
    db.refresh(credentials)

    return credentials.reddit_access_token

def enrich_representative_post(topic, twitter_posts, reddit_posts):
    twitter_map = {
        str(post.get("tweet_id")): post
        for post in twitter_posts
        if post.get("tweet_id")
    }

    reddit_map = {
        str(post.get("reddit_id")): post
        for post in reddit_posts
        if post.get("reddit_id")
    }

    for rep_post in topic.get("representative_posts", []):
            post_id = str(rep_post.get("post_id"))
            platform = rep_post.get("platform")

            if platform == "twitter":
                full_post = twitter_map.get(post_id)
            elif platform == "reddit":
                full_post = reddit_map.get(post_id)
            else:
                full_post = None

            if not full_post:
                rep_post["enriched"] = False
                continue

            # keep existing fields, add missing/full fields
            rep_post.update({
                "enriched": True,
                "media": full_post.get("media", []),
                "has_media": bool(full_post.get("media")),

                # author/user info
                "author": full_post.get("author"),
                "username": full_post.get("username"),
                "name": full_post.get("name"),
                "verified": full_post.get("verified"),
                "profile_image_url": full_post.get("profile_image_url"),

                # reddit-specific
                "subreddit": full_post.get("subreddit"),
                "permalink": full_post.get("permalink"),
                "title": full_post.get("title"),
                "selftext": full_post.get("selftext"),

                # engagement fields
                "ups": full_post.get("ups"),
                "num_comments": full_post.get("num_comments"),
                "upvote_ratio": full_post.get("upvote_ratio"),
                "retweet_count": full_post.get("retweet_count"),
                "reply_count": full_post.get("reply_count"),
                "like_count": full_post.get("like_count"),
                "quote_count": full_post.get("quote_count"),
                "bookmark_count": full_post.get("bookmark_count"),
                "impression_count": full_post.get("impression_count"),
            })
    
    return topic        
            
            

def enrich_representative_posts(topics_data, twitter_posts, reddit_posts):
    """
    Enrich representative_posts inside topics using full twitter/reddit post data.
    Does not remove existing representative_post fields.
    """

    twitter_map = {
        str(post.get("tweet_id")): post
        for post in twitter_posts
        if post.get("tweet_id")
    }

    reddit_map = {
        str(post.get("reddit_id")): post
        for post in reddit_posts
        if post.get("reddit_id")
    }

    for topic in topics_data.get("topics", []):
        for rep_post in topic.get("representative_posts", []):
            post_id = str(rep_post.get("post_id"))
            platform = rep_post.get("platform")

            if platform == "twitter":
                full_post = twitter_map.get(post_id)
            elif platform == "reddit":
                full_post = reddit_map.get(post_id)
            else:
                full_post = None

            if not full_post:
                rep_post["enriched"] = False
                continue

            # keep existing fields, add missing/full fields
            rep_post.update({
                "enriched": True,
                "media": full_post.get("media", []),
                "has_media": bool(full_post.get("media")),

                # author/user info
                "author": full_post.get("author"),
                "username": full_post.get("username"),
                "name": full_post.get("name"),
                "verified": full_post.get("verified"),
                "profile_image_url": full_post.get("profile_image_url"),

                # reddit-specific
                "subreddit": full_post.get("subreddit"),
                "permalink": full_post.get("permalink"),
                "title": full_post.get("title"),
                "selftext": full_post.get("selftext"),

                # engagement fields
                "ups": full_post.get("ups"),
                "num_comments": full_post.get("num_comments"),
                "upvote_ratio": full_post.get("upvote_ratio"),
                "retweet_count": full_post.get("retweet_count"),
                "reply_count": full_post.get("reply_count"),
                "like_count": full_post.get("like_count"),
                "quote_count": full_post.get("quote_count"),
                "bookmark_count": full_post.get("bookmark_count"),
                "impression_count": full_post.get("impression_count"),
            })

    return topics_data

def fetch_twitter_posts(access_token: str, user_id: str, page_count: int = 1, max_results: int = 100):
    all_posts = []
    next_token = None

    for _ in range(page_count):
        twitter_posts_response = twitter_api_service.get_timeline(
            access_token,
            user_id,
            next_token,
            max_results
        )

        all_posts.extend(twitter_api_service.parse_tweet_data(twitter_posts_response))
        next_token = twitter_posts_response.get("meta", {}).get("next_token")

        if not next_token:
            break

    return all_posts


def fetch_reddit_posts(access_token: str, username: str, page_count: int = 1, limit: int = 100):
    all_posts = []
    after = None

    for _ in range(page_count):  # Fetch specified number of pages of Reddit posts
        reddit_posts_response = reddit_api_service.get_best_posts(
            access_token,
            username,
            after=after,
            limit=limit,
        )

        all_posts.extend(reddit_api_service.parse_reddit_data(reddit_posts_response))
        after = reddit_posts_response.get("data", {}).get("after")

        if not after:
            break

    return all_posts

def search_twitter_posts(query: str):

    twitter_posts_response = twitter_api_service.search_recent(
            query,
            sort_order='relevancy',
            max_results=20
    )

    return twitter_api_service.parse_tweet_data(twitter_posts_response)

def search_reddit_posts(access_token: str, query: str):
    
    reddit_posts_response = reddit_api_service.search_posts_oauth(
        access_token=access_token,
        query=query,
        limit=25
    )

    return reddit_api_service.parse_reddit_data(reddit_posts_response)

@router.get("/analyze/topics")
def analyze_topics(
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    try:
        if current_user.need_to_connected_social:
            raise HTTPException(status_code=400, detail="User has not connected any social accounts")
        
        analyzed_data = mongo_db_service.find_daily_topic_digests_by_user_id(current_user.id)
        if analyzed_data:
            latest_digest = analyzed_data.get("topicsDigest")
            if latest_digest:
                return latest_digest
        
        social_credentials = (
            db.query(SocialCredentials)
            .filter(SocialCredentials.user_id == current_user.id)
            .first()
        )

        if not social_credentials:
            raise HTTPException(status_code=404, detail="Social credentials not found for this user")

        twitter_posts = []
        reddit_posts = []

        has_twitter_credentials = (
            social_credentials.twitter_access_token
            and social_credentials.twitter_user_id
        )
        has_reddit_credentials = (
            social_credentials.reddit_access_token
            and social_credentials.reddit_username
        )

        if not has_twitter_credentials and not has_reddit_credentials:
            raise HTTPException(status_code=400, detail="No social credentials are available for this user")

        if has_twitter_credentials:
            twitter_access_token = get_valid_x_access_token(db, current_user.id)
            twitter_posts = fetch_twitter_posts(
                twitter_access_token,
                social_credentials.twitter_user_id,
                page_count=2,  # Fetch more Twitter posts for better analysis
                max_results=100
            )
            

        if has_reddit_credentials:
            reddit_access_token = get_valid_reddit_access_token(db, current_user.id)
            reddit_posts = fetch_reddit_posts(
                reddit_access_token,
                social_credentials.reddit_username,
                page_count=2,  # Fetch more Reddit posts to compensate for lower engagement volume
                limit=100
            )
            
        result = analysis_service.analyze(twitter_posts, reddit_posts)
        enriched_result = enrich_representative_posts(result, twitter_posts, reddit_posts)
       
        for topic in enriched_result.get("topics", []):
            # with open(f"section2_data_{topic.get('topic_id')}.json", "w") as f:
            #     json.dump({"topic": topic}, f, indent=2)
            queries = analysis_service.get_query_for_topic(topic)
            query_result = []
            if queries:
                query_result =[{
                    "query_string": query,
                    "platform": topic.get("platform")
                } for query in queries.get("queries", [])]
            topic["queries"] = query_result
            
        result = mongo_db_service.create_daily_topic_digest(current_user.id, enriched_result)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save analysis result to database")
        
        return enriched_result
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/analyze/different-perspectives")
def analyze_different_perspectives(
    payload: DifferentPerspectiveRequest,
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):     
    try:
        if current_user.need_to_connected_social:
            raise HTTPException(status_code=400, detail="User has not connected any social accounts")
        
        analyzed_data = mongo_db_service.find_daily_topic_digests_by_user_id(current_user.id)
        if analyzed_data:
            existing_digest = analyzed_data.get("differentPerspectivesDigest", [])
            existing_topic = next(
                (d for d in existing_digest if d.get("topic_id") == payload.topic_id),
                None
            )
            if existing_topic:
                return existing_topic  
                
        social_credentials = (
                db.query(SocialCredentials)
                .filter(SocialCredentials.user_id == current_user.id)
                .first()
            )

        if not social_credentials:
            raise HTTPException(status_code=404, detail="Social credentials not found for this user")    
        
        twitter_posts = []
        reddit_posts = []
        for query in payload.queries:
            if query.platform == "twitter":
                twitter_posts.extend(search_twitter_posts(query.query_string))
            elif query.platform == "reddit":
                reddit_access_token = get_valid_reddit_access_token(db, current_user.id)
                reddit_posts.extend(search_reddit_posts(reddit_access_token, query.query_string))


        
        different_perspectives = analysis_service.get_different_perspectives(twitter_posts, reddit_posts, payload.keywords)

        if not different_perspectives:
            raise HTTPException(status_code=500, detail="Failed to analyze different perspectives")
        
        wandering_perspectives = different_perspectives.get("balanced", {})
        uncharted_perspectives = different_perspectives.get("other", {})
        # uncharted_perspectives = analysis_service.analyze_all(different_perspectives['unbalanced'])
        wandering_result = enrich_representative_post(wandering_perspectives, twitter_posts, reddit_posts)
        uncharted_result = enrich_representative_post(uncharted_perspectives, twitter_posts, reddit_posts)
        
        enriched_result = {
            "topic_id": payload.topic_id,
            "wandering": wandering_result,
            "uncharted": uncharted_result
        }
        
        result = mongo_db_service.update_daily_topic_digest_by_topic_id(current_user.id, enriched_result)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save analysis result to database")
        
        return enriched_result
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))  


@router.get("/analyze/historical-topics")
def analyze_historical_topics(
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    try:
        historical_data = mongo_db_service.find_user_topic_preferences_by_user_id(
            current_user.id
        )

        current_data = mongo_db_service.find_daily_topic_digests_by_user_id(
            current_user.id
        )

        combined_topics = combine_historical_and_current_topics(
            historical_data,
            current_data,
        )

        return {
            "historicalTopics": combined_topics
        }

    except Exception as e:
        print(f"Error fetching historical topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/analyze/historical-digests")
def get_historical_digests(
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    try:
        historical_digests = list(
            mongo_db_service.historical_digests.find(
                {
                    "userId": str(current_user.id)
                },
                {
                    "_id": 0
                }
            ).sort("date", -1)
        )

        return {
            "historicalDigests": historical_digests
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch historical digests: {str(e)}"
        )
from pydantic import BaseModel


class TwitterExchangeRequest(BaseModel):
    code_verifier: str
    callback_url: str
    code_challenge: str
    
    
class AnalyzeTweetsRequest(BaseModel):
    twitter_access_token: str
    twitter_user_id: str
    reddit_access_token: str 
    reddit_username: str


class SocialCredentialsRequest(BaseModel):
    twitter_access_token: str
    twitter_user_id: str
    reddit_access_token: str
    reddit_username: str
    
    
class RedditMeRequest(BaseModel):
    reddit_access_token: str  
    expires_in: int 
    refresh_token: str
    
class QueryRequest(BaseModel):  
    query_string: str
    platform: str
    
class DifferentPerspectiveRequest(BaseModel):
    topic_id: int
    keywords: list[str]
    queries: list[QueryRequest]    
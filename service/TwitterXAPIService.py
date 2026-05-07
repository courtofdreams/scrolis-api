
import base64
import json
from wsgiref import headers
import requests
import secrets
from config import settings
from xdk import Client
from xdk.oauth2_auth import OAuth2PKCEAuth

# Define query and parameters to include media details
default_query_params = {
    'max_results': 25,
    'tweet.fields': 'created_at,public_metrics,possibly_sensitive',
    'user.fields': 'username,name,verified,profile_image_url',
    'expansions': 'author_id,attachments.media_keys',
    'media.fields': 'url,preview_image_url,type,width,height'
}

scopes = ["tweet.read", "users.read", "offline.access"]

def basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(raw.encode()).decode()
    return f"Basic {encoded}"

class TwitterXAPIService:
    
    def __init__(self, customer_key, secret_key, bearer_token, client_id, client_secret, redirect_uri):
        self.customer_key = customer_key
        self.secret_key = secret_key
        self.bearer_token = bearer_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
    def parse_tweet_data(self,response):
        if "data" not in response or "includes" not in response or "users" not in response["includes"]:
            print(f"Unexpected response format: {json.dumps(response, indent=2)}")
            return []

        tweets_data = response["data"]
        users_data = response["includes"]["users"]

        user_map = {
            u["id"]: {
                "username": u["username"],
                "name": u["name"],
                "verified": u.get("verified", False),
                "profile_image_url": u.get("profile_image_url"),
            }
            for u in users_data
        }

        # added media map
        media_data = response["includes"].get("media", [])
        media_map = {
            m["media_key"]: {
                "media_key": m["media_key"],
                "type": m.get("type"),
                "url": m.get("url") or m.get("preview_image_url"),
            }
            for m in media_data
        }

        flattened_tweets = []

        for t in tweets_data:
            user = user_map.get(t["author_id"], {})
            metrics = t.get("public_metrics", {})

            # added media lookup
            media_keys = t.get("attachments", {}).get("media_keys", [])
            media = [
                media_map[key]
                for key in media_keys
                if key in media_map
            ]

            flattened_tweets.append({
                # ids
                "tweet_id": t["id"],
                "author_id": t["author_id"],

                # user
                "username": user.get("username"),
                "name": user.get("name"),
                "verified": user.get("verified", False),
                "profile_image_url": user.get("profile_image_url"),

                # content
                "created_at": t["created_at"],
                "text": t["text"],
                "possibly_sensitive": t.get("possibly_sensitive", False),

                # metrics (ALL)
                "retweet_count": metrics.get("retweet_count", 0),
                "reply_count": metrics.get("reply_count", 0),
                "like_count": metrics.get("like_count", 0),
                "quote_count": metrics.get("quote_count", 0),
                "bookmark_count": metrics.get("bookmark_count", 0),
                "impression_count": metrics.get("impression_count", 0),

                # added media
                "has_media": len(media) > 0,
                "media": media,
                "platform": "twitter"
            })

        return flattened_tweets    
        
    def search_all(self, query, pagination_token=None) -> dict:
        """
        Search tweets.
        """
        url = f"https://api.x.com/2/tweets/search/all"
        extend_query = default_query_params.copy()
        extend_query['query'] = query + ' -is:retweet lang:en'
        if(pagination_token is not None and pagination_token != ''):
            extend_query['pagination_token'] = pagination_token
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
        }
        try:
            response = requests.get(url, headers=headers, params=extend_query)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred: {e}"}
        
    def search_recent(self, query, sort_order='recency', max_results: int = 25, pagination_token=None) -> dict:
        """
        Search recent tweets.
        """
        url = f"https://api.x.com/2/tweets/search/recent"
        extend_query = default_query_params.copy()
        extend_query['query'] = query + ' -is:retweet lang:en'
        if(pagination_token is not None and pagination_token != ''):
            extend_query['pagination_token'] = pagination_token
        extend_query['sort_order'] = sort_order
        extend_query['max_results'] = max_results

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
        }
        try:
            response = requests.get(url, headers=headers, params=extend_query)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as e:
            
            print(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred: {e}"}
        
    
    ## TODO: Change to 100 results
    def get_timeline(self, access_token, user_id, pagination_token=None, max_results: int = 100) -> dict:
        """
        Get user timeline.
        """
        url = f"https://api.x.com/2/users/{user_id}/timelines/reverse_chronological"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        params = default_query_params.copy()
        params['max_results'] = max_results
        if pagination_token:
            params['pagination_token'] = pagination_token
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred: {e}"}

    
    def get_user_info(self, access_token) -> dict:
        """
        Get authenticated user info.
        """
        client = Client(access_token=access_token)
        return client.users.get_me()
    
    def exchange_code_for_token(self, callback_url: str, code_verifier: str, code_challenge: str) -> dict:
        """
        Exchange authorization code for access token.
        """
        auth = OAuth2PKCEAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scopes
        )
        try:
            auth.set_pkce_parameters(code_verifier=code_verifier, code_challenge=code_challenge)
            tokens = auth.fetch_token(authorization_response=callback_url)
            return tokens
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred: {e}"}

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Refresh access token using refresh token.
        """
        auth = OAuth2PKCEAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scopes
        )
        try:
            token_data = auth.refresh_token(refresh_token=refresh_token)
            return token_data
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred: {e}"}
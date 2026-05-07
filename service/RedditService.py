from urllib.parse import urlencode

import httpx
import requests
from html import unescape


class RedditService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, user_agent: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.user_agent = user_agent
        
    def get_reddit_media(self, data):
        media = []

        # gallery images
        gallery_items = data.get("gallery_data", {}).get("items", [])
        media_metadata = data.get("media_metadata", {})

        for item in gallery_items:
            media_id = item.get("media_id")
            meta = media_metadata.get(media_id, {})
            source = meta.get("s", {})

            if source.get("u"):
                media.append({
                    "type": "image",
                    "url": unescape(source.get("u")),
                    "width": source.get("x"),
                    "height": source.get("y"),
                    "media_id": media_id,
                })

        # single image
        if not media and data.get("post_hint") == "image":
            url = data.get("url_overridden_by_dest") or data.get("url")
            if url:
                media.append({
                    "type": "image",
                    "url": unescape(url),
                })

        # reddit video
        reddit_video = (
            data.get("secure_media", {})
            .get("reddit_video")
            if data.get("secure_media")
            else None
        )

        if reddit_video:
            media.append({
                "type": "video",
                "url": unescape(reddit_video.get("fallback_url")),
                "hls_url": unescape(reddit_video.get("hls_url", "")),
                "dash_url": unescape(reddit_video.get("dash_url", "")),
                "width": reddit_video.get("width"),
                "height": reddit_video.get("height"),
                "duration": reddit_video.get("duration"),
                "has_audio": reddit_video.get("has_audio"),
            })

        return media

    def parse_reddit_data(self, reddit_data):
        children = reddit_data.get("data", {}).get("children", [])

        posts = []

        for child in children:
            if child.get("kind") != "t3":
                continue

            data = child.get("data", {})

            # flatten + keep important fields
            post = {
                "reddit_id": data.get("id"),
                "title": data.get("title"),
                "selftext": data.get("selftext"),
                "subreddit": data.get("subreddit"),
                "author": data.get("author"),
                "created_utc": data.get("created_utc"),
                "ups": data.get("ups"),
                "num_comments": data.get("num_comments"),
                "upvote_ratio": data.get("upvote_ratio"),
                "over_18": data.get("over_18"),
                "permalink": data.get("permalink"),
                "media": self.get_reddit_media(data),
                "platform": "reddit"
            }

            posts.append(post)

        return posts      
           

    def search_posts(
        self,
        query: str,
        subreddit: str | None = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 25,
        after: str | None = None,
    ) -> dict:
        url = "https://www.reddit.com/search.json"
        headers = {
            "User-Agent": self.user_agent,
        }
        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
        }

        if subreddit:
            params["restrict_sr"] = "1"
            params["sr_detail"] = "1"
            params["q"] = f"subreddit:{subreddit} {query}"

        if after:
            params["after"] = after

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as exc:
            return {"error": f"An unexpected error occurred: {exc}"}

    def build_auth_url(self, state: str) -> dict:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "state": state,
            "redirect_uri": self.redirect_uri,
            "duration": "permanent",
            "scope": "identity read",
        }

        auth_url = f"https://www.reddit.com/api/v1/authorize?{urlencode(params)}"
        return {"auth_url": auth_url, "state": state}

    def get_user_info(self, access_token: str) -> dict:
        url = "https://oauth.reddit.com/api/v1/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": self.user_agent,
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "Failed to fetch user info from Reddit"}

        return response.json()

    async def exchange_code_for_token(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                auth=(self.client_id, self.client_secret),
                headers={"User-Agent": self.user_agent},
            )

        if response.status_code != 200:
            return {"error": "token_exchange_failed"}

        return response.json()

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh a Reddit access token using a refresh token."""
        try:
            response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(self.client_id, self.client_secret),
                headers={"User-Agent": self.user_agent},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as exc:
            return {"error": f"An unexpected error occurred: {exc}"}

    def get_best_posts(
        self,
        access_token: str,
        username: str,
        after: str | None = None,
        before: str | None = None,
        count: int = 0,
        limit: int = 25,
        show: str | None = None,
        sr_detail: bool = False,
    ) -> dict:
        if after and before:
            raise ValueError("Use only one of 'after' or 'before', not both.")

        url = "https://oauth.reddit.com/best"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": f"Scrollis/1.0 by (by /u/{username})",
        }

        params: dict[str, str | int] = {
            "count": count,
            "limit": min(limit, 100),
        }

        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if show == "all":
            params["show"] = "all"
        if sr_detail:
            params["sr_detail"] = "true"

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_posts_oauth(
        self,
        access_token: str,
        query: str,
        subreddit: str | None = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 25,
        after: str | None = None,
    ) -> dict:
        """
        OAuth-backed search using the authenticated reddit endpoint.
        Behaves like the public /search.json but calls https://oauth.reddit.com/search
        and requires a Bearer access token.
        """
        url = "https://oauth.reddit.com/search"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": self.user_agent,
        }

        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
        }

        if subreddit:
            params["restrict_sr"] = "1"
            params["sr_detail"] = "1"
            params["q"] = f"subreddit:{subreddit} {query}"

        if after:
            params["after"] = after

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            return {"error": f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            return {"error": f"Request error occurred: {req_err}"}
        except Exception as exc:
            return {"error": f"An unexpected error occurred: {exc}"}
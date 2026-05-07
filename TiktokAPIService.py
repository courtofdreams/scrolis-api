from time import time
import requests
from typing import Callable, Any

class TikTokAPIService:
    def __init__(self, client_key, client_secret):
        self.client_key = client_key
        self.client_secret = client_secret
        self.refresh_token = 0
        

    def refresh_tiktok_access_token(self) -> dict:
        payload = {
        "client_key":self.client_key,
        "client_secret": self.client_secret,
        "grant_type": "refresh_token",
        "refresh_token": self.refresh_token,
        }

        r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data=payload, timeout=30)
        r.raise_for_status()
        return r.json()
        
    def is_token_expired(self, expires_at_epoch: int, skew_seconds: int = 60) -> bool:
        # refresh a bit early to avoid race conditions
        return time.time() >= (expires_at_epoch - skew_seconds)
    

    def tiktok_api_call_with_refresh(
        self,
        method: str,
        url: str,
        *,
        get_tokens: Callable[[], dict],
        save_tokens: Callable[[dict], None],
        refresh_fn: Callable[[str], dict],
        **request_kwargs: Any,
    ):
        """
        get_tokens() -> {"access_token":..., "refresh_token":..., "expires_at": epoch_seconds}
        save_tokens(tokens) persists updated tokens
        refresh_fn(refresh_token) -> {"access_token":..., "refresh_token":..., "expires_in":...}
        """
        tokens = get_tokens()

        # Optional: proactive refresh
        if "expires_at" in tokens and self.is_token_expired(tokens["expires_at"]):
            new = refresh_fn(tokens["refresh_token"])
            updated = {
                **tokens,
                "access_token": new["access_token"],
                "refresh_token": new.get("refresh_token", tokens["refresh_token"]),
                "expires_at": int(time.time()) + int(new["expires_in"]),
            }
            save_tokens(updated)
            tokens = updated

        def do_request(access_token: str):
            headers = request_kwargs.pop("headers", {})
            headers = {**headers, "Authorization": f"Bearer {access_token}"}
            return requests.request(method, url, headers=headers, timeout=30, **request_kwargs)

        resp = do_request(tokens["access_token"])

        # Reactive refresh if unauthorized (token expired/revoked)
        if resp.status_code in (401, 403):
            new = refresh_fn(tokens["refresh_token"])
            updated = {
                **tokens,
                "access_token": new["access_token"],
                "refresh_token": new.get("refresh_token", tokens["refresh_token"]),
                "expires_at": int(time.time()) + int(new["expires_in"]),
            }
            save_tokens(updated)

            # retry ONCE
            resp = do_request(updated["access_token"])

        resp.raise_for_status()
        return resp.json()    
    
    
    def get_user_info(self, user_id: str, get_tokens: Callable[[], dict], save_tokens: Callable[[dict], None]) -> dict:
        url = f"https://open.tiktokapis.com/v2/video/list/"
        return self.tiktok_api_call_with_refresh(
            "GET",
            url,
            get_tokens=get_tokens,
            save_tokens=save_tokens,
            refresh_fn=self.refresh_tiktok_access_token,
        )    
        
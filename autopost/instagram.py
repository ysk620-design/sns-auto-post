"""Instagram API（Meta Graph API）で投稿する。標準ライブラリだけで動く。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("GRAPH_API_VERSION", "v25.0")
# 一時的なエラー（混雑・回数制限）。少し待ってやり直す
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613}


class InstagramError(RuntimeError):
    pass


class Client:
    def __init__(self, token: str, ig_user_id: str, version: str | None = None, sleep=time.sleep):
        self.token = token.strip()
        self.ig_user_id = str(ig_user_id)
        # Instagramログインのトークン（IG...）と Facebookログインのトークン（EAA...）で窓口が違う
        host = "graph.instagram.com" if self.token.startswith("IG") else "graph.facebook.com"
        self.base = f"https://{host}/{version or API_VERSION}"
        self.sleep = sleep

    def _call(self, method: str, path: str, params: dict | None = None, retries: int = 3) -> dict:
        query = urllib.parse.urlencode({**(params or {}), "access_token": self.token})
        url = f"{self.base}/{path.lstrip('/')}"
        for attempt in range(retries):
            try:
                if method == "GET":
                    req = urllib.request.Request(f"{url}?{query}")
                else:
                    req = urllib.request.Request(url, data=query.encode("utf-8"), method="POST")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                try:
                    err = json.loads(body).get("error", {})
                except ValueError:
                    err = {"message": body[:300]}
                transient = e.code >= 500 or err.get("is_transient") or err.get("code") in TRANSIENT_CODES
                if transient and attempt < retries - 1:
                    self.sleep(10 * (attempt + 1))
                    continue
                raise InstagramError(
                    f"Instagram APIエラー（HTTP {e.code}）: {err.get('message')}"
                    f"（code={err.get('code')}, subcode={err.get('error_subcode')}）"
                ) from None
            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    self.sleep(10 * (attempt + 1))
                    continue
                raise InstagramError(f"Instagramにつながりません: {e.reason}") from None
        raise InstagramError("Instagram APIの呼び出しに失敗しました")

    def create_container(self, **params) -> str:
        return self._call("POST", f"{self.ig_user_id}/media", params)["id"]

    def wait_ready(self, container_id: str, timeout: int = 300, interval: int = 5) -> None:
        waited = 0
        while True:
            status = self._call("GET", container_id, {"fields": "status_code"}).get("status_code", "")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram側で画像の処理に失敗しました（{status}）")
            if waited >= timeout:
                raise InstagramError("Instagram側の処理が時間内に終わりませんでした")
            self.sleep(interval)
            waited += interval

    def publish(self, container_id: str) -> str:
        return self._call("POST", f"{self.ig_user_id}/media_publish", {"creation_id": container_id})["id"]

    def publish_image(self, url: str, caption: str) -> str:
        cid = self.create_container(image_url=url, caption=caption)
        self.wait_ready(cid)
        return self.publish(cid)

    def publish_carousel(self, urls: list[str], caption: str) -> str:
        children = [self.create_container(image_url=u, is_carousel_item="true") for u in urls]
        for child in children:
            self.wait_ready(child)
        cid = self.create_container(media_type="CAROUSEL", children=",".join(children), caption=caption)
        self.wait_ready(cid)
        return self.publish(cid)

    def recent_media(self, limit: int = 5) -> list[dict]:
        data = self._call("GET", f"{self.ig_user_id}/media", {"fields": "id,caption,permalink,timestamp", "limit": limit})
        return data.get("data", [])

    def permalink(self, media_id: str) -> str | None:
        try:
            return self._call("GET", media_id, {"fields": "permalink"}).get("permalink")
        except InstagramError:
            return None

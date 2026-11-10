"""トークンでInstagramにつながるかを確認する（投稿はしない）。

使い方: python -m autopost.check_api
公開リポジトリのログに出るので、表示するのはプロフィールで誰でも見られる情報だけにする
（リーチや保存数などの分析の数値は表示しない）。
"""
from __future__ import annotations

import sys

from . import config
from .instagram import Client, InstagramError


def notice(title: str, message: str, level: str = "notice") -> None:
    # GitHub Actions の注釈として出す（実行結果の画面に一覧で表示される）
    print(f"::{level} title={title}::{message.replace(chr(10), ' / ')}")


def check_account(cfg: dict) -> bool:
    handle = cfg["handle"]
    token = config.get_token(cfg)
    if not token:
        notice(handle, f"トークン（{cfg.get('token_secret')}）が登録されていません", "warning")
        return False
    client = Client(token, cfg["ig_user_id"])
    try:
        profile = client._call("GET", cfg["ig_user_id"], {"fields": "username,followers_count,media_count"})
        notice(handle, f"接続OK：@{profile.get('username')}（フォロワー {profile.get('followers_count')}・"
                       f"投稿 {profile.get('media_count')}件）")
        try:
            client._call("GET", f"{cfg['ig_user_id']}/content_publishing_limit", {"fields": "quota_usage"})
            notice(handle, "投稿の権限：OK")
        except InstagramError as e:
            notice(handle, f"投稿の権限：NG（{e}）", "error")
        media = client._call("GET", f"{cfg['ig_user_id']}/media",
                             {"fields": "id,timestamp,media_type,media_product_type,caption", "limit": 30}).get("data", [])
        lines = []
        for m in media:
            kind = "リール" if m.get("media_product_type") == "REELS" else (
                "カルーセル" if m.get("media_type") == "CAROUSEL_ALBUM" else m.get("media_type"))
            first = (m.get("caption") or "").strip().splitlines()[0][:30] if m.get("caption") else ""
            lines.append(f"{m.get('timestamp', '')[:10]} {kind}「{first}」")
        notice(f"{handle} 過去の投稿（新しい順・{len(media)}件）", " / ".join(lines) or "なし")
        if media:
            try:
                client._call("GET", f"{media[0]['id']}/insights", {"metric": "reach"})
                notice(handle, "分析の権限：OK")
            except InstagramError as e:
                notice(handle, f"分析の権限：NG（{e}）", "warning")
        others = [c["handle"].lstrip("@") for c in config.load_accounts().values() if c["handle"] != handle] + ["bluebottle"]
        for other in others:
            fields = (f"business_discovery.username({other}){{username,followers_count,media_count,"
                      f"media.limit(3){{timestamp,media_type,media_product_type,like_count,comments_count}}}}")
            try:
                bd = client._call("GET", cfg["ig_user_id"], {"fields": fields}).get("business_discovery", {})
                items = bd.get("media", {}).get("data", [])
                notice(handle, f"他アカウント分析（@{other}）：OK（フォロワー {bd.get('followers_count')}・投稿 {bd.get('media_count')}件・"
                               f"直近3件のいいね {[m.get('like_count') for m in items]}・コメント {[m.get('comments_count') for m in items]}）")
            except InstagramError as e:
                notice(handle, f"他アカウント分析（@{other}）：NG（{e}）", "warning")
        return True
    except InstagramError as e:
        notice(handle, f"接続できません：{e}", "error")
        return False


def main() -> int:
    ok = all([check_account(cfg) for cfg in config.load_accounts().values() if cfg.get("enabled", True)])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""設定の読み込みと共通の定数。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9), "JST")

DEFAULT_THEME = {
    "main": "#1f2a44",  # 表紙・見出しの色
    "base": "#fbf7f0",  # 背景色
    "accent": "#e8684a",  # 強調色
    "accent_soft": "#ffb39f",  # 表紙で使う淡い強調色
    "muted": "#9aa1b0",  # ページ番号などの薄い文字
}


def now_jst() -> datetime:
    """現在の日本時間。テスト用に環境変数 AUTOPOST_NOW（ISO形式）で上書きできる。"""
    fixed = os.environ.get("AUTOPOST_NOW")
    if fixed:
        dt = datetime.fromisoformat(fixed)
        return dt.astimezone(JST) if dt.tzinfo else dt.replace(tzinfo=JST)
    return datetime.now(JST)


def accounts_dir(root: Path = ROOT) -> Path:
    return root / "accounts"


def queue_dir(root: Path = ROOT) -> Path:
    return root / "queue"


def posted_dir(root: Path = ROOT) -> Path:
    return root / "posted"


def load_accounts(root: Path = ROOT) -> dict[str, dict]:
    """accounts/*.json を読み込む。キーはハンドル名（@なし）。"""
    accounts: dict[str, dict] = {}
    for path in sorted(accounts_dir(root).glob("*.json")):
        cfg = json.loads(path.read_text(encoding="utf-8"))
        handle = cfg.get("handle") or path.stem
        if handle != path.stem:
            raise ValueError(f"{path.name}: handle（{handle}）とファイル名が一致しません")
        cfg["handle"] = handle
        cfg.setdefault("enabled", True)
        cfg.setdefault("post_hour_jst", 7)
        cfg.setdefault("post_window_hours", 3)
        cfg.setdefault("display_handle", "@" + handle)
        cfg.setdefault("series", "")
        cfg["theme"] = {**DEFAULT_THEME, **cfg.get("theme", {})}
        accounts[handle] = cfg
    return accounts


def get_token(cfg: dict) -> str | None:
    """アカウントのアクセストークン（GitHubのシークレットから環境変数で渡される）。"""
    name = cfg.get("token_secret")
    value = os.environ.get(name, "").strip() if name else ""
    return value or None

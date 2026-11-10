"""投稿データ（queue/<アカウント>/<フォルダ>/post.json）の読み込みと選び方。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config

PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass
class Post:
    folder: Path
    data: dict

    @classmethod
    def load(cls, folder: Path) -> "Post":
        folder = Path(folder)
        return cls(folder, json.loads((folder / "post.json").read_text(encoding="utf-8")))

    @property
    def id(self) -> str:
        return self.folder.name

    @property
    def account(self) -> str:
        return self.data.get("account") or self.folder.parent.name

    @property
    def date(self) -> date | None:
        try:
            return date.fromisoformat(str(self.data.get("date", "")))
        except ValueError:
            return None

    def slide_files(self) -> list[Path]:
        return sorted(self.folder.glob("slide*.jpg"))

    def render_info(self) -> dict:
        path = self.folder / "render.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def needs_render(self, account_cfg: dict) -> bool:
        """画像がまだ無いか、投稿データ・デザインが変わって作り直しが必要か。"""
        if self.render_info().get("hash") != render_hash(self.data, account_cfg):
            return True
        return len(self.slide_files()) != len(self.data.get("slides", []))


def template_fingerprint() -> str:
    """デザイン（templates.py と style.css）が変わったら作り直すための指紋。"""
    h = hashlib.sha256()
    for name in ("templates.py", "style.css"):
        h.update((PACKAGE_DIR / name).read_bytes())
    return h.hexdigest()[:12]


def render_hash(data: dict, account_cfg: dict) -> str:
    payload = {
        "slides": data.get("slides"),
        "no": data.get("no"),
        "pr": bool(data.get("pr", False)),
        "theme": account_cfg.get("theme"),
        "series": account_cfg.get("series"),
        "display_handle": account_cfg.get("display_handle"),
        "template": template_fingerprint(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def compose_caption(data: dict) -> str:
    """Instagramに載せるキャプション（PR表記・本文・ハッシュタグ）。"""
    body = str(data.get("caption", "")).strip()
    if data.get("pr"):
        body = "【PR】\n" + body
    tags = " ".join(data.get("hashtags", []))
    return f"{body}\n\n{tags}" if tags else body


def list_queue(account: str, root: Path = config.ROOT) -> list[Post]:
    folder = config.queue_dir(root) / account
    if not folder.is_dir():
        return []
    return [Post.load(p) for p in sorted(folder.iterdir()) if (p / "post.json").is_file()]


def all_queue_posts(root: Path = config.ROOT) -> list[Post]:
    return [Post.load(p.parent) for p in sorted(config.queue_dir(root).glob("*/*/post.json"))]


def next_post(account: str, today: date, root: Path = config.ROOT) -> Post | None:
    """今日投稿してよい投稿のうち、一番古いもの。"""
    for post in list_queue(account, root):
        if post.date and post.date <= today:
            return post
    return None


def posted_on(account: str, day: date, root: Path = config.ROOT) -> bool:
    folder = config.posted_dir(root) / account
    if not folder.is_dir():
        return False
    for path in folder.glob("*/published.json"):
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if info.get("posted_date") == day.isoformat():
            return True
    return False

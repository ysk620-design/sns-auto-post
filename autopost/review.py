"""Gemini に、プルリクエストの投稿をレビューさせる（再生数とフォローを最大にする観点だけで採点・直し案）。

使い方（GitHub Actions）: python -m autopost.review <出力フォルダ>（review-1.md, review-2.md… に分けて書く）
main と比べて追加・変更された投稿ごとに、画像（slideNN.jpg）・リール動画（reel.mp4 があれば）・本文を
Gemini に渡して、autopost/review_rubric.md の項目で採点させる。結果はプルリクエストにコメントで貼る。
週次投稿づくりのセッションは、このコメントを読んで、点数の低い項目から直して再プッシュする。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config, posts
from .pr_preview import changed_posts

API = "https://generativelanguage.googleapis.com/v1beta"
MODELS = ["gemini-flash-latest", "gemini-3-flash", "gemini-2.5-flash", "gemini-pro-latest"]
RUBRIC = Path(__file__).with_name("review_rubric.md")
MAX_POSTS = 30
MAX_VIDEO_BYTES = 15 * 1024 * 1024


def _call(model: str, body: dict, key: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except ValueError:
            return e.code, {}
    except urllib.error.URLError:
        return 0, {}


def target_text(post: posts.Post, cfg: dict) -> str:
    d = post.data
    kind = d.get("type", "carousel")
    lines = [f"アカウント: @{cfg['handle']}（{cfg.get('name', '')}）",
             f"投稿の種類: {kind}" + (f"（{d.get('post_hour_jst')}時台に投稿）" if d.get("post_hour_jst") is not None else ""),
             f"タイトル: {d.get('title', '')}", "", "キャプション:", posts.compose_caption(d)]
    if (post.folder / "reel.mp4").exists():
        lines += ["", "リール動画（reel.mp4）も付けています。音も含めて見てください。"]
    else:
        lines += ["", "画像は縦長の1枚で、BGM付きの約7秒のリールとして投稿されます（読み上げはありません）。"
                  if kind == "reel_only" else "画像はカルーセルのスライドです。"]
    return "\n".join(lines)


def review_post(post: posts.Post, cfg: dict, key: str) -> tuple[str, str]:
    parts = [{"text": RUBRIC.read_text(encoding="utf-8")}, {"text": "## 対象\n" + target_text(post, cfg)}]
    for f in post.slide_files()[:10]:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(f.read_bytes()).decode()}})
    reel = post.folder / "reel.mp4"
    if reel.exists() and reel.stat().st_size <= MAX_VIDEO_BYTES:
        parts.append({"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(reel.read_bytes()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"temperature": 0.6}}
    for model in MODELS:
        for attempt in range(2):
            code, data = _call(model, body, key)
            if code == 200:
                text = "".join(p.get("text", "") for c in data.get("candidates", [])
                               for p in c.get("content", {}).get("parts", []))
                if text.strip():
                    return model, text.strip()
            if code in (429, 500, 503, 0) and attempt == 0:
                time.sleep(10)
                continue
            break
    return "", "（レビューを取得できませんでした）"


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY が無いので、レビューはしません", file=sys.stderr)
        return 0
    accounts = config.load_accounts()
    items = [p for p in changed_posts() if p.slide_files() and p.account in accounts]
    if not items:
        return 0
    items.sort(key=lambda p: (str(p.data.get("date")), p.account, p.data.get("post_hour_jst") or 0))
    head = ["<!-- gemini-review -->", "## 🔍 Geminiのレビュー（再生数とフォローを最大にする観点）", "",
            "週次投稿づくりのClaudeが、このレビューを読んで点数の低い項目から直します。", ""]
    blocks = []
    for post in items[:MAX_POSTS]:
        model, text = review_post(post, accounts[post.account], key)
        rel = post.folder.relative_to(config.ROOT).as_posix()
        blocks.append("\n".join([
            f"<details><summary><b>{post.account} {post.data.get('date')} ｜ {post.data.get('title', '')}</b></summary>",
            "", f"`{rel}`（{model or '—'}）", "", text[:12000], "", "</details>", ""]))
        print(f"🔍 {rel}: {model or '失敗'}", file=sys.stderr)
    if len(items) > MAX_POSTS:
        blocks.append(f"※ {len(items) - MAX_POSTS}件は数が多いので省略しました")
    # GitHub のコメントは1つ6.5万文字までなので、分けて書く
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)
    pages, cur = [], "\n".join(head)
    for b in blocks:
        if len(cur) + len(b) > 60000:
            pages.append(cur)
            cur = "<!-- gemini-review -->\n## 🔍 Geminiのレビュー（つづき）\n\n"
        cur += b + "\n"
    pages.append(cur)
    for i, text in enumerate(pages, 1):
        (out_dir / f"review-{i}.md").write_text(text, encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())

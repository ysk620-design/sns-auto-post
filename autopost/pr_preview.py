"""プルリクエストに貼る「投稿プレビュー」（画像の一覧と本文）を作る。

使い方: python -m autopost.pr_preview <画像を含むコミットのSHA> > preview.md
main ブランチと比べて、追加・変更された投稿だけを載せる（事前に git fetch origin main しておく）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date

from . import config, posts

WEEKDAYS = "月火水木金土日"


def _blob(ref: str, path: str) -> str | None:
    r = subprocess.run(["git", "rev-parse", f"{ref}:{path}"], cwd=config.ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def changed_posts() -> list[posts.Post]:
    out = []
    for post in posts.all_queue_posts():
        rel = (post.folder / "post.json").relative_to(config.ROOT).as_posix()
        if _blob("HEAD", rel) != _blob("origin/main", rel):
            out.append(post)
    return out


def build(sha: str, slug: str) -> str:
    items = changed_posts()
    if not items:
        return ""
    accounts = config.load_accounts()
    items.sort(key=lambda p: (str(p.data.get("date")), p.account))
    lines = ["## 📱 投稿プレビュー", "", "画像は全スライドの一覧です。問題なければ、このプルリクエストをマージしてください。", ""]
    for post in items:
        d = post.date
        day = f"{d.month}/{d.day}（{WEEKDAYS[d.weekday()]}）" if isinstance(d, date) else str(post.data.get("date"))
        cfg = accounts.get(post.account, {})
        series = cfg.get("series", "")
        no = post.data.get("no")
        head = f"### {day} @{post.account}"
        if series and no:
            head += f"　{series} #{no}"
        if post.data.get("title"):
            head += f"「{post.data['title']}」"
        rel = post.folder.relative_to(config.ROOT).as_posix()
        lines += [head, ""]
        if post.data.get("reel_title"):
            lines += [f"リール上部のタイトル：「{post.data['reel_title']}」", ""]
        lines += [f"![{post.id}](https://raw.githubusercontent.com/{slug}/{sha}/{rel}/preview.jpg)", ""]
        if (post.folder / "reel.mp4").exists():
            lines += [f"🎬 [読み上げ付きリールを再生する](https://github.com/{slug}/blob/{sha}/{rel}/reel.mp4)"
                      "（読み方がおかしくないか、音を出して確認してください）", ""]
        lines += ["<details><summary>キャプション</summary>", "", "```", posts.compose_caption(post.data), "```", "",
                  "</details>", ""]
        if post.data.get("review_notes"):
            notes = str(post.data["review_notes"]).replace("\n", "\n> ")
            lines += [f"> **確認してほしい点**：{notes}", ""]
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("使い方: python -m autopost.pr_preview <コミットSHA>", file=sys.stderr)
        return 2
    slug = os.environ.get("GITHUB_REPOSITORY", "ysk620-design/sns-auto-post")
    sys.stdout.write(build(sys.argv[1], slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())

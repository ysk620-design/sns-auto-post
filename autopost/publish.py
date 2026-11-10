"""キューから今日の投稿を選んで Instagram に投稿する（GitHub Actions から毎時実行）。

使い方:
  python -m autopost.publish check   # 今投稿するものがあるか（GitHub Actions の出力に書く）
  python -m autopost.publish run     # 投稿する
オプション:
  --account eigo_1phrase  そのアカウントだけ
  --force                 時間帯と「今日はもう投稿済み」のチェックを飛ばして今すぐ投稿
  --dry-run               投稿はせず、何を投稿するかだけ表示
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config, posts
from .instagram import Client, InstagramError

ROOT = config.ROOT


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def repo_slug() -> str:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", git("remote", "get-url", "origin"))
    if not m:
        raise RuntimeError("GitHubのリポジトリ名がわかりません")
    return m.group(1)


def set_output(**values) -> None:
    lines = [f"{k}={v}" for k, v in values.items()]
    print("\n".join(lines))
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def find_due(accounts: dict, now, only: str = "", force: bool = False, dry_run: bool = False, root: Path = ROOT):
    """今投稿すべき (アカウント設定, 投稿) のリスト。"""
    today = now.date()
    due = []
    for handle, cfg in accounts.items():
        if only and handle != only:
            continue
        if not cfg.get("enabled", True):
            print(f"・{handle}: 停止中（enabled が false）")
            continue
        if not dry_run and not config.get_token(cfg):
            print(f"・{handle}: トークン（{cfg.get('token_secret')}）が未登録なのでスキップ")
            continue
        if not (force or dry_run):
            start, window = int(cfg["post_hour_jst"]), int(cfg["post_window_hours"])
            if not start <= now.hour < start + window:
                print(f"・{handle}: 投稿時間外（{start}時〜{start + window}時）")
                continue
            if posts.posted_on(handle, today, root):
                print(f"・{handle}: 今日はもう投稿済み")
                continue
        post = posts.next_post(handle, today, root)
        if post is None:
            print(f"・{handle}: 今日投稿できるデータがキューにありません")
            continue
        due.append((cfg, post))
    return due


def ensure_rendered(cfg: dict, post: posts.Post) -> posts.Post:
    if post.needs_render(cfg):
        from . import render

        problems = asyncio.run(render.render_posts([(post.folder, post.data, cfg)]))
        if problems:
            raise RuntimeError("画像を作れませんでした: " + " / ".join(problems))
        post = posts.Post.load(post.folder)
    return post


def commit_and_push(message: str) -> None:
    git("add", "-A", "queue", "posted")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        git("commit", "-m", message)
    for attempt in range(5):
        if subprocess.run(["git", "push"], cwd=ROOT, capture_output=True).returncode == 0:
            return
        subprocess.run(["git", "pull", "--rebase"], cwd=ROOT, capture_output=True)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("GitHubへの保存（git push）に失敗しました")


def wait_reachable(url: str, timeout: int = 120) -> None:
    """GitHubに置いた画像がネットから見えるようになるまで待つ。"""
    deadline = time.time() + timeout
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as resp:
                if resp.status == 200:
                    return
        except urllib.error.URLError:
            pass
        if time.time() > deadline:
            raise RuntimeError(f"画像のURLにアクセスできません: {url}")
        time.sleep(5)


def publish_one(cfg: dict, post: posts.Post, now, dry_run: bool = False) -> dict | None:
    handle = cfg["handle"]
    caption = posts.compose_caption(post.data)
    if dry_run:
        state = "作成済み" if not post.needs_render(cfg) else "未作成（投稿時に作ります）"
        print(f"\n▶ {handle}: {post.id}（予定日 {post.data.get('date')}）")
        print(f"  画像: {len(post.data.get('slides', []))}枚・{state}")
        print("  キャプション:\n" + "\n".join("    " + line for line in caption.splitlines()))
        return None

    post = ensure_rendered(cfg, post)
    files = post.slide_files()
    commit_and_push(f"画像を準備: {handle}/{post.id}")
    sha = git("rev-parse", "HEAD")
    slug = repo_slug()
    urls = [f"https://raw.githubusercontent.com/{slug}/{sha}/{f.relative_to(ROOT).as_posix()}" for f in files]
    for url in urls:
        wait_reachable(url)

    client = Client(config.get_token(cfg), cfg["ig_user_id"])
    # 前回の実行で投稿だけ成功していた場合に、二重投稿しないための確認
    existing = next((m for m in client.recent_media() if (m.get("caption") or "").strip() == caption.strip()), None)
    if existing:
        print(f"・{handle}: 同じ投稿がすでにInstagramにあるので、記録だけ更新します")
        media_id, permalink = existing["id"], existing.get("permalink")
    else:
        media_id = client.publish_image(urls[0], caption) if len(urls) == 1 else client.publish_carousel(urls, caption)
        permalink = client.permalink(media_id)

    record = {
        "media_id": media_id,
        "permalink": permalink,
        "posted_at": config.now_jst().isoformat(timespec="seconds"),
        "posted_date": now.date().isoformat(),
        "image_commit": sha,
    }
    dest = config.posted_dir(ROOT) / handle / post.id
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(post.folder), str(dest))
    (dest / "published.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commit_and_push(f"投稿しました: {handle}/{post.id}")
    print(f"✅ {handle}: 投稿しました {permalink or media_id}")
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Instagramに投稿する")
    ap.add_argument("command", choices=["check", "run"])
    ap.add_argument("--account", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    accounts = config.load_accounts()
    now = config.now_jst()
    print(f"日本時間 {now:%Y-%m-%d %H:%M}")
    due = find_due(accounts, now, args.account.strip(), args.force, args.dry_run)

    if args.command == "check":
        needs_render = any(post.needs_render(cfg) for cfg, post in due) and not args.dry_run
        set_output(
            due=str(bool(due)).lower(),
            needs_render=str(needs_render).lower(),
            accounts=",".join(cfg["handle"] for cfg, _ in due),
        )
        return 0

    if not due:
        print("今は投稿するものがありません")
        return 0
    if os.environ.get("GITHUB_ACTIONS") == "true":
        git("config", "user.name", "github-actions[bot]")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    failures = 0
    for cfg, post in due:
        try:
            publish_one(cfg, post, now, args.dry_run)
        except (InstagramError, RuntimeError, subprocess.CalledProcessError) as e:
            print(f"❌ {cfg['handle']}: {e}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

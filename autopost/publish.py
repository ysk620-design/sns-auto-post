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
import tempfile
import time
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

from . import config, posts, story
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


def reel_delayed(cfg: dict) -> bool:
    """リールをカルーセルとは別の日・時間に投稿する設定か（reel.delay_days / reel.post_hour_jst）。"""
    r = cfg.get("reel") or {}
    return bool(r.get("enabled")) and (int(r.get("delay_days", 0)) > 0 or "post_hour_jst" in r)


def _published(handle: str, root: Path):
    folder = config.posted_dir(root) / handle
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("*/published.json")):
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue


def find_due_reels(accounts: dict, now, only: str = "", force: bool = False, dry_run: bool = False,
                   root: Path = ROOT):
    """今投稿すべき「あとから出すリール」の (アカウント設定, 投稿済みフォルダ) のリスト（1アカウント1本まで）。"""
    today = now.date()
    due = []
    for handle, cfg in accounts.items():
        if only and handle != only:
            continue
        if not cfg.get("enabled", True) or not (cfg.get("reel") or {}).get("enabled"):
            continue
        if not dry_run and not config.get_token(cfg):
            continue
        r = cfg["reel"]
        if not (force or dry_run):
            start = int(r.get("post_hour_jst", cfg["post_hour_jst"]))
            window = int(r.get("post_window_hours", cfg["post_window_hours"]))
            if not start <= now.hour < start + window:
                continue
        items = list(_published(handle, root))
        if not force and any(info.get("reel_posted_date") == today.isoformat() for _, info in items):
            print(f"・{handle}: 今日のリールはもう投稿済み")
            continue
        pending = [path for path, info in items if info.get("reel_status") == "pending"
                   and str(info.get("reel_due", "")) <= today.isoformat()]
        if pending:
            due.append((cfg, pending[0].parent))
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
        count = len(post.slide_files()) if story.is_story(post.data) else len(post.data.get("slides", []))
        print(f"  画像: {count}枚・{state}")
        if story.is_story(post.data):
            if story.reel_wanted(post.data, cfg):
                print(f"  リール: 読み上げ付き・{'あとで別に投稿' if reel_delayed(cfg) else '続けて投稿'}")
        elif (cfg.get("reel") or {}).get("enabled") and post.data.get("reel", True):
            from . import reel

            when = "あとで別に投稿" if reel_delayed(cfg) else "続けて投稿"
            print(f"  リール: あり・{when}（上部タイトル「{post.data.get('reel_title') or reel.default_title(post.data)}」）")
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
    recent = client.recent_media()

    def already_posted(media_types: set[str], text: str = caption) -> dict | None:
        # 前回の実行で投稿だけ成功していた場合に、二重投稿しないための確認
        return next((m for m in recent if m.get("media_type") in media_types
                     and (m.get("caption") or "").strip() == text.strip()), None)

    existing = already_posted({"CAROUSEL_ALBUM", "IMAGE"})
    if existing:
        print(f"・{handle}: 同じ投稿がすでにInstagramにあるので、記録だけ更新します")
        media_id, permalink = existing["id"], existing.get("permalink")
    else:
        media_id = client.publish_image(urls[0], caption) if len(urls) == 1 else client.publish_carousel(urls, caption)
        permalink = client.permalink(media_id)
    print(f"✅ {handle}: 投稿しました {permalink or media_id}")

    record = {
        "media_id": media_id,
        "permalink": permalink,
        "posted_at": config.now_jst().isoformat(timespec="seconds"),
        "posted_date": now.date().isoformat(),
        "image_commit": sha,
    }

    reel_error = None
    reel_cfg = cfg.get("reel") or {}
    wants_reel = bool(reel_cfg.get("enabled")) and post.data.get("reel", True) is not False
    if wants_reel and reel_delayed(cfg):
        # リールは別の日・時間に、あとから投稿する（find_due_reels が拾う）
        record["reel_status"] = "pending"
        record["reel_due"] = (now.date() + timedelta(days=int(reel_cfg.get("delay_days", 0)))).isoformat()
        print(f"・{handle}: リールは {record['reel_due']} の {reel_cfg.get('post_hour_jst', cfg['post_hour_jst'])}時台に投稿予定")
    elif wants_reel:
        try:
            reel_caption = posts.compose_reel_caption(post.data, cfg)
            record.update(publish_reel(client, cfg, post, reel_caption,
                                       already_posted({"VIDEO", "REELS"}, reel_caption)))
            print(f"🎬 {handle}: リールを投稿しました {record.get('reel_permalink') or record.get('reel_media_id')}")
        except Exception as e:  # リールが失敗しても、カルーセルの記録は残す
            reel_error = str(e)
            record["reel_error"] = reel_error

    dest = config.posted_dir(ROOT) / handle / post.id
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(post.folder), str(dest))
    (dest / "published.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commit_and_push(f"投稿しました: {handle}/{post.id}")
    if reel_error:
        raise RuntimeError(f"カルーセルは投稿できましたが、リールの投稿に失敗しました: {reel_error}")
    return record


def publish_reel(client: Client, cfg: dict, post: posts.Post, caption: str, existing: dict | None) -> dict:
    """スライドからリール動画を作って投稿する（グリッドに重複しないよう、リールタブだけに出す）。"""
    if existing:
        return {"reel_media_id": existing["id"], "reel_permalink": existing.get("permalink")}
    from . import reel

    reel_cfg = cfg.get("reel") or {}
    prebuilt = story.is_story(post.data)
    if prebuilt:
        # ストーリー形式は、画像と一緒に作ってある読み上げ付きの動画（reel.mp4）をそのまま使う
        video = post.folder / "reel.mp4"
        if not video.exists():
            raise RuntimeError("リール動画（reel.mp4）がありません")
    else:
        title = post.data.get("reel_title") or reel.default_title(post.data)
        video = Path(tempfile.mkdtemp()) / "reel.mp4"
        reel.make_reel(post.folder, title, reel_cfg.get("subtitle", ""), cfg["theme"], video)
    share = bool(reel_cfg.get("share_to_feed", False))
    try:
        reel_id = client.publish_reel(video, caption, share)
    except InstagramError as e:
        # 直接アップロードがうまくいかないときは、動画をGitHubに置いてURLで渡す
        print(f"・直接アップロードに失敗したので、URL方式で再試行します（{e}）")
        if not prebuilt:
            shutil.copy(video, post.folder / "reel.mp4")
        commit_and_push(f"リール動画を準備: {cfg['handle']}/{post.id}")
        url = f"https://raw.githubusercontent.com/{repo_slug()}/{git('rev-parse', 'HEAD')}/" \
              f"{(post.folder / 'reel.mp4').relative_to(ROOT).as_posix()}"
        wait_reachable(url)
        reel_id = client.publish_reel_url(url, caption, share)
    return {"reel_media_id": reel_id, "reel_permalink": client.permalink(reel_id)}


MAX_REEL_ATTEMPTS = 3


def publish_pending_reel(cfg: dict, folder: Path, now, dry_run: bool = False) -> dict | None:
    """投稿済みのカルーセルから、あとから出すリールを投稿して published.json を更新する。"""
    handle = cfg["handle"]
    post = posts.Post.load(folder)
    caption = posts.compose_reel_caption(post.data, cfg)
    path = folder / "published.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    if dry_run:
        from . import reel

        print(f"\n▶ {handle}: リール {post.id}（カルーセル投稿日 {info.get('posted_date')}）")
        if not story.is_story(post.data):
            print(f"  上部タイトル「{post.data.get('reel_title') or reel.default_title(post.data)}」")
        return None

    client = Client(config.get_token(cfg), cfg["ig_user_id"])
    existing = next((m for m in client.recent_media() if m.get("media_type") in {"VIDEO", "REELS"}
                     and (m.get("caption") or "").strip() == caption.strip()), None)
    error = None
    try:
        info.update(publish_reel(client, cfg, post, caption, existing))
        info.update(reel_status="posted", reel_posted_at=config.now_jst().isoformat(timespec="seconds"),
                    reel_posted_date=now.date().isoformat())
        info.pop("reel_error", None)
        print(f"🎬 {handle}: リールを投稿しました {info.get('reel_permalink') or info.get('reel_media_id')}")
    except Exception as e:
        error = str(e)
        info["reel_error"] = error
        info["reel_attempts"] = int(info.get("reel_attempts", 0)) + 1
        if info["reel_attempts"] >= MAX_REEL_ATTEMPTS:
            info["reel_status"] = "failed"
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commit_and_push(f"リールを投稿しました: {handle}/{post.id}" if not error else f"リールの投稿に失敗: {handle}/{post.id}")
    if error:
        raise RuntimeError(f"リールの投稿に失敗しました（{info['reel_attempts']}回目）: {error}")
    return info


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
    due_reels = find_due_reels(accounts, now, args.account.strip(), args.force, args.dry_run)

    if args.command == "check":
        needs_render = any(post.needs_render(cfg) for cfg, post in due) and not args.dry_run
        needs_voice = not args.dry_run and any(
            story.is_story(post.data) and post.needs_render(cfg) and story.reel_wanted(post.data, cfg)
            for cfg, post in due)
        handles = dict.fromkeys(cfg["handle"] for cfg, _ in due + due_reels)
        set_output(
            due=str(bool(due or due_reels)).lower(),
            needs_render=str(needs_render).lower(),
            needs_voice=str(needs_voice).lower(),
            accounts=",".join(handles),
        )
        return 0

    if not due and not due_reels:
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
    for cfg, folder in due_reels:
        try:
            publish_pending_reel(cfg, folder, now, args.dry_run)
        except (InstagramError, RuntimeError, subprocess.CalledProcessError) as e:
            print(f"❌ {cfg['handle']}: {e}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

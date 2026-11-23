"""投稿データからスライド画像（1080×1350のJPEG）を作る。

使い方:
  python -m autopost.render                 # queue の投稿のうち、作り直しが必要なものだけ
  python -m autopost.render examples --all  # 見本をすべて作り直す
  python -m autopost.render queue/eigo_1phrase/2026-11-12-xxx

type が "story" の投稿（アメコミ風カルーセル＋読み上げ付きリール）は autopost/story が作る。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from . import art, config, posts, story, templates

# 文字が多くて枠からはみ出すときは、少しずつ縮小して収める
FIT_JS = """
() => {
  const out = [];
  for (const s of document.querySelectorAll('section.s')) {
    if (s.classList.contains('pp')) {
      // にぎやかな1枚まとめ：タイトルは3行まで、中身は枠に収まるまで文字と絵を小さくする
      const wrap = s.querySelector('.ppwrap');
      const title = s.querySelector('.pptitle');
      let k = 1, tk = 1;
      const set = () => { s.style.setProperty('--k', String(k)); s.style.setProperty('--tk', String(tk)); };
      set();
      const lines = () => title.getBoundingClientRect().height / (parseFloat(getComputedStyle(title).fontSize) * 1.1);
      while (title && lines() > 3.2 && tk > 0.7) { tk = Math.round((tk - 0.04) * 100) / 100; set(); }
      const over = () => wrap.scrollHeight > wrap.clientHeight + 1;
      // 1行に収めたい短い言葉（日本語・英語・名前）は、少しだけ小さくして1行にする。無理なら折り返す
      for (const el of s.querySelectorAll('.ppl b, .ppr b, .ppit span, .ppt h3 span')) {
        el.style.whiteSpace = 'nowrap';
        let sc = 1;
        while (el.scrollWidth > el.clientWidth + 1 && sc > 0.72) { sc = Math.round((sc - 0.04) * 100) / 100; el.style.setProperty('--s', String(sc)); }
        if (el.scrollWidth > el.clientWidth + 1) { el.style.whiteSpace = ''; el.style.setProperty('--s', '0.88'); }
      }
      // タイトル（つかみ）はなるべく大きいままにして、先に中身を少し小さくする
      while (over() && k > 0.84) { k = Math.round((k - 0.02) * 100) / 100; set(); }
      while (over() && tk > 0.88) { tk = Math.round((tk - 0.02) * 100) / 100; set(); }
      while (over() && k > 0.6) { k = Math.round((k - 0.02) * 100) / 100; set(); }
      while (over() && tk > 0.62) { tk = Math.round((tk - 0.04) * 100) / 100; set(); }
      out.push({zoom: Math.min(k, tk), overflow: over()});
      continue;
    }
    const b = s.querySelector('.body');
    if (!b) { out.push({zoom: 1, overflow: false}); continue; }
    const cs = getComputedStyle(s);
    const limit = s.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    let z = 1;
    b.style.zoom = '1';
    const tooTall = () => b.getBoundingClientRect().height > limit + 1;
    while (tooTall() && z > 0.62) {
      z = Math.round((z - 0.04) * 100) / 100;
      b.style.zoom = String(z);
    }
    out.push({zoom: z, overflow: tooTall()});
  }
  return out;
}
"""


def chrome_path() -> str | None:
    candidates = [os.environ.get("CHROME_PATH", ""), "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
                  "/usr/bin/chromium", "/usr/bin/chromium-browser"]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def make_preview(folder: Path) -> None:
    """全スライドを縮小して1枚に並べた確認用画像（preview.jpg）。"""
    try:
        from PIL import Image
    except ImportError:
        return
    files = sorted(folder.glob("slide*.jpg"))
    if not files:
        return
    cols, tw, th, gap = 4, 270, 338, 12
    rows = math.ceil(len(files) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), "#e9e9e9")
    for idx, f in enumerate(files):
        with Image.open(f) as im:
            thumb = im.convert("RGB")
            thumb.thumbnail((tw, th))
            sheet.paste(thumb, (gap + (idx % cols) * (tw + gap), gap + (idx // cols) * (th + gap)))
    sheet.save(folder / "preview.jpg", quality=85)


async def render_posts(items: list[tuple[Path, dict, dict]]) -> list[str]:
    """items: (投稿フォルダ, 投稿データ, アカウント設定) のリスト。収まらなかった箇所を返す。"""
    from playwright.async_api import async_playwright

    problems: list[str] = []
    async with async_playwright() as p:
        kwargs = {}
        exe = chrome_path()
        if exe:
            kwargs["executable_path"] = exe
        browser = await p.chromium.launch(**kwargs)
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        for folder, data, cfg in items:
            if story.is_story(data):
                from .story import build

                problems += await build.render_story(browser, folder, data, cfg)
                make_preview(folder)
                continue
            await page.set_content(templates.build_html(data, cfg), wait_until="load")
            await page.evaluate("document.fonts.ready")
            fit = await page.evaluate(FIT_JS)
            for old in folder.glob("slide*.jpg"):
                old.unlink()
            sections = await page.query_selector_all("section.s")
            for i, el in enumerate(sections, 1):
                await el.screenshot(path=str(folder / f"slide{i:02d}.jpg"), type="jpeg", quality=92)
            info = {
                "hash": posts.render_hash(data, cfg),
                "slides": len(sections),
                "zoom": [f["zoom"] for f in fit],
                "rendered_at": config.now_jst().isoformat(timespec="seconds"),
            }
            old_reel = folder / "reel.mp4"
            if old_reel.exists():
                old_reel.unlink()
            if posts.quiz_reel_wanted(data, cfg):
                # テスト回は、文字をしぼったクイズリールを画像と一緒に作っておく（PRで確認できるように）
                from . import quizreel, reel

                title = data.get("reel_title") or reel.default_title(data)
                handle = cfg.get("display_handle", "@" + cfg["handle"])
                info["reel_seconds"] = quizreel.make_quiz_reel(data, cfg["theme"], title, handle, old_reel,
                                                               follow=cfg.get("matome_follow") or "")
            (folder / "render.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            make_preview(folder)
            rel = folder.relative_to(config.ROOT) if folder.is_relative_to(config.ROOT) else folder
            for idx, f in enumerate(fit, 1):
                if f["overflow"]:
                    problems.append(f"{rel}: {idx}枚目の文字が多すぎて収まりません。文を短くしてください")
                elif f["zoom"] < 0.85:
                    print(f"⚠️ {rel}: {idx}枚目は文字が多いので{int(f['zoom'] * 100)}%に縮小しました")
            extra = f"・クイズリール{info['reel_seconds']}秒" if "reel_seconds" in info else ""
            print(f"🖼  {rel}: {len(sections)}枚{extra}")
        await browser.close()
    return problems


def changed_from_main(folder: Path) -> bool:
    """main ブランチと比べて post.json が追加・変更されているか（main が取れないときは True）。"""
    rel = (folder / "post.json").relative_to(config.ROOT).as_posix()

    def run(*args):
        r = subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    if run("rev-parse", "--verify", "-q", "origin/main") is None:
        return True
    return run("hash-object", rel) != run("rev-parse", f"origin/main:{rel}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="投稿データからスライド画像を作る")
    ap.add_argument("targets", nargs="*", default=["queue"], help="queue / examples / 投稿フォルダのパス")
    ap.add_argument("--all", action="store_true", help="作成済みのものも作り直す")
    ap.add_argument("--check-voice", action="store_true",
                    help="作らずに、読み上げ音声（VOICEVOX）の準備が必要かだけを調べる")
    ap.add_argument("--changed-only", action="store_true",
                    help="main と比べて追加・変更された投稿だけを作る（プルリクエストのブランチ用。"
                         "デザインの変更で全部を作り直すと、投稿済みのフォルダとぶつかるため）")
    args = ap.parse_args(argv)
    accounts = config.load_accounts()
    folders: list[Path] = []
    for t in args.targets or ["queue"]:
        if t == "queue":
            folders += [p.folder for p in posts.all_queue_posts()]
        elif t == "examples":
            folders += [p.parent for p in sorted((config.ROOT / "examples").glob("*/post.json"))]
        else:
            folders.append(Path(t).resolve())
    items, missing = [], 0
    loaded = []
    for folder in folders:
        post = posts.Post.load(folder)
        cfg = accounts.get(post.account)
        if cfg is None:
            print(f"❌ {folder}: アカウント「{post.account}」の設定がありません")
            missing += 1
            continue
        if args.changed_only and "queue" in folder.parts and not changed_from_main(folder):
            continue
        loaded.append((post, cfg))
    if not args.check_voice:
        # 1枚まとめに入れる絵で足りないものを、先にまとめて作る（GEMINI_API_KEY があるときだけ）
        art.ensure([(post.data, cfg) for post, cfg in loaded])
    for post, cfg in loaded:
        if args.all or post.needs_render(cfg):
            items.append((post.folder, post.data, cfg))
    if args.check_voice:
        need = any(story.is_story(data) and story.reel_wanted(data, cfg) for _, data, cfg in items)
        print(f"needs_voice={str(need).lower()}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                f.write(f"needs_voice={str(need).lower()}\n")
        return 0
    if not items:
        print("作り直しが必要な投稿はありません")
        return 1 if missing else 0
    problems = asyncio.run(render_posts(items))
    for p in problems:
        print(f"❌ {p}")
    return 1 if (problems or missing) else 0


if __name__ == "__main__":
    sys.exit(main())

"""投稿データからスライド画像（1080×1350のJPEG）を作る。

使い方:
  python -m autopost.render                 # queue の投稿のうち、作り直しが必要なものだけ
  python -m autopost.render examples --all  # 見本をすべて作り直す
  python -m autopost.render queue/eigo_1phrase/2026-11-12-xxx
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path

from . import config, posts, templates

# 文字が多くて枠からはみ出すときは、少しずつ縮小して収める
FIT_JS = """
() => {
  const out = [];
  for (const s of document.querySelectorAll('section.s')) {
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
            (folder / "render.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            make_preview(folder)
            rel = folder.relative_to(config.ROOT) if folder.is_relative_to(config.ROOT) else folder
            for idx, f in enumerate(fit, 1):
                if f["overflow"]:
                    problems.append(f"{rel}: {idx}枚目の文字が多すぎて収まりません。文を短くしてください")
                elif f["zoom"] < 0.85:
                    print(f"⚠️ {rel}: {idx}枚目は文字が多いので{int(f['zoom'] * 100)}%に縮小しました")
            print(f"🖼  {rel}: {len(sections)}枚")
        await browser.close()
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="投稿データからスライド画像を作る")
    ap.add_argument("targets", nargs="*", default=["queue"], help="queue / examples / 投稿フォルダのパス")
    ap.add_argument("--all", action="store_true", help="作成済みのものも作り直す")
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
    for folder in folders:
        post = posts.Post.load(folder)
        cfg = accounts.get(post.account)
        if cfg is None:
            print(f"❌ {folder}: アカウント「{post.account}」の設定がありません")
            missing += 1
            continue
        if args.all or post.needs_render(cfg):
            items.append((folder, post.data, cfg))
    if not items:
        print("作り直しが必要な投稿はありません")
        return 1 if missing else 0
    problems = asyncio.run(render_posts(items))
    for p in problems:
        print(f"❌ {p}")
    return 1 if (problems or missing) else 0


if __name__ == "__main__":
    sys.exit(main())

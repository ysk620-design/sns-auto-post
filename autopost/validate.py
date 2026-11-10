"""投稿データ（post.json）のチェック。

使い方:
  python -m autopost.validate             # queue の投稿をすべてチェック
  python -m autopost.validate --examples  # 見本（examples）もチェック
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import config, posts

LAYOUT_FIELDS = {
    "cover": ({"top"}, {"kicker", "ng", "bottom", "big", "sub", "badge", "foot", "tag", "top_size", "ng_size", "big_size"}),
    "callout": ({"title"}, {"label", "body", "note", "style", "tag"}),
    "cards": ({"title", "cards"}, {"note", "tag"}),
    "points": ({"title", "points"}, {"note", "tag", "numbered"}),
    "table": ({"title", "rows"}, {"tag", "foot"}),
    "quiz": ({"question"}, {"answer", "cta", "button", "tag"}),
    "cta": ({"title"}, {"body", "cta", "button", "tag"}),
}
POST_FIELDS = {
    "account", "date", "type", "no", "title", "slides", "caption", "hashtags", "pr", "review_notes",
    "reel", "reel_title",
}
NG_WORDS = ["ストーリーズ"]
MAX_HASHTAGS = 5
MAX_CAPTION = 2200


def _check_slide(i: int, s, errors: list[str]) -> None:
    if not isinstance(s, dict):
        errors.append(f"{i}枚目: 形式が正しくありません")
        return
    layout = s.get("layout")
    if layout not in LAYOUT_FIELDS:
        errors.append(f"{i}枚目: layout「{layout}」は使えません（使えるもの: {', '.join(LAYOUT_FIELDS)}）")
        return
    required, optional = LAYOUT_FIELDS[layout]
    for key in sorted(required):
        if not s.get(key):
            errors.append(f"{i}枚目（{layout}）: {key} がありません")
    unknown = set(s) - required - optional - {"layout"}
    if unknown:
        errors.append(f"{i}枚目（{layout}）: 使えない項目があります: {', '.join(sorted(unknown))}")
    if layout == "callout" and s.get("style", "ng") not in ("ng", "ok"):
        errors.append(f"{i}枚目（callout）: style は ng か ok にしてください")
    if layout == "cards":
        cards = s.get("cards")
        if not isinstance(cards, list) or not 1 <= len(cards) <= 3:
            errors.append(f"{i}枚目（cards）: cards は1〜3個にしてください")
    if layout == "points":
        pts = s.get("points")
        if not isinstance(pts, list) or not 1 <= len(pts) <= 6 or not all(isinstance(p, str) for p in pts):
            errors.append(f"{i}枚目（points）: points は文字を1〜6個にしてください")
    if layout == "table":
        rows = s.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
            errors.append(f"{i}枚目（table）: rows は1〜6行にしてください")


def validate_post(data, accounts: dict, folder: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["post.json の形式が正しくありません"]
    unknown = set(data) - POST_FIELDS
    if unknown:
        errors.append(f"使えない項目があります: {', '.join(sorted(unknown))}")
    account = data.get("account")
    if account not in accounts:
        errors.append(f"account「{account}」が accounts/ にありません")
    if folder is not None and folder.parent.name != account:
        errors.append(f"フォルダの場所（{folder.parent.name}）と account（{account}）が一致しません")
    try:
        date.fromisoformat(str(data.get("date", "")))
    except ValueError:
        errors.append("date は 2026-11-12 のような形で書いてください")
    kind = data.get("type", "carousel")
    slides = data.get("slides")
    if kind not in ("carousel", "image"):
        errors.append("type は carousel か image にしてください")
    if not isinstance(slides, list) or not slides:
        errors.append("slides がありません")
    else:
        if kind == "carousel" and not 2 <= len(slides) <= 10:
            errors.append("カルーセルは2〜10枚にしてください")
        if kind == "image" and len(slides) != 1:
            errors.append("type が image のときは1枚にしてください")
        for i, s in enumerate(slides, 1):
            _check_slide(i, s, errors)
    caption = data.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        errors.append("caption（本文）がありません")
    else:
        if "#" in caption or "＃" in caption:
            errors.append("本文に # を書かないでください（ハッシュタグになってしまいます。番号は No.01 のように書く）")
        for word in NG_WORDS:
            if word in caption:
                errors.append(f"本文に「{word}」を含めないでください")
    tags = data.get("hashtags", [])
    if not isinstance(tags, list) or len(tags) > MAX_HASHTAGS:
        errors.append(f"hashtags は{MAX_HASHTAGS}個までにしてください")
    else:
        for tag in tags:
            if not isinstance(tag, str) or not tag.startswith("#") or len(tag) < 2 or any(c.isspace() for c in tag):
                errors.append(f"ハッシュタグ「{tag}」の形が正しくありません（#から始めて、空白を入れない）")
    if "pr" in data and not isinstance(data["pr"], bool):
        errors.append("pr は true か false にしてください")
    if "reel" in data and not isinstance(data["reel"], bool):
        errors.append("reel は true か false にしてください")
    if "reel_title" in data and (not isinstance(data["reel_title"], str) or len(data["reel_title"]) > 30):
        errors.append("reel_title（リール上部のタイトル）は30文字以内にしてください")
    if isinstance(caption, str) and len(posts.compose_caption(data)) > MAX_CAPTION:
        errors.append(f"キャプションが長すぎます（ハッシュタグ込みで{MAX_CAPTION}文字まで）")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="投稿データをチェックする")
    ap.add_argument("--examples", action="store_true", help="見本（examples）もチェックする")
    args = ap.parse_args(argv)
    accounts = config.load_accounts()
    targets = [(p.folder, True) for p in posts.all_queue_posts()]
    if args.examples:
        targets += [(p.parent, False) for p in sorted((config.ROOT / "examples").glob("*/post.json"))]
    total_errors = 0
    for folder, in_queue in targets:
        rel = folder.relative_to(config.ROOT)
        try:
            data = posts.Post.load(folder).data
        except ValueError as e:
            print(f"❌ {rel}: post.json を読み込めません（{e}）")
            total_errors += 1
            continue
        errors = validate_post(data, accounts, folder if in_queue else None)
        if errors:
            total_errors += len(errors)
            print(f"❌ {rel}")
            for err in errors:
                print(f"   - {err}")
        else:
            print(f"✅ {rel}")
    if not targets:
        print("チェックする投稿はありません")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())

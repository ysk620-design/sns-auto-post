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

import re

from . import config, posts, story

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
STORY_FIELDS = {
    "account", "date", "type", "no", "title", "caption", "hashtags", "pr", "review_notes", "reel", "sources",
    "icon", "burst", "top", "big", "big_size", "chat_title", "scenes", "comments", "stat", "cta", "reel_script",
}
SCENE_FIELDS = {"title", "mood", "say", "nar", "prop", "clerk", "police", "kid", "look"}
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


def _text_ok(value, errors: list[str], where: str, limit: int | None = None) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} がありません")
        return
    if "<" in story.ALLOWED_TAGS.sub("", value):
        errors.append(f"{where}: 使える装飾は <br> と <em> だけです")
    if limit and len(re.sub(r"<[^>]+>", "", value)) > limit:
        errors.append(f"{where}: 長すぎます（{limit}文字まで）")


def _check_icon(value, errors: list[str], where: str) -> None:
    if not isinstance(value, str) or value.partition(":")[0] not in story.ICONS:
        errors.append(f"{where}「{value}」は使えません（使えるもの: {', '.join(story.ICONS)}）")


def _check_comments(items, errors: list[str], where: str, lo: int, hi: int, limit: int) -> None:
    if not isinstance(items, list) or not lo <= len(items) <= hi:
        errors.append(f"{where} は{lo}〜{hi}個にしてください")
        return
    for i, c in enumerate(items, 1):
        if not isinstance(c, list) or len(c) != 3 or not all(isinstance(x, str) and x.strip() for x in c):
            errors.append(f"{where}の{i}個目: [国旗の絵文字, だれの声か, コメント] の3つを書いてください")
            continue
        _text_ok(c[1], errors, f"{where}の{i}個目（だれの声か）", 24)
        _text_ok(c[2], errors, f"{where}の{i}個目（コメント）", limit)


def _validate_story(data: dict, errors: list[str]) -> None:
    unknown = set(data) - STORY_FIELDS
    if unknown:
        errors.append(f"使えない項目があります: {', '.join(sorted(unknown))}")
    _check_icon(data.get("icon"), errors, "icon")
    _text_ok(data.get("top"), errors, "top（表紙の1行目）", 16)
    _text_ok(data.get("big"), errors, "big（表紙の大きな文字）", 24)
    _text_ok(data.get("chat_title"), errors, "chat_title（リールのチャット画面の見出し）", 40)
    _text_ok(data.get("cta"), errors, "cta（最後の問いかけ）", 40)
    if "burst" in data and (not isinstance(data["burst"], str) or not re.fullmatch(r"[A-Z!? ]{1,8}", data["burst"])):
        errors.append("burst は WOW! のような英大文字8文字以内にしてください")
    if "big_size" in data and not (isinstance(data["big_size"], int) and 60 <= data["big_size"] <= 130):
        errors.append("big_size は 60〜130 の数字にしてください")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 4:
        errors.append("scenes（場面）は4つにしてください")
        scenes = []
    for i, sc in enumerate(scenes, 1):
        if not isinstance(sc, dict):
            errors.append(f"場面{i}: 形式が正しくありません")
            continue
        extra = set(sc) - SCENE_FIELDS
        if extra:
            errors.append(f"場面{i}: 使えない項目があります: {', '.join(sorted(extra))}")
        _text_ok(sc.get("title"), errors, f"場面{i}の title", 14)
        _text_ok(sc.get("say"), errors, f"場面{i}の say（ふきだし）", 18)
        _text_ok(sc.get("nar"), errors, f"場面{i}の nar（説明）", 44)
        if sc.get("mood") not in story.MOODS:
            errors.append(f"場面{i}: mood は {', '.join(story.MOODS)} のどれかにしてください")
        if "clerk" in sc and sc["clerk"] not in story.MOODS:
            errors.append(f"場面{i}: clerk は {', '.join(story.MOODS)} のどれかにしてください")
        if "prop" in sc:
            _check_icon(sc["prop"], errors, f"場面{i}の prop")
        look = sc.get("look", {})
        if not isinstance(look, dict) or set(look) - {"hair", "shirt"} or \
                not all(isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) for v in look.values()):
            errors.append(f"場面{i}: look は hair と shirt を #2b2b2b のような色で書いてください")
    _check_comments(data.get("comments"), errors, "comments（海外の声）", 3, 6, 44)
    st = data.get("stat")
    if not isinstance(st, dict) or set(st) != {"l1", "n1", "l2", "n2", "msg", "src"}:
        errors.append("stat（実は…の数字）は l1, n1, l2, n2, msg, src をすべて書いてください")
    else:
        for key, limit in (("l1", 20), ("n1", 9), ("l2", 20), ("n2", 9), ("msg", 50), ("src", 70)):
            _text_ok(st[key], errors, f"stat の {key}", limit)
    rs = data.get("reel_script")
    if data.get("reel", True) is not False:
        if not isinstance(rs, dict) or set(rs) != {"comments", "nar"}:
            errors.append("reel_script（リール用）は comments と nar を書いてください")
        else:
            _check_comments(rs["comments"], errors, "reel_script の comments", 3, 3, 30)
            nar = rs["nar"]
            want = 1 + len(scenes) + 3 + 2  # 表紙＋場面＋海外の声3つ＋実は…＋締め
            if not isinstance(nar, list) or len(nar) != want or \
                    not all(isinstance(t, str) and t.strip() and "<" not in t for t in nar):
                errors.append(f"reel_script の nar（読み上げ台本）は{want}行にしてください（1画面に1行）")
            elif any(len(t) > 60 for t in nar):
                errors.append("reel_script の nar: 1行は60文字までにしてください")
    src = data.get("sources")
    if not isinstance(src, list) or not src or not all(isinstance(s, str) and "http" in s for s in src):
        errors.append("sources に、海外の声と数字の出典（URL入り）を書いてください")


def validate_post(data, accounts: dict, folder: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["post.json の形式が正しくありません"]
    wanted = (accounts.get(data.get("account")) or {}).get("format", "slides")
    if story.is_story(data) != (wanted == "story"):
        errors.append('このアカウントは type を "story" にしてください' if wanted == "story"
                      else 'type "story" は、format が "story" のアカウントでしか使えません')
    unknown = set() if story.is_story(data) else set(data) - POST_FIELDS
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
    if kind == "story":
        _validate_story(data, errors)
    elif kind not in ("carousel", "image"):
        errors.append("type は carousel か image にしてください")
    if kind == "story":
        pass
    elif not isinstance(slides, list) or not slides:
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

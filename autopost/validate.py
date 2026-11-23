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

from . import config, cover_art, posts, story

LAYOUT_FIELDS = {
    "cover": ({"top"}, {"kicker", "ng", "bottom", "big", "sub", "badge", "foot", "tag", "top_size", "ng_size", "big_size", "art", "art_labels"}),
    "callout": ({"title"}, {"label", "body", "note", "style", "tag"}),
    "cards": ({"title", "cards"}, {"note", "tag"}),
    "points": ({"title", "points"}, {"note", "tag", "numbered"}),
    "table": ({"title", "rows"}, {"tag", "foot"}),
    "quiz": ({"question"}, {"answer", "cta", "button", "tag"}),
    "cta": ({"title"}, {"body", "cta", "button", "tag"}),
    "matome": ({"title", "items"}, {"kicker", "sub", "head", "note", "big", "big_label", "rank", "follow"}),
    "pop": ({"title", "items"}, {"kicker", "bubble", "sub", "big", "big_label", "head", "rank", "arrow", "note",
                                 "follow", "bg", "ask", "tag"}),
    "tiles": ({"title", "tiles"}, {"kicker", "bubble", "sub", "cols", "summary", "note", "follow", "bg", "ask", "tag"}),
    "tier": ({"title", "tiers"}, {"kicker", "bubble", "sub", "note", "follow", "bg", "ask", "tag"}),
}
TALL_LAYOUTS = ("matome", "pop", "tiles", "tier")  # 縦長の1枚（リールだけの投稿で使う）
POST_FIELDS = {
    "account", "date", "type", "no", "title", "slides", "caption", "hashtags", "pr", "review_notes",
    "reel", "reel_title", "reel_style", "reel_questions", "post_hour_jst", "quiz_end_title",
}
STORY_FIELDS = {
    "account", "date", "type", "no", "title", "caption", "hashtags", "pr", "review_notes", "reel", "sources",
    "icon", "burst", "top", "big", "big_size", "chat_title", "scenes", "comments", "stat", "cta", "reel_script",
    "color", "art",
}
SCENE_FIELDS = {"title", "mood", "say", "nar", "prop", "clerk", "police", "kid", "look", "art", "say_side"}
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
    if layout == "cover" and "art" in s and s["art"] not in cover_art.ARTS:
        errors.append(f"{i}枚目（cover）: art は {' / '.join(cover_art.ARTS)} のどれかにしてください")
    if layout == "cover" and "art_labels" in s:
        lb = s["art_labels"]
        if not (isinstance(lb, list) and len(lb) == 2 and all(isinstance(x, str) and len(x) <= 7 for x in lb)):
            errors.append(f"{i}枚目（cover）: art_labels は7文字以内の文字を2つにしてください")
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
    if layout == "matome":
        items = s.get("items")
        if not isinstance(items, list) or not 6 <= len(items) <= 14:
            errors.append(f"{i}枚目（matome）: items は6〜14行にしてください")
        elif not all(isinstance(it, list) and len(it) == 3 and all(isinstance(x, str) and x for x in it) for it in items):
            errors.append(f"{i}枚目（matome）: items は [状況, 金額, 制度名] の3つを並べてください")
        if "head" in s and not (isinstance(s["head"], list) and len(s["head"]) == 2):
            errors.append(f"{i}枚目（matome）: head は列の見出しを2つにしてください")
    if layout == "table":
        rows = s.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
            errors.append(f"{i}枚目（table）: rows は1〜6行にしてください")
    if layout in ("pop", "tiles", "tier"):
        _check_pop(i, layout, s, errors)


def _plain_len(value) -> int:
    return len(re.sub(r"<[^>]+>", "", str(value)))


def _short(value, limit: int, where: str, errors: list[str], required: bool = False) -> None:
    if value is None or value == "":
        if required:
            errors.append(f"{where} がありません")
        return
    if not isinstance(value, str):
        errors.append(f"{where} は文字で書いてください")
    elif _plain_len(value) > limit:
        errors.append(f"{where}「{value}」が長すぎます（{limit}文字まで）")


def _check_art_text(value, where: str, errors: list[str]) -> None:
    """icon / bg は Gemini に渡す英語の説明。"""
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or not value.isascii() or len(value) > 160:
        errors.append(f"{where} は英語の短い説明（160文字まで）にしてください。例 \"an empty wallet with a moth flying out\"")


def _check_pop(i: int, layout: str, s: dict, errors: list[str]) -> None:
    where = f"{i}枚目（{layout}）"
    _short(s.get("title"), 40, f"{where}: title", errors, True)
    _short(s.get("kicker"), 24, f"{where}: kicker", errors)
    _short(s.get("bubble"), 24, f"{where}: bubble", errors)
    _short(s.get("sub"), 34, f"{where}: sub", errors)
    _short(s.get("ask"), 16, f"{where}: ask", errors)
    _short(s.get("note"), 80, f"{where}: note", errors)
    _check_art_text(s.get("bg"), f"{where}: bg", errors)
    if layout == "pop":
        items = s.get("items")
        if not isinstance(items, list) or not 5 <= len(items) <= 12:
            errors.append(f"{where}: items は5〜12行にしてください")
        if not isinstance(items, list):
            items = []
        for k, it in enumerate(items, 1):
            w = f"{where} の{k}行目"
            if not isinstance(it, dict):
                errors.append(f"{w}: {{\"left\": …, \"right\": …}} の形で書いてください")
                continue
            extra = set(it) - {"left", "right", "left_sub", "right_sub", "ng", "icon"}
            if extra:
                errors.append(f"{w}: 使えない項目があります: {', '.join(sorted(extra))}")
            _short(it.get("left"), 16, f"{w}の left", errors, True)
            _short(it.get("right"), 30, f"{w}の right", errors, True)
            _short(it.get("left_sub"), 24, f"{w}の left_sub", errors)
            _short(it.get("right_sub"), 26, f"{w}の right_sub", errors)
            _short(it.get("ng"), 26, f"{w}の ng", errors)
            _check_art_text(it.get("icon"), f"{w}の icon", errors)
        if "head" in s and not (isinstance(s["head"], list) and len(s["head"]) == 2
                                and all(isinstance(x, str) and 0 < len(x) <= 12 for x in s["head"])):
            errors.append(f"{where}: head は列の見出し（12文字まで）を2つにしてください")
    if layout == "tiles":
        tiles = s.get("tiles")
        if not isinstance(tiles, list) or not 4 <= len(tiles) <= 12:
            errors.append(f"{where}: tiles は4〜12個にしてください")
        if not isinstance(tiles, list):
            tiles = []
        for k, t in enumerate(tiles, 1):
            w = f"{where} の{k}個目"
            if not isinstance(t, dict):
                errors.append(f"{w}: {{\"label\": …, \"icon\": …, \"a\": …, \"b\": …}} の形で書いてください")
                continue
            extra = set(t) - {"label", "icon", "a", "b"}
            if extra:
                errors.append(f"{w}: 使えない項目があります: {', '.join(sorted(extra))}")
            _short(t.get("label"), 10, f"{w}の label", errors, True)
            _short(t.get("a"), 14, f"{w}の a", errors)
            _short(t.get("b"), 26, f"{w}の b", errors)
            _check_art_text(t.get("icon"), f"{w}の icon", errors)
        if "cols" in s and s["cols"] not in (2, 3):
            errors.append(f"{where}: cols は 2 か 3 にしてください")
        sm = s.get("summary")
        if sm is not None and not (isinstance(sm, dict) and set(sm) <= {"label", "big"} and sm.get("big")):
            errors.append(f"{where}: summary は {{\"label\": …, \"big\": …}} の形で書いてください")
        elif isinstance(sm, dict):
            _short(sm.get("label"), 20, f"{where}: summary の label", errors)
            _short(sm.get("big"), 14, f"{where}: summary の big", errors)
    if layout == "tier":
        tiers = s.get("tiers")
        if not isinstance(tiers, list) or not 3 <= len(tiers) <= 6:
            errors.append(f"{where}: tiers は3〜6段にしてください")
        if not isinstance(tiers, list):
            tiers = []
        for k, t in enumerate(tiers, 1):
            w = f"{where} の{k}段目"
            if not isinstance(t, dict):
                errors.append(f"{w}: {{\"rank\": \"S\", \"items\": [...]}} の形で書いてください")
                continue
            extra = set(t) - {"rank", "label", "items", "color"}
            if extra:
                errors.append(f"{w}: 使えない項目があります: {', '.join(sorted(extra))}")
            _short(t.get("rank"), 3, f"{w}の rank", errors, True)
            _short(t.get("label"), 14, f"{w}の label", errors)
            if "color" in t and not (isinstance(t["color"], str) and re.fullmatch(r"#[0-9a-fA-F]{6}", t["color"])):
                errors.append(f"{w}: color は #ff5a5f のような色で書いてください")
            its = t.get("items")
            if not isinstance(its, list) or not 1 <= len(its) <= 5:
                errors.append(f"{w}: items は1〜5個にしてください")
                continue
            for m, it in enumerate(its, 1):
                ww = f"{w}の{m}個目"
                if not isinstance(it, dict):
                    errors.append(f"{ww}: {{\"name\": …, \"icon\": …}} の形で書いてください")
                    continue
                extra = set(it) - {"name", "icon", "note"}
                if extra:
                    errors.append(f"{ww}: 使えない項目があります: {', '.join(sorted(extra))}")
                _short(it.get("name"), 9, f"{ww}の name", errors, True)
                _short(it.get("note"), 12, f"{ww}の note", errors)
                _check_art_text(it.get("icon"), f"{ww}の icon", errors)


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


def _check_story_art(data: dict, scenes: list, errors: list[str]) -> None:
    """漫画の絵（Gemini）の説明。art を書いたら、表紙・4場面・締めの6コマすべてに説明が必要。"""
    a = data.get("art")
    if a is None:
        if any(isinstance(sc, dict) and "art" in sc for sc in scenes):
            errors.append("場面に art を書くときは、投稿の art（cast・cover・end）も書いてください")
        return
    if not isinstance(a, dict) or set(a) != {"cast", "cover", "end"}:
        errors.append("art は cast（登場人物の見た目）・cover（表紙のコマ）・end（締めのコマ）の3つを書いてください")
    for key, limit in (("cast", 420), ("cover", 300), ("end", 300)):
        v = a.get(key) if isinstance(a, dict) else None
        if v is not None and (not isinstance(v, str) or not v.strip() or not v.isascii() or len(v) > limit):
            errors.append(f"art の {key} は英語で書いてください（{limit}文字まで）")
    for i, sc in enumerate(scenes, 1):
        if not isinstance(sc, dict):
            continue
        v = sc.get("art")
        if not isinstance(v, str) or not v.strip() or not v.isascii() or len(v) > 300:
            errors.append(f"場面{i}: art（このコマの絵の説明）を英語で書いてください（300文字まで）")
        if "say_side" in sc and sc["say_side"] not in ("left", "right"):
            errors.append(f"場面{i}: say_side は left か right にしてください（話している人がいる側）")


def _validate_story(data: dict, errors: list[str]) -> None:
    if "color" in data:
        from .story import design
        if data["color"] not in design.PALETTES:
            errors.append(f"color は {' / '.join(design.PALETTES)} のどれかにしてください")
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
    _check_story_art(data, scenes, errors)
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
    if data.get("type") == "reel_only":
        pass  # リールだけの投稿は、どのアカウントでも使える
    elif story.is_story(data) != (wanted == "story"):
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
    elif kind not in ("carousel", "image", "reel_only"):
        errors.append("type は carousel・image・reel_only のどれかにしてください")
    if kind == "reel_only":
        h = data.get("post_hour_jst")
        if not (isinstance(h, int) and 0 <= h <= 23):
            errors.append("type が reel_only のときは、post_hour_jst（投稿する時。0〜23）を書いてください")
        if data.get("reel_style") == "quiz":
            pass  # クイズリールだけを出す（問題のスライドの形は quizreel.validate が確かめる）
        elif not (isinstance(slides, list) and len(slides) == 1 and isinstance(slides[0], dict)
                  and slides[0].get("layout") in TALL_LAYOUTS):
            errors.append("type が reel_only のときは、slides を matome・pop・tiles・tier のどれか1枚にしてください")
    elif "post_hour_jst" in data:
        errors.append("post_hour_jst は type が reel_only のときだけ書けます")
    if kind == "story":
        pass
    elif not isinstance(slides, list) or not slides:
        errors.append("slides がありません")
    else:
        if kind == "carousel" and not 2 <= len(slides) <= 10:
            errors.append("カルーセルは2〜10枚にしてください")
        if (kind == "image" or (kind == "reel_only" and data.get("reel_style") != "quiz")) and len(slides) != 1:
            errors.append("type が image のときは1枚にしてください")
        for i, s in enumerate(slides, 1):
            _check_slide(i, s, errors)
            if isinstance(s, dict) and s.get("layout") in ("pop", "tiles", "tier") and kind != "reel_only":
                errors.append(f"{i}枚目: {s['layout']} は縦長なので、type が reel_only の投稿でだけ使えます")
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
    if "reel_style" in data and data["reel_style"] != "quiz":
        errors.append("reel_style は quiz だけ使えます（テスト回のクイズリール）")
    if data.get("reel_style") == "quiz":
        from . import quizreel
        errors += [f"クイズリール: {e}" for e in quizreel.validate(data)]
    elif "reel_questions" in data:
        errors.append("reel_questions は reel_style が quiz のときだけ書けます")
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

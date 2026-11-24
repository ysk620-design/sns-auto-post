"""1枚まとめ（pop / tiles / tier）に入れる絵（アイコン・背景）と、海外反応の漫画の絵の用意と読み込み。

- アイコン: assets/icons/<タッチ>/<名前>.jpg。投稿の icon（英語の短い説明）から名前を作るので、
  同じ説明なら前に作った絵を使い回す（お金がかからない）
- 背景:    assets/bg/<名前>.jpg。スライドの bg（英語の説明）か、accounts/*.json の art.backgrounds から日替わり
- 漫画: assets/story/<名前>/p1〜p6.jpg（表紙・場面4つ・締め）。投稿の art（登場人物と表紙・締めの説明）と
  各場面の art から、1回で6コマを描かせて切り分ける（人物の見た目がそろう）
- 無い絵は、GitHub Actions で画像を作るとき（GEMINI_API_KEY があるとき）に Gemini でまとめて作る。
  キーが無いときや失敗したときは、絵なしで作る（あとで絵ができたら、自動で作り直される）
"""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import date
from pathlib import Path

from . import config

ASSETS = config.ROOT / "assets"
POP_LAYOUTS = ("pop", "tiles", "tier", "podium", "bars")
# 1回の実行で作ってよい数の上限（設定ミスでお金を使いすぎないように）
MAX_ICONS_PER_RUN = 72
MAX_BGS_PER_RUN = 8
MAX_COMICS_PER_RUN = 10


def slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    base = "-".join(words)[:48].strip("-") or "art"
    digest = hashlib.sha1(" ".join(str(text).lower().split()).encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


def style_of(cfg: dict) -> str:
    return str((cfg.get("art") or {}).get("style", "clay"))


def icon_path(desc: str, cfg: dict, root: Path | None = None) -> Path:
    return (root or ASSETS) / "icons" / style_of(cfg) / f"{slug(desc)}.jpg"


def bg_path(desc: str, root: Path | None = None) -> Path:
    return (root or ASSETS) / "bg" / f"{slug(desc)}.jpg"


def _clean(values) -> list[str]:
    out = []
    for v in values:
        if isinstance(v, str) and v.strip() and v.strip() not in out:
            out.append(v.strip())
    return out


def icons_of(slide: dict) -> list[str]:
    layout = slide.get("layout")
    found: list = []
    if layout in ("pop", "podium", "bars"):
        found = [it.get("icon") for it in slide.get("items") or [] if isinstance(it, dict)]
    elif layout == "tiles":
        found = [t.get("icon") for t in slide.get("tiles") or [] if isinstance(t, dict)]
    elif layout == "tier":
        for t in slide.get("tiers") or []:
            if isinstance(t, dict):
                found += [it.get("icon") for it in t.get("items") or [] if isinstance(it, dict)]
    return _clean(found)


def background_of(slide: dict, data: dict, cfg: dict) -> str | None:
    if slide.get("layout") not in POP_LAYOUTS:
        return None
    if isinstance(slide.get("bg"), str) and slide["bg"].strip():
        return slide["bg"].strip()
    pool = _clean((cfg.get("art") or {}).get("backgrounds") or [])
    if not pool:
        return None
    try:
        day = date.fromisoformat(str(data.get("date", ""))).toordinal()
    except ValueError:
        day = 0
    return pool[day % len(pool)]


def wanted(data: dict, cfg: dict) -> tuple[list[str], list[str]]:
    icons: list[str] = []
    bgs: list[str] = []
    for s in data.get("slides") or []:
        if not isinstance(s, dict):
            continue
        icons += icons_of(s)
        b = background_of(s, data, cfg)
        if b:
            bgs.append(b)
    return _clean(icons), _clean(bgs)


def missing(data: dict, cfg: dict) -> tuple[list[str], list[str]]:
    icons, bgs = wanted(data, cfg)
    return [i for i in icons if not icon_path(i, cfg).exists()], [b for b in bgs if not bg_path(b).exists()]


def state(data: dict, cfg: dict) -> list[str]:
    """描くときに使える絵の一覧。render の指紋に入れて、絵があとからできたら作り直す。"""
    icons, bgs = wanted(data, cfg)
    paths = [icon_path(i, cfg) for i in icons] + [bg_path(b) for b in bgs]
    return [p.name for p in paths if p.exists()]


# ---------- 海外反応のストーリー（漫画の6コマ） ----------

def story_panels_wanted(data: dict) -> list[str] | None:
    """漫画の6コマ（表紙・場面4つ・締め）の説明。art が書かれていない投稿は None（今までの絵）。"""
    a = data.get("art")
    scenes = data.get("scenes") or []
    if not isinstance(a, dict) or not a.get("cast") or len(scenes) != 4:
        return None
    descs = [a.get("cover")] + [sc.get("art") if isinstance(sc, dict) else None for sc in scenes] + [a.get("end")]
    if not all(isinstance(d, str) and d.strip() for d in descs):
        return None
    return [d.strip() for d in descs]


def story_dir(data: dict, root: Path | None = None) -> Path | None:
    descs = story_panels_wanted(data)
    if descs is None:
        return None
    key = hashlib.sha1(("\n".join([data["art"]["cast"].strip()] + descs)).encode("utf-8")).hexdigest()[:12]
    return (root or ASSETS) / "story" / key


def story_paths(data: dict) -> list[Path]:
    d = story_dir(data)
    return [d / f"p{i}.jpg" for i in range(1, 7)] if d else []


def story_missing(data: dict) -> bool:
    paths = story_paths(data)
    return bool(paths) and not all(p.exists() for p in paths)


def story_uris(data: dict) -> list[str]:
    """6コマの絵（data URI）。1コマでも足りなければ空（今までの絵で作る。絵柄が混ざらないように）。"""
    paths = story_paths(data)
    return [data_uri(p) for p in paths] if paths and all(p.exists() for p in paths) else []


def cleanup_story(data: dict) -> None:
    """投稿が済んだストーリーの漫画の絵を消す（スライドとリールに入っているので、もう使わない）。"""
    import shutil

    d = story_dir(data)
    if d and d.exists():
        shutil.rmtree(d)


def missing_any(data: dict, cfg: dict) -> bool:
    """作る予定の絵（アイコン・背景・漫画）に、まだ無いものがあるか。"""
    icons, bgs = missing(data, cfg)
    return bool(icons or bgs) or story_missing(data)


def data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def icon_uri(desc, cfg: dict) -> str:
    if not isinstance(desc, str) or not desc.strip():
        return ""
    return data_uri(icon_path(desc.strip(), cfg))


def bg_uri(slide: dict, data: dict, cfg: dict) -> str:
    b = background_of(slide, data, cfg)
    return data_uri(bg_path(b)) if b else ""


def ensure(items: list[tuple[dict, dict]], log=print) -> int:
    """items（投稿データ, アカウント設定）に足りない絵を Gemini で作る。作った数を返す。"""
    from . import imagegen

    need_icons: dict[str, list[str]] = {}
    models: dict[str, list[str] | None] = {}
    need_bgs: list[str] = []
    bg_models: list[str] | None = None
    for data, cfg in items:
        icons, bgs = missing(data, cfg)
        st = style_of(cfg)
        bucket = need_icons.setdefault(st, [])
        bucket += [i for i in icons if i not in bucket]
        models.setdefault(st, (cfg.get("art") or {}).get("icon_models"))
        need_bgs += [b for b in bgs if b not in need_bgs]
        bg_models = bg_models or (cfg.get("art") or {}).get("bg_models")
    need_story = [(data, cfg) for data, cfg in items if story_missing(data)]
    total = sum(len(v) for v in need_icons.values()) + len(need_bgs) + len(need_story) * 6
    if not total:
        return 0
    if not imagegen.api_key():
        log(f"🎨 絵が{total}個足りませんが、GEMINI_API_KEY が無いので絵なしで作ります")
        return 0
    made = 0
    budget = MAX_ICONS_PER_RUN
    for st, descs in need_icons.items():
        descs = descs[:budget]
        if not descs:
            continue
        budget -= len(descs)
        log(f"🎨 アイコンを{len(descs)}個作ります（タッチ: {st}）")
        dummy = {"art": {"style": st}}
        made += imagegen.generate_icons(descs, [icon_path(d, dummy) for d in descs], style=st,
                                        models=models.get(st), log=log)
    for desc in need_bgs[:MAX_BGS_PER_RUN]:
        log(f"🎨 背景を作ります: {desc[:60]}")
        if imagegen.generate_background(desc, bg_path(desc), models=bg_models, log=log):
            made += 1
    for data, cfg in need_story[:MAX_COMICS_PER_RUN]:
        log(f"🎨 漫画（6コマ）を作ります: {data.get('title') or data.get('top', '')}")
        acfg = cfg.get("art") or {}
        failed = story_dir(data) / "failed-sheet.jpg"  # コマ割りに失敗したときの元の絵（原因を見るため）
        n = imagegen.generate_comic(data["art"]["cast"], story_panels_wanted(data), story_paths(data),
                                    models=acfg.get("comic_models"), style=acfg.get("comic_style", ""),
                                    fail_sheet=failed, log=log)
        if n and failed.exists():
            failed.unlink()
        made += n
    if total > made:
        log(f"⚠️ 絵が{total - made}個できませんでした（その部分は今までの絵で作ります）")
    return made

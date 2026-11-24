"""にぎやかな1枚まとめ（縦長 1080×1920。リールだけの投稿 type "reel_only" で使う）。

伸びている1枚まとめの型（大きな中央タイトル・巨大な数字・1項目ごとの絵・写真の背景・余白なし）を、
オリジナルの中身で作る。絵は Gemini で作る（art.py）。絵がまだ無いときは、絵なしで作る。

layout:
  pop    10選などのリスト。title / kicker / bubble / sub / big / big_label / head（列の見出し2つ） /
         items（6〜12行。各行 {left, right, left_sub, right_sub, ng, icon}） / rank（true で上位3つにメダル） /
         arrow（false で → を出さない） / note / follow / bg
  tiles  絵のマス目（日本と海外の比べっこなど）。title / kicker / bubble / sub / cols（2か3） /
         tiles（4〜12個。各 {label, icon, a, b}） / summary（{label, big}） / note / follow / bg
  podium 表彰台＋横棒のランキング（数字の大きさを棒で見せる）。title / kicker / bubble / sub / big / big_label /
         items（6〜9個。各 {name, value, num, icon, note}。num は棒の長さに使う数（例 50.8）。上位3つは表彰台、
         4位からは横棒） / note / follow / bg / ask
  bars   横棒のランキング（全部を一列の横棒で、数字の差を棒の長さで見せる。上位3つは金銀銅）。項目は podium と同じで
         items は6〜10個
  tree   樹形図（分かれ道を選ぶたびに累計がふえ、行き止まりに総額）。title / kicker / bubble / sub / big / big_label /
         stages（各 {name, years, options: {選択肢: 金額（万円）}}） / routes（3〜8本。各 {path: [各段階の選択肢], name}） /
         unit / note / follow / bg / ask。同じ選択の続く部分は1本にまとまる
  tier   ティア表。title / kicker / bubble / sub / tiers（3〜6段。各 {rank, label, items: [{name, icon, note}]}） /
         note / follow / bg

共通: title の「10選」「TOP10」の数字は自動で大きくなる。<span class="hl">…</span> は強調色の文字になる。
icon / bg は英語の短い説明（例 "an empty wallet with a moth flying out"）。同じ説明の絵は使い回す。
"""
from __future__ import annotations

import re

from . import art

TIER_COLORS = {"S": "#f2b705", "A": "#ff5a5f", "B": "#ff9f1c", "C": "#2ec4b6", "D": "#3a86ff", "E": "#8e7dbe"}
TILE_COLORS = ["#ff5c8a", "#ff8a00", "#2bb673", "#2f80ed", "#9b51e0", "#00a8c6", "#eb5757", "#27ae60", "#f2994a",
               "#56ccf2", "#bb6bd9", "#6fcf97"]
_NUM_RE = re.compile(r"(\d+)(?=選)|(?<=TOP)(\d+)")


def _title(esc, text: str) -> str:
    out = esc(text)
    # 「10選」「TOP10」の数字を大きく（タグの中の数字はさわらない）
    parts = re.split(r"(<[^>]+>)", out)
    for i, p in enumerate(parts):
        if not p.startswith("<"):
            parts[i] = _NUM_RE.sub(lambda m: f'<span class="ppnum">{m.group(0)}</span>', p)
    return "".join(parts)


def _width(text) -> float:
    """文字の幅のおおよそ（全角1、半角0.58）。"""
    plain = re.sub(r"<[^>]+>", "", str(text or ""))
    return sum(0.58 if ord(ch) < 0x2E80 else 1.0 for ch in plain)


def _split(items: list) -> float:
    """左（日本語・状況）と右（英語・金額）の幅の配分。長い方を広くする。"""
    left = max([_width(it.get("left")) * 40 for it in items] + [_width(it.get("left_sub") or it.get("ng")) * 24 for it in items])
    right = max([_width(it.get("right")) * 42 for it in items] + [_width(it.get("right_sub")) * 24 for it in items])
    share = left / (left + right) if left + right else 0.42
    return min(0.64, max(0.3, share))


def _img(uri: str, cls: str = "") -> str:
    return f'<img class="{cls}" src="{uri}" alt="">' if uri else ""


def _head(b, s: dict) -> str:
    esc = b.esc
    kick = f'<span class="ppkick">{esc(s["kicker"])}</span>' if s.get("kicker") else ""
    bubble = f'<div class="ppbubble">{esc(s["bubble"])}</div>' if s.get("bubble") else ""
    big = ""
    if s.get("big"):
        label = f'<span class="ppbl">{esc(s["big_label"])}</span>' if s.get("big_label") else ""
        big = f'<p class="ppbig">{label}{esc(s["big"])}</p>'
    sub = f'<div class="ppsub"><span>{esc(s["sub"])}</span></div>' if s.get("sub") else ""
    cls = "pphead hasbubble" if bubble else "pphead"
    return (f'<div class="{cls}"><div class="pptop">{kick}</div>'
            f'<div class="ppcard"><h1 class="pptitle">{_title(esc, s["title"])}</h1>{big}</div>{sub}{bubble}</div>')


def _foot(b, s: dict, ask: str) -> str:
    follow = s.get("follow") or b.cfg.get("matome_follow") or "フォローで毎日1枚、見逃さない"
    return (f'<div class="ppfoot"><b>{b.esc(follow)}</b>'
            f'<span>💬 {b.esc(ask)}　｜　🔖 保存して見返そう　｜　{b.handle}</span></div>')


def _frame(b, s: dict, kind: str, inner: str) -> str:
    t = b.cfg["theme"]
    ink = t.get("ink", t["main"])
    hot = t.get("hot", "#e5322d")
    uri = art.bg_uri(s, b.data, b.cfg)
    bg = f'<div class="ppbg" style="background-image:url({uri})"></div>' if uri else '<div class="ppbg none"></div>'
    return (f'<section class="s pp pp-{kind}" style="--ink:{ink};--hot:{hot};--brand:{t["main"]}">{bg}'
            f'<div class="ppwrap">{inner}</div></section>')


def pop(b, i: int, s: dict) -> str:
    esc = b.esc
    head = s.get("head")
    cols = (f'<div class="ppcols"><span>{esc(head[0])}</span><span>{esc(head[1])}</span></div>'
            if isinstance(head, list) and len(head) == 2 else "")
    arrow = '<span class="ppa">→</span>' if s.get("arrow", True) else ""
    # 絵を使う投稿では、絵がまだ無い行も同じ幅をあけて、文字の位置をそろえる
    any_icon = any(art.icon_uri(it.get("icon"), b.cfg) for it in s["items"])
    rows = ""
    for k, it in enumerate(s["items"], 1):
        top = f" top m{k}" if s.get("rank") and k <= 3 else ""
        icon = art.icon_uri(it.get("icon"), b.cfg)
        pic = f'<span class="ppi">{_img(icon)}</span>' if icon else ('<span class="ppi empty"></span>' if any_icon else "")
        sub_l = ""
        if it.get("ng"):
            sub_l = f'<small class="ng"><i>✕</i>{esc(it["ng"])}</small>'
        elif it.get("left_sub"):
            sub_l = f'<small>{esc(it["left_sub"])}</small>'
        sub_r = f'<small>{esc(it["right_sub"])}</small>' if it.get("right_sub") else ""
        rows += (f'<div class="pprow{top}"><span class="ppn">{k}</span>{pic}'
                 f'<div class="ppl"><b>{esc(it["left"])}</b>{sub_l}</div>{arrow}'
                 f'<div class="ppr"><b>{esc(it["right"])}</b>{sub_r}</div></div>')
    note = f'<p class="ppnote">{esc(s["note"])}</p>' if s.get("note") else ""
    lg = _split(s["items"])
    body = f'<div class="pplist fitbox" style="--lg:{lg:.2f};--rg:{1 - lg:.2f}">{cols}{rows}{note}</div>'
    return _frame(b, s, "pop", _head(b, s) + body + _foot(b, s, s.get("ask") or "いくつ知ってた？"))


def tiles(b, i: int, s: dict) -> str:
    esc = b.esc
    cols = int(s.get("cols", 3))
    cells = ""
    for k, t in enumerate(s["tiles"], 1):
        color = TILE_COLORS[(k - 1) % len(TILE_COLORS)]
        icon = art.icon_uri(t.get("icon"), b.cfg)
        pic = f'<div class="pic" style="background-image:url({icon})"></div>' if icon else '<div class="pic none"></div>'
        a = f'<span class="a">{esc(t["a"])}</span>' if t.get("a") else ""
        bb = f'<span class="b">{esc(t["b"])}</span>' if t.get("b") else ""
        cells += (f'<div class="ppt" style="--c:{color}"><h3><i>{k}</i><span>{esc(t["label"])}</span></h3>'
                  f'{pic}{a}{bb}</div>')
    summary = ""
    sm = s.get("summary")
    if isinstance(sm, dict) and sm.get("big"):
        summary = (f'<div class="ppsum"><span>{esc(sm.get("label", ""))}</span>'
                   f'<b>{esc(sm["big"])}</b></div>')
    note = f'<p class="ppnote box">{esc(s["note"])}</p>' if s.get("note") else ""
    body = f'<div class="pptiles fitbox" style="--cols:{cols}">{cells}</div>{summary}{note}'
    return _frame(b, s, "tiles", _head(b, s) + body + _foot(b, s, s.get("ask") or "知ってたのはいくつ？"))


def tier(b, i: int, s: dict) -> str:
    esc = b.esc
    rows = ""
    for t in s["tiers"]:
        rank = str(t.get("rank", ""))
        color = t.get("color") or TIER_COLORS.get(rank[:1].upper(), "#7a8396")
        label = f'<small>{esc(t["label"])}</small>' if t.get("label") else ""
        items = ""
        for it in t.get("items") or []:
            icon = art.icon_uri(it.get("icon"), b.cfg)
            note = f'<small>{esc(it["note"])}</small>' if it.get("note") else ""
            items += f'<div class="ppit">{_img(icon)}<span>{esc(it["name"])}</span>{note}</div>'
        rows += f'<div class="pptr" style="--c:{color}"><div class="rk"><b>{esc(rank)}</b>{label}</div><div class="its">{items}</div></div>'
    note = f'<p class="ppnote box">{esc(s["note"])}</p>' if s.get("note") else ""
    body = f'<div class="pptier fitbox">{rows}</div>{note}'
    return _frame(b, s, "tier", _head(b, s) + body + _foot(b, s, s.get("ask") or "あなたの1位はどれ？"))


MEDALS = ("#f5c400", "#b9c3cd", "#d98b4a")


def podium(b, i: int, s: dict) -> str:
    esc = b.esc
    items = s["items"]
    top = max(float(it.get("num") or 0) for it in items) or 1
    cols = ""
    for k in (2, 1, 3):  # 真ん中が1位
        if k > len(items):
            continue
        it = items[k - 1]
        ratio = float(it.get("num") or 0) / top
        icon = art.icon_uri(it.get("icon"), b.cfg)
        pic = f'<div class="pci">{_img(icon)}</div>' if icon else '<div class="pci none"></div>'
        note = f'<small>{esc(it["note"])}</small>' if it.get("note") else ""
        cols += (f'<div class="pc p{k}" style="--m:{MEDALS[k - 1]};--h:{0.55 + 0.45 * ratio:.3f}">{pic}'
                 f'<b class="pcn">{esc(it["name"])}</b>'
                 f'<div class="step"><i>{k}</i><span class="pcv">{esc(it["value"])}</span>{note}</div></div>')
    bars = ""
    for k, it in enumerate(items[3:], 4):
        ratio = float(it.get("num") or 0) / top
        icon = art.icon_uri(it.get("icon"), b.cfg)
        pic = f'<span class="ppi">{_img(icon)}</span>' if icon else '<span class="ppi empty"></span>'
        note = f'<small>{esc(it["note"])}</small>' if it.get("note") else ""
        bars += (f'<div class="pbr"><span class="ppn">{k}</span>{pic}<div class="pbm">'
                 f'<div class="pbl"><b class="pbn">{esc(it["name"])}</b>{note}</div>'
                 f'<div class="pbt"><i style="width:{max(6.0, 100 * ratio):.1f}%"></i><em>{esc(it["value"])}</em></div>'
                 f'</div></div>')
    note = f'<p class="ppnote">{esc(s["note"])}</p>' if s.get("note") else ""
    body = (f'<div class="pppod fitbox"><div class="podium">{cols}</div>'
            f'<div class="ppbars">{bars}{note}</div></div>')
    return _frame(b, s, "podium", _head(b, s) + body + _foot(b, s, s.get("ask") or "予想は当たった？"))


def bars(b, i: int, s: dict) -> str:
    esc = b.esc
    items = s["items"]
    top = max(float(it.get("num") or 0) for it in items) or 1
    rows = ""
    for k, it in enumerate(items, 1):
        ratio = float(it.get("num") or 0) / top
        icon = art.icon_uri(it.get("icon"), b.cfg)
        pic = f'<span class="ppi">{_img(icon)}</span>' if icon else '<span class="ppi empty"></span>'
        note = f'<small>{esc(it["note"])}</small>' if it.get("note") else ""
        medal = f" top m{k}" if k <= 3 else ""
        rows += (f'<div class="pbr{medal}"><span class="ppn">{k}</span>{pic}<div class="pbm">'
                 f'<div class="pbl"><b class="pbn">{esc(it["name"])}</b>{note}</div>'
                 f'<div class="pbt2"><div class="tr"><i style="width:{max(4.0, 100 * ratio):.1f}%"></i></div>'
                 f'<em>{esc(it["value"])}</em></div></div></div>')
    note = f'<p class="ppnote">{esc(s["note"])}</p>' if s.get("note") else ""
    body = f'<div class="ppbars all fitbox">{rows}{note}</div>'
    return _frame(b, s, "bars", _head(b, s) + body + _foot(b, s, s.get("ask") or "予想は当たった？"))


TREE_COLORS = {"公立": "#2f7de1", "国立": "#2f7de1", "公": "#2f7de1"}


def _man(v: float) -> str:
    return f"{round(v):,}"


def tree(b, i: int, s: dict) -> str:
    """樹形図。routes の共通の前半はまとめて1つの枝にする。座標は Python で計算して SVG の線を引く。"""
    esc = b.esc
    stages, routes = s["stages"], s["routes"]
    n, m = len(stages), len(routes)
    unit = s.get("unit", "万")
    W, colw, left, tot_w = 1000, 140, 6, 260
    xs = [left + k * colw for k in range(n)]
    row_h = 100 / m  # 行の高さ（%）
    nodes, lines = {}, []
    for r, route in enumerate(routes):
        acc = 0.0
        for k, choice in enumerate(route["path"]):
            acc += float(stages[k]["options"][choice])
            key = tuple(route["path"][: k + 1])
            if key not in nodes:
                nodes[key] = {"row": r, "k": k, "label": choice, "acc": acc}
                if k:
                    parent = nodes[tuple(route["path"][:k])]
                    lines.append((parent["k"], parent["row"], k, r))
        route["_total"] = acc
    y = lambda row: (row + 0.5) * row_h
    svg = "".join(
        f'<path d="M{xs[k0] + 62} {y(r0):.2f} V{y(r1):.2f} H{xs[k1]}" />' if r0 != r1 else
        f'<path d="M{xs[k0] + 62} {y(r0):.2f} H{xs[k1]}" />' for k0, r0, k1, r1 in lines)
    svg += "".join(f'<path d="M{xs[n - 1] + 124} {y(r):.2f} H{W - tot_w + 6}" class="dash" />' for r in range(m))
    divs = ""
    for node in nodes.values():
        pub = node["label"] in TREE_COLORS
        divs += (f'<div class="tn {"pub" if pub else "pri"}" style="left:{xs[node["k"]] / W * 100:.2f}%;top:{y(node["row"]):.2f}%">'
                 f'<b>{esc(node["label"])}</b><small>{_man(node["acc"])}{unit}</small></div>')
    top = max(r["_total"] for r in routes)
    for r, route in enumerate(routes):
        hot = " max" if route["_total"] == top else ""
        divs += (f'<div class="tt{hot}" style="top:{y(r):.2f}%"><small>{esc(route.get("name", ""))}</small>'
                 f'<b>{_man(route["_total"])}<i>{unit}円</i></b></div>')
    heads = "".join(f'<span style="left:{xs[k] / W * 100:.2f}%">{esc(st["name"])}<small>{esc(st.get("years", ""))}</small></span>'
                    for k, st in enumerate(stages))
    heads += '<span class="th" style="right:0">総額</span>'
    note = f'<p class="ppnote">{esc(s["note"])}</p>' if s.get("note") else ""
    legend = '<div class="tlg"><span class="pub">公立・国立</span><span class="pri">私立</span><em>数字はそこまでの累計</em></div>'
    body = (f'<div class="pptree fitbox"><div class="tgrid">{heads}</div>{legend}'
            f'<div class="tbox"><svg viewBox="0 0 {W} 100" preserveAspectRatio="none">{svg}</svg>{divs}</div>{note}</div>')
    return _frame(b, s, "tree", _head(b, s) + body + _foot(b, s, s.get("ask") or "うちはどのルート？"))

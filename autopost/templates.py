"""投稿データ（post.json）からスライドのHTMLを組み立てる。

スライドの種類（layout）:
  cover   表紙（濃い背景）。top / ng / bottom / sub
  callout よくある間違い・ポイントを大きなカードで。label / title / body / note / style(ng|ok)
  cards   フレーズや項目のカード（1〜3個）。title / cards[[大きい文字, 小さい文字]] / note
  points  箇条書き（1〜6個）。title / points / note / numbered
  table   まとめ早見表（1〜6行）。title / rows[[左, 右]]
  quiz    復習クイズ＋フォローの呼びかけ。question / answer / cta / button
  cta     コメント募集などの締め。title / body / cta / button
どのスライドも tag（左上の小見出し）を指定できる。
"""
from __future__ import annotations

import html
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent / "style.css").read_text(encoding="utf-8")
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"

# 投稿データの中で使ってよいHTMLタグ（それ以外は文字としてそのまま表示する）
_ALLOWED = {
    "<br>": "<br>",
    "<br/>": "<br>",
    "<br />": "<br>",
    "<b>": "<b>",
    "</b>": "</b>",
    '<span class="hl">': '<span class="hl">',
    "</span>": "</span>",
    "<small>": "<small>",
    "</small>": "</small>",
}
_TAG_RE = re.compile("|".join(re.escape(html.escape(k)) for k in sorted(_ALLOWED, key=len, reverse=True)))
_UNESCAPE = {html.escape(k): v for k, v in _ALLOWED.items()}


def esc(text) -> str:
    """文字をHTMLとして安全にする（許可したタグと改行だけ活かす）。"""
    if text is None:
        return ""
    out = html.escape(str(text))
    out = _TAG_RE.sub(lambda m: _UNESCAPE[m.group(0)], out)
    return out.replace("\n", "<br>")


def _pair(item) -> tuple[str, str]:
    if isinstance(item, dict):
        return item.get("main", ""), item.get("sub", "")
    if isinstance(item, (list, tuple)):
        return (item[0] if item else ""), (item[1] if len(item) > 1 else "")
    return str(item), ""


class _Builder:
    def __init__(self, data: dict, cfg: dict):
        self.data = data
        self.cfg = cfg
        self.handle = esc(cfg["display_handle"])
        self.n = len(data["slides"])
        self.scene = 0

    def frame(self, i: int, cls: str, tag: str, inner: str, foot_right: str = "→", foot: bool = True) -> str:
        pg = f'<div class="pg">{i}/{self.n}</div>' if i > 1 else ""
        pr = '<div class="prmark">PR</div>' if (i == 1 and self.data.get("pr")) else ""
        ft = f'<div class="foot"><span>{self.handle}</span><span>{foot_right}</span></div>' if foot else ""
        return f'<section class="s {cls}"><div class="tag">{tag}</div>{pg}{pr}<div class="body">{inner}</div>{ft}</section>'

    def note(self, s: dict) -> str:
        return f'<p class="note">{esc(s["note"])}</p>' if s.get("note") else ""

    def cover(self, i: int, s: dict) -> str:
        series, no = self.cfg.get("series", ""), self.data.get("no")
        default_tag = f"{series} #{no}" if series and no else series
        inner = f'<h1 style="font-size:{int(s.get("top_size", 104))}px">{esc(s["top"])}</h1>'
        if s.get("ng"):
            inner += (
                '<div class="ngbig"><span class="x">✕</span>'
                f'<span class="strike" style="font-size:{int(s.get("ng_size", 92))}px">{esc(s["ng"])}</span></div>'
            )
        if s.get("bottom"):
            inner += f'<h1 style="font-size:92px">{esc(s["bottom"])}</h1>'
        if s.get("sub"):
            inner += f'<p class="sub">{esc(s["sub"])}</p>'
        return self.frame(i, "cover", esc(s.get("tag", default_tag)), inner, "スワイプ →")

    def callout(self, i: int, s: dict) -> str:
        style = s.get("style", "ng")
        label = s.get("label") or ("✕ よくある間違い" if style == "ng" else "◎ 正解")
        tag = s.get("tag") or ("なぜNG？" if style == "ng" else "ポイント")
        body = f'<div class="ja">{esc(s["body"])}</div>' if s.get("body") else ""
        inner = (
            f'<div class="card callout {esc(style)}"><div class="lbl">{esc(label)}</div>'
            f'<div class="en">{esc(s["title"])}</div>{body}</div>{self.note(s)}'
        )
        return self.frame(i, "", esc(tag), inner)

    def cards(self, i: int, s: dict) -> str:
        self.scene += 1
        tag = s.get("tag") or f"場面{CIRCLED[min(self.scene, len(CIRCLED)) - 1]}"
        cards = ""
        for item in s["cards"]:
            main, sub = _pair(item)
            sub_html = f'<div class="ja">{esc(sub)}</div>' if sub else ""
            cards += f'<div class="card"><div class="en">{esc(main)}</div>{sub_html}</div>'
        inner = f'<h2>{esc(s["title"])}</h2>{cards}{self.note(s)}'
        return self.frame(i, "", esc(tag), inner)

    def points(self, i: int, s: dict) -> str:
        cls = "points numbered" if s.get("numbered") else "points"
        items = "".join(f"<li>{esc(p)}</li>" for p in s["points"])
        inner = f'<h2>{esc(s["title"])}</h2><ul class="{cls}">{items}</ul>{self.note(s)}'
        return self.frame(i, "", esc(s.get("tag", "ポイント")), inner)

    def table(self, i: int, s: dict) -> str:
        rows = "".join(f"<tr><td>{esc(_pair(r)[0])}</td><td>{esc(_pair(r)[1])}</td></tr>" for r in s["rows"])
        inner = f'<h2>{esc(s["title"])}</h2><table>{rows}</table>'
        return self.frame(i, "", esc(s.get("tag", "まとめ")), inner, esc(s.get("foot", "📌 保存してね")))

    def quiz(self, i: int, s: dict) -> str:
        answer = s.get("answer", "答えはコメントで！")
        cta = s.get("cta", "📌 保存して、明日さっそく使おう<br>👤 毎日投稿中")
        button = s.get("button", f'{self.cfg["display_handle"]} をフォロー')
        inner = (
            f'<div class="quiz"><div class="lbl">Q.</div><p>{esc(s["question"])}</p>'
            f'<div class="ans">{esc(answer)}</div></div>'
            f'<p class="cta">{esc(cta)}</p><div><span class="btn">{esc(button)}</span></div>'
        )
        return self.frame(i, "", esc(s.get("tag", "復習クイズ")), inner, foot=False)

    def cta(self, i: int, s: dict) -> str:
        body = f'<p class="lead">{esc(s["body"])}</p>' if s.get("body") else ""
        cta = f'<p class="cta">{esc(s["cta"])}</p>' if s.get("cta") else ""
        button = s.get("button", f'{self.cfg["display_handle"]} をフォロー')
        inner = f'<h2>{esc(s["title"])}</h2>{body}{cta}<div><span class="btn">{esc(button)}</span></div>'
        return self.frame(i, "", esc(s.get("tag", "最後に")), inner, foot=False)


LAYOUTS = ("cover", "callout", "cards", "points", "table", "quiz", "cta")


def build_html(data: dict, cfg: dict) -> str:
    b = _Builder(data, cfg)
    sections = [getattr(b, s["layout"])(i, s) for i, s in enumerate(data["slides"], 1)]
    t = cfg["theme"]
    css_vars = (
        f':root{{--main:{t["main"]};--base:{t["base"]};--accent:{t["accent"]};'
        f'--accent-soft:{t["accent_soft"]};--muted:{t["muted"]}}}'
    )
    return (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">'
        f"<style>{css_vars}{CSS}</style></head><body>{''.join(sections)}</body></html>"
    )

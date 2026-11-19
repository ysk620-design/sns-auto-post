"""新しい投稿を、ストーリーズでもお知らせする画像（story.jpg、1080×1920）を作る。

カルーセルを投稿したあとに、表紙をストーリーズに流す（accounts/<アカウント>.json の "story_share" を false にすると止まる）。
ストーリーズはフォロワーの画面の一番上に出るので、投稿を見てもらうきっかけになる。
APIではリンクのスタンプは付けられないので、画像の中で「プロフィールから見てね」と案内する。
"""
from __future__ import annotations

from pathlib import Path

W, H = 1080, 1920
DEFAULT_BG = "#1d3c32"


def wanted(cfg: dict) -> bool:
    return cfg.get("story_share", True) is not False


def make_story_image(cover: Path, out: Path, handle: str, theme: dict | None = None) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    from PIL import ImageFont

    from .reel import find_font

    theme = theme or {}
    bg_color = theme.get("main", DEFAULT_BG)
    accent = theme.get("accent_soft", "#ffe14d")
    font_path = find_font()

    with Image.open(cover) as im:
        im = im.convert("RGB")
        # 背景：表紙をぼかして暗くしたもの（色はアカウントのテーマに寄せる）
        bg = im.resize((W, int(im.height * W / im.width))).resize((W, H)).filter(ImageFilter.GaussianBlur(40))
        bg = Image.blend(bg, Image.new("RGB", (W, H), bg_color), 0.55)
        cw = 900
        card = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS)
    x, y = (W - cw) // 2, 410  # 上の200pxほどはストーリーズの名前などが重なるので空ける
    shadow = Image.new("RGB", (cw, card.height), "#000")
    bg.paste(Image.blend(bg.crop((x + 14, y + 18, x + 14 + cw, y + 18 + card.height)), shadow, 0.45), (x + 14, y + 18))
    bg.paste(card, (x, y))

    d = ImageDraw.Draw(bg)
    f_top = ImageFont.truetype(font_path, 64, index=0)
    f_bot = ImageFont.truetype(font_path, 48, index=0)
    f_h = ImageFont.truetype(font_path, 40, index=0)
    top = "新しい投稿をアップしました"
    tw = d.textlength(top, font=f_top)
    pad = 36
    d.rounded_rectangle(((W - tw) / 2 - pad, 250, (W + tw) / 2 + pad, 350), radius=50, fill=accent)
    d.text((W / 2, 300), top, font=f_top, fill=bg_color if accent.lower() != bg_color.lower() else "#111", anchor="mm")
    by = y + card.height + 90
    d.text((W / 2, by), "▶ プロフィールから見てね", font=f_bot, fill="#ffffff", anchor="mm")
    d.text((W / 2, by + 80), handle, font=f_h, fill=(255, 255, 255, 200), anchor="mm")
    bg.save(out, quality=90)
    return out

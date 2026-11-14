"""スライド画像からリール動画（1080×1920・BGM付き・12〜15秒）を作る。

最初に全画面のつかみ画面、そのあと上に固定タイトル、その下でスライドが横に切り替わる形。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

W, H = 1080, 1920
TOP = 240  # 上の固定タイトルの高さ
FADE = 0.25  # スライドの切り替えにかける秒数


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # pip の imageio-ffmpeg に入っている ffmpeg を使う

    return imageio_ffmpeg.get_ffmpeg_exe()


def find_font() -> str:
    candidates = []
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", "Noto Sans CJK JP:bold"], capture_output=True, text=True)
        candidates.append(out.stdout.strip())
    except FileNotFoundError:
        pass
    candidates += ["~/.local/share/fonts/NotoSansCJKjp-Bold.otf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]
    for c in candidates:
        if c and Path(c).expanduser().exists() and re.search(r"CJK", c):
            return str(Path(c).expanduser())
    raise RuntimeError("日本語フォント（Noto Sans CJK JP）が見つかりません")


HOOK = 1.6  # 最初のつかみ画面の秒数


def durations(n: int) -> list[float]:
    """表紙のあとの各スライドの表示秒数（表紙はつかみ画面に置きかえるので数に入れない）。

    全体で12〜15秒くらいに収める。最後まで見てもらうこと（と繰り返し再生）を優先する。
    """
    if n <= 1:
        return [3.0] * n
    return [2.3] + [2.0] * (n - 3) + [2.6, 1.8] if n >= 3 else [2.3, 1.8]


def default_title(data: dict) -> str:
    """reel_title が無いときの上部タイトル（キャプションの1行目）。"""
    first = str(data.get("caption", "")).strip().splitlines()[0] if data.get("caption") else ""
    return first[:24]


def _fit_font(draw, text: str, path: str, size: int, min_size: int, max_width: int):
    from PIL import ImageFont

    while True:
        font = ImageFont.truetype(path, size, index=0)
        if draw.textlength(text, font=font) <= max_width or size <= min_size:
            return font
        size -= 2


def _plain(text) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(text or ""), flags=re.I)
    return re.sub(r"<[^>]+>", "", text).strip()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if line and draw.textlength(line + ch, font=font) > max_width:
                lines.append(line)
                line = ""
            line += ch
        if line:
            lines.append(line)
    return lines


def hook_frame(data: dict, title: str, theme: dict, font_path: str, out: Path) -> None:
    """最初の1.6秒に見せる、全画面のつかみ画面。表紙の言葉を大きく見せて「続きが気になる」形にする。"""
    from PIL import Image, ImageDraw, ImageFont

    cover = next((s for s in data.get("slides", []) if s.get("layout") == "cover"), {})
    parts = []  # (文字, 大きさ, 色, 前の余白)
    if cover.get("kicker"):
        parts.append((_plain(cover["kicker"]), 64, theme["accent_soft"], 0))
    parts.append((_plain(cover.get("top")) or title, 112, "#ffffff", 20))
    if cover.get("ng"):
        parts.append(("× " + _plain(cover["ng"]), 124, theme["accent"], 40))
    if cover.get("bottom"):
        parts.append((_plain(cover["bottom"]), 104, "#ffffff", 30))
    if cover.get("big"):
        parts.append((_plain(cover["big"]).replace("\n", ""), 230, theme["accent_soft"], 40))
    parts.append(("正解はこのあと ▼" if cover.get("ng") else "くわしくはこのあと ▼", 60, theme["muted"], 80))

    img = Image.new("RGB", (W, H), theme["main"])
    draw = ImageDraw.Draw(img)
    # 改行は表紙のとおり（<br>の位置）にして、はみ出す行は文字を小さくして1行に収める
    for scale in [x / 100 for x in range(100, 40, -5)]:  # 全体が画面に収まるまで小さくする
        blocks, total = [], 0
        for text, size, color, gap in parts:
            lines = [ln for ln in text.split("\n") if ln.strip()] or [""]
            px = int(size * scale)
            while px > 30:
                font = ImageFont.truetype(font_path, px, index=0)
                if max(draw.textlength(ln, font=font) for ln in lines) <= W - 100:
                    break
                px -= 4
            lh = int(px * 1.3)
            blocks.append((lines, font, color, int(gap * scale), lh))
            total += int(gap * scale) + lh * len(lines)
        if total <= H - 360:
            break
    y = (H - total) // 2
    for lines, font, color, gap, lh in blocks:
        y += gap
        for line in lines:
            draw.text((W // 2, y + lh // 2), line, font=font, fill=color, anchor="mm")
            y += lh
    img.save(out)


def _bgm(total: float, out: Path, volume: float = 0.5) -> bool:
    """オリジナルのBGM（自作なので著作権の心配なし）を書き出す。numpy などが無ければ無音にする。"""
    try:
        import numpy as np
        from scipy.io import wavfile

        from .story.bgm import SR, make_bgm
    except ImportError:
        return False
    mix = make_bgm(total)[: int(SR * total)] * volume
    fade = int(SR * 0.8)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    wavfile.write(out, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    return True


def make_reel(folder: Path, title: str, subtitle: str, theme: dict, out_path: Path, data: dict | None = None) -> Path:
    """つかみ画面（1.6秒）→ 表紙以外のスライドを短めに切り替え → BGM付き、の12〜15秒のリールを作る。"""
    import json

    from PIL import Image, ImageDraw

    slides = sorted(Path(folder).glob("slide*.jpg"))
    if not slides:
        raise RuntimeError("スライド画像がありません")
    if data is None:
        data = json.loads((Path(folder) / "post.json").read_text(encoding="utf-8"))
    body = slides[1:] if len(slides) > 1 else slides
    durs = [HOOK] + durations(len(body))
    font_path = find_font()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        frames = [tmpdir / "f00.png"]
        hook_frame(data, title, theme, font_path, frames[0])
        for i, path in enumerate(body, 1):
            canvas = Image.new("RGB", (W, H), theme["main"])
            with Image.open(path) as im:
                canvas.paste(im.convert("RGB").resize((W, 1350)), (0, TOP))
            frame = tmpdir / f"f{i:02d}.png"
            canvas.save(frame)
            frames.append(frame)

        banner = Image.new("RGBA", (W, TOP), theme["main"])
        draw = ImageDraw.Draw(banner)
        title_font = _fit_font(draw, title, font_path, 50, 34, W - 80)
        draw.text((W // 2, 110), title, font=title_font, fill="#ffffff", anchor="mm")
        if subtitle:
            sub_font = _fit_font(draw, subtitle, font_path, 34, 26, W - 80)
            draw.text((W // 2, 180), subtitle, font=sub_font, fill=theme["accent_soft"], anchor="mm")
        banner_path = tmpdir / "banner.png"
        banner.save(banner_path)

        k = len(frames)
        total = sum(durs) - FADE * (k - 1)
        music = tmpdir / "bgm.wav"
        args = [ffmpeg_exe(), "-y", "-loglevel", "error"]
        for frame, dur in zip(frames, durs):
            args += ["-loop", "1", "-t", str(dur), "-i", str(frame)]
        if _bgm(total + 0.5, music):
            args += ["-i", str(music)]
        else:
            args += ["-f", "lavfi", "-t", "120", "-i", "anullsrc=r=44100:cl=stereo"]
        args += ["-i", str(banner_path)]
        filters, prev, offset = [], "0:v", 0.0
        for i in range(1, k):
            offset += durs[i - 1] - FADE
            filters.append(f"[{prev}][{i}:v]xfade=transition=slideleft:duration={FADE}:offset={offset:.2f}[v{i}]")
            prev = f"v{i}"
        # 上のタイトル帯は、つかみ画面のあとから出す
        filters.append(f"[{prev}][{k + 1}:v]overlay=0:0:enable='gte(t,{HOOK - FADE:.2f})',format=yuv420p,fps=30[vout]")
        args += [
            "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", f"{k}:a", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(out_path),
        ]
        subprocess.run(args, check=True)
    return Path(out_path)


def main(argv=None) -> int:
    """確認用: python -m autopost.reel <投稿フォルダ> <出力.mp4>"""
    import argparse

    from . import config, posts

    ap = argparse.ArgumentParser(description="投稿フォルダからリール動画を作る（確認用）")
    ap.add_argument("folder")
    ap.add_argument("out")
    args = ap.parse_args(argv)
    post = posts.Post.load(Path(args.folder))
    cfg = config.load_accounts()[post.account]
    title = post.data.get("reel_title") or default_title(post.data)
    make_reel(post.folder, title, (cfg.get("reel") or {}).get("subtitle", ""), cfg["theme"], Path(args.out), post.data)
    print(f"🎬 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

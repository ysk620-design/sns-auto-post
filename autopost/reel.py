"""スライド画像からリール動画（1080×1920・無音）を作る。

上に固定タイトル、その下でスライドが横に切り替わる形。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

W, H = 1080, 1920
TOP = 240  # 上の固定タイトルの高さ
FADE = 0.4  # スライドの切り替えにかける秒数


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


def durations(n: int) -> list[float]:
    """各スライドの表示秒数。表紙は短め、最後の2枚（まとめ・締め）は長め。"""
    if n <= 2:
        return [3.5] * n
    return [2.5] + [4.0] * (n - 3) + [4.5, 3.5]


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


def make_reel(folder: Path, title: str, subtitle: str, theme: dict, out_path: Path) -> Path:
    from PIL import Image, ImageDraw

    slides = sorted(Path(folder).glob("slide*.jpg"))
    if not slides:
        raise RuntimeError("スライド画像がありません")
    durs = durations(len(slides))
    font_path = find_font()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        frames = []
        for i, path in enumerate(slides, 1):
            canvas = Image.new("RGB", (W, H), theme["main"])
            with Image.open(path) as im:
                canvas.paste(im.convert("RGB").resize((W, 1350)), (0, TOP))
            if i == 1:  # 表紙右下の「スワイプ →」はリールでは不要なので隠す
                ImageDraw.Draw(canvas).rectangle((600, TOP + 1235, 1040, TOP + 1310), fill=theme["main"])
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

        args = [ffmpeg_exe(), "-y", "-loglevel", "error"]
        for frame, dur in zip(frames, durs):
            args += ["-loop", "1", "-t", str(dur), "-i", str(frame)]
        k = len(frames)
        args += ["-f", "lavfi", "-t", "120", "-i", "anullsrc=r=44100:cl=stereo", "-i", str(banner_path)]
        filters, prev, offset = [], "0:v", 0.0
        for i in range(1, k):
            offset += durs[i - 1] - FADE
            filters.append(f"[{prev}][{i}:v]xfade=transition=slideleft:duration={FADE}:offset={offset:.2f}[v{i}]")
            prev = f"v{i}"
        filters.append(f"[{prev}][{k + 1}:v]overlay=0:0,format=yuv420p,fps=30[vout]")
        total = sum(durs) - FADE * (k - 1)
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
    make_reel(post.folder, title, (cfg.get("reel") or {}).get("subtitle", ""), cfg["theme"], Path(args.out))
    print(f"🎬 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

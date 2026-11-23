"""Gemini の画像生成で、1枚まとめに入れるイラストと背景を作る。

- APIキーは GitHub のシークレット GEMINI_API_KEY（環境変数）からだけ読む。ファイルやログには出さない
- 画像の中に文字を書かせると崩れやすいので、絵だけを作らせる（文字はテンプレート側で上に載せる）
- アイコンは1回の呼び出しで最大12個をまとめて描かせ（シート）、切り分けて使う。
  1個ずつ頼むより安く、タッチもそろう
- キーが無いときや失敗したときは None を返す（呼び出し側は絵なしで作る）

試しに作る:  python -m autopost.imagegen --test <出力フォルダ>
"""
from __future__ import annotations

import base64
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"
# 用途ごとのモデル（上から順に試す）
MODELS = {
    "icons": ["gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image"],
    # 漫画は人物をそろえる力と画力が大事なので、上位モデルから試す
    "comic": ["gemini-3-pro-image", "gemini-nano-banana-2.1"],
    # 背景は使い回すので、ぼかしの指示をよく守る上位モデルで作る
    "background": ["gemini-3-pro-image", "gemini-nano-banana-2.1", "gemini-3.1-flash-image"],
}
NO_TEXT = " Absolutely no text, letters, numbers, signs, logos or watermarks anywhere in the image."

# タッチ（アイコン）
ICON_STYLES = {
    "clay": ("cute 3D clay render, soft studio lighting, smooth rounded shapes, pastel colors, playful and friendly, "
             "high quality, each object with a small soft contact shadow"),
    "anime": "bright cheerful anime-style illustration, clean lines, soft colors",
    "flat": "flat vector illustration, bold simple shapes, pastel colors",
}
# 背景（写真風・ぼかし）
BG_STYLE = ("Realistic photograph, vertical composition, shot with a wide aperture so the whole scene is softly out "
            "of focus with gentle bokeh, bright and airy natural light, inviting colors, no people.")

# 並べ方（個数の上限, 列, 行, 縦横比）
GRIDS = [(4, 2, 2, "1:1"), (6, 3, 2, "3:2"), (9, 3, 3, "1:1"), (12, 4, 3, "4:3")]
SHEET_MAX = 12


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _post(url: str, body: dict, key: str, timeout: int = 180) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # 通信エラー
        return 0, {"error": {"status": "NETWORK", "message": str(e)[:200]}}


def _find_image(obj) -> bytes | None:
    """返ってきたJSONの中から、画像（base64）を探す。API の形が変わっても拾えるように深く探す。"""
    if isinstance(obj, dict):
        mime = obj.get("mime_type") or obj.get("mimeType") or ""
        data = obj.get("data")
        if isinstance(data, str) and len(data) > 1000 and (mime.startswith("image/") or not mime):
            try:
                return base64.b64decode(data)
            except Exception:
                pass
        for v in obj.values():
            found = _find_image(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_image(v)
            if found:
                return found
    return None


def _error_text(res: dict) -> str:
    err = res.get("error") if isinstance(res, dict) else None
    if isinstance(err, dict):
        return f'{err.get("status", "")} {err.get("message", "")}'[:300]
    return json.dumps(list(res.keys()) if isinstance(res, dict) else res)[:300]


def generate(prompt: str, out_path: Path, aspect: str = "1:1", size: str = "1K", kind: str = "icons",
             models: list[str] | None = None, log=print) -> Path | None:
    """prompt の絵を out_path に保存する。うまくいかなければ None。"""
    key = api_key()
    if not key:
        log("  GEMINI_API_KEY が無いので、絵は作りません")
        return None
    text = prompt.strip() + NO_TEXT
    for model in models or MODELS.get(kind, MODELS["icons"]):
        want = size
        for attempt in range(3):
            size = want
            status, res = _post(f"{API}/interactions", {
                "model": model, "input": text,
                "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect,
                                    "image_size": size},
            }, key)
            img = _find_image(res) if status == 200 else None
            how = "interactions"
            if img is None:
                log(f"  {model}（interactions）: {status} {_error_text(res)}")
                status, res = _post(f"{API}/models/{model}:generateContent", {
                    "contents": [{"parts": [{"text": text}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"],
                                         "imageConfig": {"aspectRatio": aspect, "imageSize": size}},
                }, key)
                img = _find_image(res) if status == 200 else None
                how = "generateContent"
                if img is None:
                    log(f"  {model}（generateContent）: {status} {_error_text(res)}")
            if img is not None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(img)
                log(f"  ✅ {model}（{how}）→ {out_path.name}（{len(img) // 1024}KB）")
                return out_path
            if status == 400 and "size" in _error_text(res).lower() and want != "1K":
                want = "1K"  # この大きさに対応していないモデルは、1K でやり直す
                continue
            if status in (429, 500, 503, 0) and attempt == 0:
                time.sleep(8)  # 混雑・一時的な失敗は少し待って1回だけやり直す
                continue
            break
    return None


# ---------- アイコンのシート ----------

def grid_for(count: int) -> tuple[int, int, str]:
    for limit, cols, rows, aspect in GRIDS:
        if count <= limit:
            return cols, rows, aspect
    raise ValueError(f"1枚のシートに描けるのは{SHEET_MAX}個までです")


def sheet_prompt(subjects: list[str], style: str = "clay") -> tuple[str, int, int, str]:
    cols, rows, aspect = grid_for(len(subjects))
    look = ICON_STYLES.get(style, style)
    lines = [f"{i}. {s.strip().rstrip('.')}" for i, s in enumerate(subjects, 1)]
    empty = cols * rows - len(subjects)
    prompt = (
        f"A sprite sheet of {len(subjects)} separate small illustrations arranged in an invisible grid of "
        f"{cols} columns and {rows} rows on a plain pure white background. "
        "Each item sits alone in the center of its own cell, fully inside the cell, with wide empty white space "
        "around it; items never touch or overlap each other and there are no grid lines, frames or borders. "
        f"Every item is drawn in the same style: {look}. "
        "Items in reading order (left to right, then top to bottom):\n" + "\n".join(lines)
    )
    if empty:
        prompt += f"\nLeave the last {empty} cell(s) completely empty and white."
    return prompt, cols, rows, aspect


def slice_sheet(sheet: Path, count: int, cols: int, rows: int, size: int = 360) -> list:
    """シート画像を切り分けて、PIL の画像のリストを返す（見つからない所は None）。"""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    img = Image.open(sheet).convert("RGB")
    arr = np.asarray(img).astype(np.int16)
    H, W = arr.shape[:2]
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bg = np.median(border, axis=0)
    mask = np.abs(arr - bg).max(axis=2) > 26
    mask = ndimage.binary_opening(mask, iterations=2)
    grow = max(2, int(min(H, W) * 0.008))
    lab, _ = ndimage.label(ndimage.binary_dilation(mask, iterations=grow))
    cw, ch = W / cols, H / rows
    boxes: dict[int, list[int]] = {}
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        area = int((lab[sl] == i).sum())
        if area < H * W * 0.002:
            continue  # ゴミ
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        cell = int((y0 + y1) / 2 // ch) * cols + int((x0 + x1) / 2 // cw)
        b = boxes.setdefault(cell, [x0, y0, x1, y1])
        b[0], b[1], b[2], b[3] = min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)
    out = []
    for idx in range(count):
        r, c = divmod(idx, cols)
        cx0, cy0, cx1, cy1 = int(c * cw), int(r * ch), int((c + 1) * cw), int((r + 1) * ch)
        box = boxes.get(idx)
        if box is None:
            # かたまりが見つからないときは、マスの中の色のある所を切り出す
            inset = int(min(cw, ch) * 0.03)
            sub = mask[cy0 + inset:cy1 - inset, cx0 + inset:cx1 - inset]
            ys, xs = np.nonzero(sub)
            if len(xs) < 50:
                out.append(None)
                continue
            box = [cx0 + inset + xs.min(), cy0 + inset + ys.min(), cx0 + inset + xs.max(), cy0 + inset + ys.max()]
        # となりのマスに大きくはみ出したものは、マスの範囲で切る
        x0 = max(box[0], cx0 - int(cw * 0.15))
        y0 = max(box[1], cy0 - int(ch * 0.15))
        x1 = min(box[2], cx1 + int(cw * 0.15))
        y1 = min(box[3], cy1 + int(ch * 0.15))
        side = max(x1 - x0, y1 - y0)
        pad = int(side * 0.08)
        side += pad * 2
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        canvas = Image.new("RGB", (side, side), tuple(int(v) for v in bg))
        left, top = mx - side // 2, my - side // 2
        crop = img.crop((max(0, left), max(0, top), min(W, left + side), min(H, top + side)))
        canvas.paste(crop, (max(0, -left), max(0, -top)))
        out.append(canvas.resize((size, size), Image.LANCZOS))
    return out


def generate_icons(subjects: list[str], out_paths: list[Path], style: str = "clay", models: list[str] | None = None,
                   keep_sheet: Path | None = None, log=print) -> int:
    """subjects の絵をまとめて作り、out_paths（JPEG）に保存する。できた数を返す。"""
    import tempfile

    done = 0
    for start in range(0, len(subjects), SHEET_MAX):
        part = subjects[start:start + SHEET_MAX]
        paths = out_paths[start:start + SHEET_MAX]
        prompt, cols, rows, aspect = sheet_prompt(part, style)
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.jpg"
            if not generate(prompt, sheet, aspect=aspect, size="2K", kind="icons", models=models, log=log):
                continue
            if keep_sheet:
                keep_sheet.parent.mkdir(parents=True, exist_ok=True)
                keep_sheet.write_bytes(sheet.read_bytes())
            pieces = slice_sheet(sheet, len(part), cols, rows)
        for piece, path in zip(pieces, paths):
            if piece is None:
                log(f"  ⚠️ 切り出せませんでした: {path.name}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            piece.save(path, quality=90)
            done += 1
    return done


def generate_background(description: str, out_path: Path, models: list[str] | None = None, log=print) -> Path | None:
    """写真風のぼかした背景（縦長 1080×1920）を作る。"""
    import tempfile

    from PIL import Image

    prompt = f"{description.strip().rstrip('.')}. {BG_STYLE}"
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "bg.jpg"
        if not generate(prompt, raw, aspect="9:16", size="2K", kind="background", models=models, log=log):
            return None
        img = Image.open(raw).convert("RGB")
        # 1080×1920 にそろえる（縦横比が少し違っても中央で切る）
        w, h = img.size
        scale = max(1080 / w, 1920 / h)
        img = img.resize((math.ceil(w * scale), math.ceil(h * scale)), Image.LANCZOS)
        w, h = img.size
        img = img.crop(((w - 1080) // 2, (h - 1920) // 2, (w - 1080) // 2 + 1080, (h - 1920) // 2 + 1920))
        # ぼかしが弱いと文字の邪魔になるので、念のため少しぼかす
        from PIL import ImageFilter
        img = img.filter(ImageFilter.GaussianBlur(radius=5))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, quality=86)
    return out_path


# ---------- 漫画のシート（海外反応のストーリー） ----------

COMIC_STYLE = ("full-color modern webtoon comic illustration, clean bold black outlines, bright flat colors with soft "
               "cel shading, cute expressive characters with big easy-to-read facial expressions, warm wholesome mood")
COMIC_COLS, COMIC_ROWS = 2, 3  # 6コマ（表紙・場面4つ・締め）。1コマ 3:2 で、全体は正方形
COMIC_SLOTS = ("top-left", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-right")
COMIC_ROLES = ("title panel, the most eye-catching moment", "scene 1", "scene 2", "scene 3", "scene 4",
               "happy ending")


def comic_prompt(cast: str, panels: list[str], style: str = "") -> str:
    lines = [f"Panel {i} ({COMIC_SLOTS[i - 1]}, {COMIC_ROLES[i - 1]}): {d.strip().rstrip('.')}."
             for i, d in enumerate(panels, 1)]
    return (
        f"A comic page laid out as a strict grid of {COMIC_COLS} columns and {COMIC_ROWS} rows: exactly "
        f"{len(panels)} equal rectangular panels, each wider than tall (3:2), each with a thin black border, "
        "separated by plain white gutters of equal width. No panel spans more than one cell. "
        f"Art style for every panel: {style or COMIC_STYLE}. "
        "Recurring characters, drawn exactly the same (same face, hairstyle, skin tone and clothes) in every panel "
        f"they appear in: {cast.strip().rstrip('.')}. "
        "In every panel, leave the top third as simple background (plain wall, ceiling or sky) because a speech "
        "bubble will be added there later; keep faces in the middle of the panel, below the top third. "
        "Do not draw speech bubbles, captions or sound effects. Do not depict any real, identifiable person or "
        "brand.\n" + "\n".join(lines)
    )


def _split_at(profile, expected: float, span: float) -> int:
    """白いすき間（ガター）のいちばんそれらしい位置。"""
    lo, hi = max(1, int(expected - span)), min(len(profile) - 1, int(expected + span))
    seg = profile[lo:hi]
    good = seg >= seg.max() - 0.02
    runs, start = [], None
    for i, g in enumerate(good):
        if g and start is None:
            start = i
        if (not g or i == len(good) - 1) and start is not None:
            runs.append((start, i if not g else i + 1))
            start = None
    best = min(runs, key=lambda r: abs((lo + (r[0] + r[1]) / 2) - expected))
    return int(lo + (best[0] + best[1]) / 2)


def slice_grid(sheet: Path, cols: int, rows: int, max_w: int = 1200) -> list:
    """コマ割りの画像を、白いすき間を手がかりに切り分ける。枠線は少し内側で切って落とす。
    すき間が見つからない（コマ割りが違う）ときは空のリストを返す。"""
    import numpy as np
    from PIL import Image

    img = Image.open(sheet).convert("RGB")
    W, H = img.size
    white = np.asarray(img.convert("L")) > 232
    col_p, row_p = white.mean(axis=0), white.mean(axis=1)
    xs = [0] + [_split_at(col_p, W * k / cols, W * 0.08) for k in range(1, cols)] + [W]
    ys = [0] + [_split_at(row_p, H * k / rows, H * 0.08) for k in range(1, rows)] + [H]
    if any(col_p[x] < 0.85 for x in xs[1:-1]) or any(row_p[y] < 0.85 for y in ys[1:-1]):
        return []
    out = []
    for r in range(rows):
        for c in range(cols):
            cell = img.crop((xs[c], ys[r], xs[c + 1], ys[r + 1]))
            yy, xx = np.nonzero(np.asarray(cell.convert("L")) < 232)
            if len(xx) < 1000:
                return []
            x0, x1, y0, y1 = xx.min(), xx.max(), yy.min(), yy.max()
            if (x1 - x0) < cell.width * 0.7 or (y1 - y0) < cell.height * 0.7:
                return []  # コマが小さすぎる（割り方が想定と違う）
            inset = int(min(x1 - x0, y1 - y0) * 0.015) + 3  # 黒い枠線を落とす
            cell = cell.crop((x0 + inset, y0 + inset, x1 - inset, y1 - inset))
            if cell.width > max_w:
                cell = cell.resize((max_w, int(cell.height * max_w / cell.width)), Image.LANCZOS)
            out.append(cell)
    return out


def generate_comic(cast: str, panels: list[str], out_paths: list[Path], models: list[str] | None = None,
                   style: str = "", fail_sheet: Path | None = None, attempts: int = 2, log=print) -> int:
    """6コマの漫画を1回で描かせて切り分け、out_paths（JPEG）に保存する。できたコマの数を返す。
    コマ割りがうまくいかなかったときは、もう一度描かせる（attempts 回まで）。"""
    import tempfile

    for attempt in range(attempts):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "comic.jpg"
            if not generate(comic_prompt(cast, panels, style), sheet, aspect="1:1", size="2K", kind="comic",
                            models=models, log=log):
                return 0
            pieces = slice_grid(sheet, COMIC_COLS, COMIC_ROWS)
            if len(pieces) != len(out_paths) and fail_sheet:
                fail_sheet.parent.mkdir(parents=True, exist_ok=True)
                fail_sheet.write_bytes(sheet.read_bytes())
        if len(pieces) == len(out_paths):
            for piece, path in zip(pieces, out_paths):
                path.parent.mkdir(parents=True, exist_ok=True)
                piece.save(path, quality=88)
            return len(pieces)
        log(f"  ⚠️ コマ割りが想定と違ったので描き直します（{attempt + 1}回目）")
    return 0


# ---------- 試し ----------

TEST_ICONS = [
    "a surprised little character with a wide open mouth",
    "an empty wallet with a moth flying out",
    "a cup of coffee with steam",
    "a thumbs-up hand",
    "a tired sleepy character resting on a pillow",
    "a rumbling stomach with a hamburger thought bubble",
    "two hands doing a high five",
    "a smartphone with a heart",
    "a red alarm clock ringing",
]


def _test(out_dir: Path) -> int:
    ok = 0
    for model in ["gemini-3.1-flash-lite-image", "gemini-nano-banana-2.1", "gemini-3-pro-image"]:
        print(f"▶ アイコン {model}")
        tag = model.replace("gemini-", "")
        paths = [out_dir / tag / f"icon{i:02d}.jpg" for i in range(1, len(TEST_ICONS) + 1)]
        n = generate_icons(TEST_ICONS, paths, models=[model], keep_sheet=out_dir / tag / "sheet.jpg")
        print(f"  {n}/{len(TEST_ICONS)} 個")
        ok += n
    for model in ["gemini-nano-banana-2.1", "gemini-3-pro-image"]:
        print(f"▶ 背景 {model}")
        tag = model.replace("gemini-", "")
        if generate_background("A charming street in London with red double-decker buses and old brick buildings",
                               out_dir / tag / "bg.jpg", models=[model]):
            ok += 1
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--test":
        sys.exit(_test(Path(sys.argv[2])))
    print(__doc__)

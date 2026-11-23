"""Gemini の画像生成で、1枚まとめなどに入れるイラストを作る。

- APIキーは GitHub のシークレット GEMINI_API_KEY（環境変数）からだけ読む。ファイルやログには出さない
- 画像の中に文字を書かせると崩れやすいので、絵だけを作らせる（文字はテンプレート側で上に載せる）
- キーが無いときや失敗したときは None を返す（呼び出し側は絵なしで作る）

試しに作る:  python -m autopost.imagegen --test <出力フォルダ>
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"
# 安くて速いものから順に試す
MODELS = ["gemini-3.1-flash-lite-image", "gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-2.5-flash-image"]
NO_TEXT = " No text, no letters, no numbers, no logos, no watermark anywhere in the image."


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _post(url: str, body: dict, key: str, timeout: int = 120) -> tuple[int, dict]:
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


def generate(prompt: str, out_path: Path, aspect: str = "1:1", models: list[str] | None = None,
             log=print) -> Path | None:
    """prompt の絵を out_path（PNG/JPG）に保存する。うまくいかなければ None。"""
    key = api_key()
    if not key:
        log("  GEMINI_API_KEY が無いので、絵は作りません")
        return None
    text = prompt.strip() + NO_TEXT
    for model in models or MODELS:
        # 1) Interactions API
        status, res = _post(f"{API}/interactions", {
            "model": model, "input": text,
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect, "image_size": "1K"},
        }, key)
        img = _find_image(res) if status == 200 else None
        how = "interactions"
        if img is None:
            log(f"  {model}（interactions）: {status} {_error_text(res)}")
            # 2) generateContent（以前からの形）
            status, res = _post(f"{API}/models/{model}:generateContent", {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
            }, key)
            img = _find_image(res) if status == 200 else None
            how = "generateContent"
            if img is None:
                log(f"  {model}（generateContent）: {status} {_error_text(res)}")
                continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(img)
        log(f"  ✅ {model}（{how}）→ {out_path.name}（{len(img) // 1024}KB）")
        return out_path
    return None


TEST_PROMPTS = {
    # 同じ題材をタッチ違いで
    "water_anime": "A glass of ice water placed on a wooden table in a Japanese restaurant. Bright, cheerful anime-style illustration, soft colors, clean lines.",
    "water_flat": "A glass of ice water placed on a wooden table in a Japanese restaurant. Flat vector illustration, bold simple shapes, pastel colors, white background.",
    "water_photo": "A glass of ice water placed on a wooden table in a Japanese restaurant. Realistic photo, natural light, shallow depth of field.",
    "water_clay": "A glass of ice water placed on a wooden table in a Japanese restaurant. Cute 3D clay render style, soft lighting, pastel colors.",
    # アニメ調で題材違い
    "toilet_anime": "A very clean, modern public restroom in Japan with a high-tech toilet. Bright, cheerful anime-style illustration, soft colors, clean lines.",
    "oshibori_anime": "A rolled white wet towel (oshibori) on a small tray at a Japanese restaurant. Bright, cheerful anime-style illustration, soft colors, clean lines.",
    "tourist_anime": "A surprised foreign tourist with a backpack looking amazed in a Tokyo street. Bright, cheerful anime-style illustration, soft colors, clean lines.",
}


def _test(out_dir: Path) -> int:
    ok = 0
    for name, prompt in TEST_PROMPTS.items():
        print(f"▶ {name}")
        if generate(prompt, out_dir / f"{name}.png"):
            ok += 1
        time.sleep(1)
    print(f"{ok}/{len(TEST_PROMPTS)} 枚できました")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--test":
        sys.exit(_test(Path(sys.argv[2])))
    print(__doc__)

"""Gemini にリール・投稿をレビューさせる（試作）。

review/in/ の動画（mp4）や画像（jpg/png）を、review/target.md の説明と review/rubric.md の
採点項目と一緒に Gemini に渡し、結果を review/out.md に書く。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"
HERE = Path(__file__).parent
MODELS = ["gemini-3.1-flash", "gemini-3-flash", "gemini-2.5-flash", "gemini-3.1-pro", "gemini-2.5-pro"]
MIME = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def call(model: str, body: dict, key: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def list_models(key: str) -> list[str]:
    req = urllib.request.Request(f"{API}/models?pageSize=200", headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    names = [m["name"].split("/")[-1] for m in data.get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    return [n for n in names if "flash" in n and "image" not in n and "lite" not in n and "tts" not in n]


def main() -> int:
    key = os.environ["GEMINI_API_KEY"]
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "in"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "target.md"
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "out.md"
    parts = [{"text": (HERE / "rubric.md").read_text()},
             {"text": "## 対象\n" + target.read_text()}]
    for f in sorted(in_dir.iterdir()):
        if f.suffix.lower() in MIME:
            parts.append({"inline_data": {"mime_type": MIME[f.suffix.lower()],
                                          "data": base64.b64encode(f.read_bytes()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"temperature": 0.7}}
    tried = []
    models = MODELS[:]
    for extra in (False, True):
        if extra:
            try:
                models = [m for m in list_models(key) if m not in tried][:4]
            except Exception as e:  # noqa: BLE001
                print("list models failed:", e)
                break
        for m in models:
            tried.append(m)
            code, data = call(m, body, key)
            if code == 200:
                text = "".join(p.get("text", "") for c in data.get("candidates", [])
                               for p in c.get("content", {}).get("parts", []))
                out.write_text(f"<!-- model: {m} -->\n{text}\n")
                print("ok", m)
                return 0
            print(m, code, str(data.get("error", {}).get("message", ""))[:200])
    out.write_text("レビューに失敗しました: " + ", ".join(tried) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""ストーリー形式の投稿（type が "story"）：アメコミ風カルーセル＋読み上げ付きリール。

post.json の書き方は examples/kaigai_hokkori/post.json と accounts/kaigai_hokkori.md を参照。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 小物アイコン（art.py の icon）。"noren:鮨" のように、のれんの文字を指定できる
ICONS = ("wallet", "wagyu", "sushi", "watch", "ramen", "noren", "question", "koban", "ball", "trash", "crane",
         "sandwich", "train", "phone", "bag", "shinkansen", "broom", "coffee")
MOODS = ("wow", "happy", "love", "sad", "think")
ALLOWED_TAGS = re.compile(r"<br\s*/?>|</?em>", re.I)

DEFAULT_VOICE = {
    "style_id": 14,       # VOICEVOX の声（14＝冥鳴ひまり）
    "speed": 0.8,         # 話す速さ
    "pitch": 0.0,
    "intonation": 1.0,
    "pause": 1.5,         # 読点・句点の間の倍率
    "gap": 0.6,           # 画面と画面の間（秒）
    "bgm_volume": 0.15,
}


def is_story(data: dict) -> bool:
    return isinstance(data, dict) and data.get("type") == "story"


def fingerprint() -> str:
    """デザインや音声の作り方が変わったら作り直すための指紋。"""
    h = hashlib.sha256()
    for path in sorted(HERE.glob("*.py")):
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def voice_settings(cfg: dict) -> dict:
    return {**DEFAULT_VOICE, **((cfg.get("reel") or {}).get("voice") or {})}


def reel_wanted(data: dict, cfg: dict) -> bool:
    return bool((cfg.get("reel") or {}).get("enabled")) and data.get("reel", True) is not False


def render_payload(data: dict, cfg: dict) -> dict:
    """画像と動画の中身を決める項目（ここが変わったら作り直す）。"""
    keys = ("icon", "burst", "top", "big", "big_size", "chat_title", "scenes", "comments", "stat", "cta", "reel_script")
    reel_cfg = cfg.get("reel") or {}
    return {
        "story": {k: data.get(k) for k in keys},
        "name": cfg.get("name"),
        "display_handle": cfg.get("display_handle"),
        "reel": reel_wanted(data, cfg),
        "voice": voice_settings(cfg),
        "credit": reel_cfg.get("credit", ""),
        "template": fingerprint(),
    }

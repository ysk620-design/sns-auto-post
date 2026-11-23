"""リールのBGM（フリー音源）。

- 使う曲の一覧は music/tracks.json（曲名・配布ページ・ダウンロードURL・雰囲気・規約の確認日）。
  公開リポジトリなので、**音楽ファイルそのものは置かない**（多くのフリー音源は再配布が禁止のため）。
  GitHub Actions が配布元からダウンロードして、Actions のキャッシュ（~/.cache/music）にだけ保存する
- 投稿ごとに曲を変える（投稿のフォルダ名から決まるので、作り直しても同じ曲になる）
- 曲が無いとき（一覧が空・ダウンロードに失敗）は、これまでの自作のBGM（story/bgm.py）を使う

曲を用意する:  python -m autopost.music download   （scripts/setup_music.sh から呼ばれる）
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import config

TRACKS_FILE = config.ROOT / "music" / "tracks.json"


def cache_dir() -> Path:
    return Path(os.environ.get("MUSIC_CACHE", Path.home() / ".cache" / "music"))


def tracks() -> list[dict]:
    if not TRACKS_FILE.exists():
        return []
    data = json.loads(TRACKS_FILE.read_text(encoding="utf-8"))
    return [t for t in data.get("tracks", []) if t.get("id") and t.get("url")]


def track_path(t: dict) -> Path:
    return cache_dir() / f"{t['id']}.mp3"


def available(mood: str | None = None) -> list[dict]:
    out = [t for t in tracks() if track_path(t).exists() and track_path(t).stat().st_size > 50_000]
    if mood:
        matched = [t for t in out if mood in (t.get("moods") or [])]
        return matched or out
    return out


def pick(key: str, mood: str | None = None) -> dict | None:
    """key（投稿のフォルダ名など）から曲を1つ選ぶ。同じ key なら同じ曲。"""
    cands = available(mood)
    if not cands:
        return None
    idx = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % len(cands)
    return cands[idx]


def best_start(t: dict, seconds: float) -> float:
    """曲の中で、seconds 秒のあいだ一番にぎやかな（音が大きい）所の始まり（秒）。サビを狙うため。
    落ち着いた曲（calm）は最初から。曲より長く使うときも最初から（くり返す）。"""
    if "start" in t:
        return float(t["start"])
    if "calm" in (t.get("moods") or []):
        return 0.0
    import numpy as np

    from .reel import ffmpeg_exe

    sr = 8000
    raw = subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-i", str(track_path(t)), "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    dur = len(x) / sr
    if dur < seconds + 8:
        return 0.0
    hop = sr // 2  # 0.5秒ごと
    n = len(x) // hop
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    win = max(1, int(seconds * 2))
    best, best_v = 0.0, -1.0
    for i in range(n - win):
        start = i * 0.5
        if start < 4 or start + seconds > dur - 3:
            continue  # 曲の頭（前奏）と終わりは避ける
        v = float(rms[i:i + win].mean())
        if v > best_v:
            best, best_v = start, v
    return best


def render_wav(t: dict, seconds: float, out_wav: Path, volume: float = 0.5) -> Path:
    """曲の聞きどころを seconds 秒切り出して、音量をそろえ、最初と最後をフェードした wav にする。
    曲が短いときはくり返す。"""
    from .reel import ffmpeg_exe

    start = best_start(t, seconds)
    fade_out = min(1.2, seconds / 4)
    af = (f"loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume},"
          f"afade=t=in:st=0:d=0.25,afade=t=out:st={max(0.0, seconds - fade_out):.2f}:d={fade_out:.2f}")
    subprocess.run(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{start:.2f}",
         "-i", str(track_path(t)), "-t", f"{seconds:.2f}", "-af", af, "-ar", "44100", "-ac", "2", str(out_wav)],
        check=True,
    )
    return out_wav


def bgm_array(key: str, seconds: float, volume: float = 0.5, mood: str | None = None):
    """BGM を numpy の配列（44100Hz・ステレオ・-1〜1）で返す。曲が無ければ None。"""
    t = pick(key, mood)
    if t is None:
        return None
    import tempfile

    import numpy as np
    from scipy.io import wavfile

    with tempfile.TemporaryDirectory() as tmp:
        wav = render_wav(t, seconds, Path(tmp) / "bgm.wav", volume=1.0)
        sr, data = wavfile.read(wav)
    arr = data.astype(np.float32) / 32768.0
    if arr.ndim == 1:
        arr = np.stack([arr, arr], 1)
    print(f"🎵 BGM: {t.get('title', t['id'])}")
    return arr * volume


def download(log=print) -> int:
    """一覧の曲で、まだ手元に無いものをダウンロードする。できた数を返す。"""
    cache_dir().mkdir(parents=True, exist_ok=True)
    ok = 0
    for t in tracks():
        path = track_path(t)
        if path.exists() and path.stat().st_size > 50_000:
            ok += 1
            continue
        for attempt in range(3):
            try:
                req = urllib.request.Request(t["url"], headers={"User-Agent": "Mozilla/5.0 (sns-auto-post BGM cache)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                if len(body) < 50_000:
                    raise RuntimeError(f"ファイルが小さすぎます（{len(body)} bytes）")
                path.write_bytes(body)
                log(f"🎵 {t.get('title', t['id'])}（{len(body) // 1024}KB）")
                ok += 1
                break
            except Exception as e:  # 配布元の一時的な不調など
                log(f"⚠️ {t.get('title', t['id'])} をダウンロードできませんでした（{e}）")
                time.sleep(3)
        time.sleep(1)  # 配布元に負担をかけないように、1曲ずつ間をあける
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "download":
        n = download()
        print(f"曲 {n}/{len(tracks())} 曲")
        sys.exit(0)
    print(__doc__)

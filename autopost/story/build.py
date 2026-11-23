"""ストーリー形式の投稿から、カルーセル画像（slideNN.jpg）と読み上げ付きリール（reel.mp4）を作る。"""
from __future__ import annotations

import copy
import io
import json
import subprocess
import tempfile
from pathlib import Path

from .. import config
from . import design, reel_wanted, render_payload, tts, voice_settings

SR = 44100
LEAD = 0.15  # 画面が切り替わってから声が出るまで（秒）
FPS = 30
ZOOM = 0.06  # 1画面のあいだに寄る（引く）割合

# 枠からはみ出した文字がないかを調べる
OVERFLOW_JS = """
() => [...document.querySelectorAll('body > section')].map(s => {
  const bad = [];
  for (const el of s.querySelectorAll('.nar, .say, .cm, .bb, .p')) {
    const r = el.getBoundingClientRect(), b = s.getBoundingClientRect();
    if (r.bottom > b.bottom + 2 || r.right > b.right + 2) bad.push(el.className);
    if (el.classList.contains('say') && el.scrollHeight > 150) bad.push('say（2行以上）');
  }
  return bad;
})
"""


def _hash(data: dict, cfg: dict) -> str:
    import hashlib

    raw = json.dumps(render_payload(data, cfg), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def render_hash(data: dict, cfg: dict) -> str:
    return _hash(data, cfg)


def needs_render(folder: Path, data: dict, cfg: dict) -> bool:
    info_path = folder / "render.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    if info.get("hash") != render_hash(data, cfg):
        return True
    if len(list(folder.glob("slide*.jpg"))) != info.get("slides"):
        return True
    return reel_wanted(data, cfg) and not (folder / "reel.mp4").exists()


def _wav_to_float(raw: bytes):
    import numpy as np
    from scipy.io import wavfile

    sr, w = wavfile.read(io.BytesIO(raw))
    if sr != SR:
        raise RuntimeError(f"音声のサンプリング周波数が違います（{sr}）")
    return w.astype(np.float32) / 32768


def make_reel_video(png_dir: Path, lines: list[str], voice: dict, out: Path, motion: list[bool] | None = None) -> float:
    """画面PNG（01..NN）と台本から、読み上げ＋BGM付きの mp4 を作る。長さ（秒）を返す。"""
    import numpy as np
    from scipy.io import wavfile

    from ..reel import ffmpeg_exe
    from .bgm import make_bgm

    pngs = sorted(png_dir.glob("*.png"))
    if len(pngs) != len(lines):
        raise RuntimeError(f"リールの画面数（{len(pngs)}）と台本の行数（{len(lines)}）が合いません")
    voices = [_wav_to_float(tts.speak(text, voice)) for text in lines]
    durs = [round(LEAD + len(w) / SR + float(voice["gap"]), 2) for w in voices]
    durs[-1] += 1.0  # 最後は少し余韻
    total = sum(durs)

    nar = np.zeros(int(SR * (total + 1)), np.float32)
    t = 0.0
    for w, d in zip(voices, durs):
        s = int(SR * (t + LEAD))
        nar[s:s + len(w)] += w
        t += d
    nar = nar[:int(SR * total)]
    nar *= 0.9 / max(float(np.max(np.abs(nar))), 1e-6)
    from .. import music

    # 読み上げの邪魔をしない、落ち着いた曲を選ぶ（フリー音源が無ければ自作のBGM）
    real = music.bgm_array(Path(out).parent.name, total, 1.0, mood="calm")
    bgm = (real * 0.55 if real is not None else make_bgm(total))
    bgm = np.pad(bgm, ((0, max(0, len(nar) - len(bgm))), (0, 0)))[:len(nar)]
    mix = np.clip(np.stack([nar, nar], 1) + bgm * float(voice["bgm_volume"]), -1, 1)

    motion = motion or [False] * len(pngs)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavfile.write(tmp / "mix.wav", SR, (mix * 32767).astype(np.int16))
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", str(FPS)]
        parts = []
        zoom_in = True
        for idx, (png, d, move) in enumerate(zip(pngs, durs, motion)):
            n = max(1, round(d * FPS))
            clip = tmp / f"part{idx:02d}.mp4"
            if move:
                # ゆっくりズーム（画面ごとに寄る・引くを交互に）。拡大してから縮めると、動きがなめらかになる
                z = f"1+{ZOOM}*on/{n}" if zoom_in else f"{1 + ZOOM}-{ZOOM}*on/{n}"
                zoom_in = not zoom_in
                vf = (f"scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d={n}:s=1080x1920:fps={FPS}")
                cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(png), "-vf", vf, "-frames:v", str(n)]
            else:
                cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-vf", "scale=1080:1920",
                       "-frames:v", str(n)]
            subprocess.run(cmd + enc + [str(clip)], check=True)
            parts.append(clip)
        (tmp / "parts.txt").write_text("".join(f"file '{c}'\n" for c in parts), encoding="utf-8")
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "parts.txt"),
             "-i", str(tmp / "mix.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-shortest", "-movflags", "+faststart", str(out)],
            check=True,
        )
    return total


async def _shoot(browser, html: str, height: int, out_dir: Path, prefix: str, ext: str) -> list:
    page = await browser.new_page(viewport={"width": 1080, "height": height})
    try:
        await page.set_content(html, wait_until="load")
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        overflow = await page.evaluate(OVERFLOW_JS)
        for i, el in enumerate(await page.query_selector_all("body > section"), 1):
            path = str(out_dir / f"{prefix}{i:02d}.{ext}")
            if ext == "jpg":
                await el.screenshot(path=path, type="jpeg", quality=92)
            else:
                await el.screenshot(path=path)
        return overflow
    finally:
        await page.close()


async def render_story(browser, folder: Path, data: dict, cfg: dict) -> list[str]:
    """1投稿ぶんの画像とリール動画を作る。直してほしい点（文字のはみ出しなど）を返す。"""
    name, handle = cfg.get("name", ""), cfg.get("display_handle", "@" + cfg["handle"])
    rel = folder.relative_to(config.ROOT) if folder.is_relative_to(config.ROOT) else folder
    problems: list[str] = []

    for old in list(folder.glob("slide*.jpg")) + [folder / "reel.mp4"]:
        if old.exists():
            old.unlink()
    overflow = await _shoot(browser, design.carousel(data, name, handle), 1350, folder, "slide", "jpg")
    for idx, bad in enumerate(overflow, 1):
        if bad:
            problems.append(f"{rel}: {idx}枚目の文字が枠に収まりません（{', '.join(sorted(set(bad)))}）。文を短くしてください")
    slides = len(list(folder.glob("slide*.jpg")))
    info = {"hash": render_hash(data, cfg), "slides": slides,
            "rendered_at": config.now_jst().isoformat(timespec="seconds")}

    if reel_wanted(data, cfg):
        if not tts.available():
            raise RuntimeError("読み上げ音声の準備（scripts/setup_voicevox.sh）ができていないので、リールを作れません")
        reel_data = copy.deepcopy(data)
        reel_data["comments"] = data["reel_script"]["comments"]
        credit = (cfg.get("reel") or {}).get("credit", "")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            over = await _shoot(browser, design.reel_pages(reel_data, name, handle, credit), 1920, tmp, "", "png")
            for idx, bad in enumerate(over, 1):
                if bad:
                    problems.append(f"{rel}: リールの{idx}画面目の文字が枠に収まりません。文を短くしてください")
            info["reel_seconds"] = round(make_reel_video(tmp, data["reel_script"]["nar"], voice_settings(cfg),
                                                         folder / "reel.mp4", design.reel_motion(reel_data)), 1)

    (folder / "render.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = f"・リール{info['reel_seconds']}秒" if "reel_seconds" in info else ""
    print(f"🖼  {rel}: {slides}枚{extra}")
    return problems

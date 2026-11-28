"""虚構図鑑（layout "zukan"）。この世にいない生き物などを、図鑑のページ風に見せる読み上げ付きリール。

流れ（約8〜9秒。Gemini のレビューで点数が高かった型）:
  つかみ（場面の絵か動画＋あるあるの一言、約2秒）→ 図鑑のページ（名前と特徴）→ オチ（赤い帯＋効果音＋コメントの誘い）
  → 最後の0.5秒でつかみの絵に戻る（ループでつながる）
音: 読み上げ（VOICEVOX）＋BGM（声の間は自動で小さく）＋オチの効果音。音量はそろえる（loudnorm）

post.json（type "reel_only"、slides は zukan 1枚）:
  no        図鑑の番号（例 "001"）。虚構図鑑だけは作品の一部として番号を出す
  name      名前（カタカナ。例 "ツリカワモドキ"）
  latin     学名風のラテン語（例 "Pseudoansa matutina"）
  group     分類（例 "擬態環形獣のなかま"）
  hook_top / hook_bottom  つかみの言葉（上の段・下の段。下の段が一番強い言葉）
  feature   特徴（2行まで。<b>…</b> で強調色）
  ochi      オチ（<br> で2行まで）
  ask       コメントの誘い（例 "今朝にぎった人はコメントで除霊"）
  voice     読み上げる3つの文 [つかみ, ページ, オチ]（省略すると hook と name・feature・ochi から作る）
  plate     図鑑の挿絵の説明（英語。Gemini で描く）
  scene     つかみの場面の説明（英語。写真風。Gemini で描く）
  投稿フォルダに opener.mp4（Gemini アプリで作った動画）を置くと、つかみに動画を使う。
  opener_focus（0〜1。横長の動画のどのあたりを縦に切り出すか。生き物のいる位置。省略すると 0.5＝中央）と
  opener_start（動画の何秒目から使うか）も書ける
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import re
import subprocess
import tempfile
import wave
from pathlib import Path

from . import art, config

PACKAGE_DIR = Path(__file__).parent
SR = 44100
FPS = 30
LOOP = 0.5
MIN_SECONDS = (2.0, 2.8, 2.6)  # つかみ・ページ・オチの最低秒数
OPENER = "opener.mp4"
CREDIT_DEFAULT = "ナレーション VOICEVOX:冥鳴ひまり"
FONT_SANS = "'Noto Sans CJK JP','Noto Sans JP',sans-serif"
FONT_SERIF = "'Noto Serif CJK JP','Noto Serif JP',serif"

PLATE_STYLE = ("Vintage natural history encyclopedia illustration, detailed hand-drawn linework with soft watercolor, "
               "plain aged parchment background, the whole creature visible and centered, side view, no labels.")
SCENE_STYLE = ("Photorealistic, vertical composition, cinematic natural light, shot like real smartphone footage, "
               "the strange creature clearly visible in the center of the frame.")


def slide_of(data: dict) -> dict | None:
    for s in data.get("slides") or []:
        if isinstance(s, dict) and s.get("layout") == "zukan":
            return s
    return None


def is_zukan(data: dict) -> bool:
    return slide_of(data) is not None


# ---------- 絵（Gemini で作って assets/zukan に保存。同じ説明なら使い回す） ----------

def plate_path(desc: str, root: Path | None = None) -> Path:
    return (root or art.ASSETS) / "zukan" / f"plate-{art.slug(desc)}.jpg"


def scene_path(desc: str, root: Path | None = None) -> Path:
    return (root or art.ASSETS) / "zukan" / f"scene-{art.slug(desc)}.jpg"


def wanted(data: dict) -> list[tuple[str, str, Path]]:
    s = slide_of(data)
    if not s:
        return []
    out = []
    if isinstance(s.get("plate"), str) and s["plate"].strip():
        out.append(("plate", s["plate"].strip(), plate_path(s["plate"].strip())))
    if isinstance(s.get("scene"), str) and s["scene"].strip():
        out.append(("scene", s["scene"].strip(), scene_path(s["scene"].strip())))
    return out


def missing(data: dict) -> list[tuple[str, str, Path]]:
    return [w for w in wanted(data) if not w[2].exists()]


def state(data: dict) -> list[str]:
    return [p.name for _, _, p in wanted(data) if p.exists()]


def ensure(items: list[dict], log=print) -> int:
    """足りない挿絵・場面の絵を作る。作った数を返す。"""
    from . import imagegen

    need = []
    for data in items:
        need += [w for w in missing(data) if w not in need]
    if not need:
        return 0
    if not imagegen.api_key():
        log(f"🎨 図鑑の絵が{len(need)}枚足りませんが、GEMINI_API_KEY が無いので絵なしで作ります")
        return 0
    made = 0
    for kind, desc, path in need[:8]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "plate":
            prompt = f"{desc.rstrip('.')}. {PLATE_STYLE}"
            ok = imagegen.generate(prompt, path, aspect="1:1", size="1K", kind="comic", log=log)
        else:
            prompt = f"{desc.rstrip('.')}. {SCENE_STYLE}"
            ok = imagegen.generate(prompt, path, aspect="9:16", size="1K", kind="comic", log=log)
        if ok:
            made += 1
            log(f"🎨 図鑑の絵を作りました: {kind} {desc[:50]}")
    return made


def opener_digest(folder: Path) -> str:
    p = folder / OPENER
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else ""


def code_fingerprint() -> str:
    return hashlib.sha256((PACKAGE_DIR / "zukan.py").read_bytes()).hexdigest()[:12]


# ---------- 画面（HTML） ----------

def _esc(text) -> str:
    """<br> と <b> だけ通す。"""
    out = html.escape(str(text or ""))
    return re.sub(r"&lt;(/?)(br|b)\s*/?&gt;", r"<\1\2>", out)


def _uri(path: Path) -> str:
    if not path or not path.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _css(theme: dict) -> str:
    red = theme.get("hot", "#c8402f")
    return f"""
.zk{{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:{FONT_SERIF};color:#3a2a1a}}
.zk .paper{{position:absolute;inset:0;background:radial-gradient(ellipse at 30% 20%,#f6ead0 0%,#ead7b0 60%,#d6bb86 100%)}}
.zk .ztag{{position:absolute;top:70px;left:60px;font-size:44px;font-weight:900;letter-spacing:.24em;color:#3a2a1a}}
.zk .ztag em{{font-style:normal;font-size:38px;color:{red};letter-spacing:.05em;margin-left:10px}}
.zk .zfic{{position:absolute;top:80px;right:60px;font-size:28px;color:#7a5a36;border:2px solid #7a5a36;padding:4px 14px;border-radius:30px;font-family:{FONT_SANS}}}
.zk .zpic{{position:absolute;top:170px;left:0;right:0;height:760px;overflow:hidden;background:#e9d6ae}}
.zk .zpic img{{width:100%;height:100%;object-fit:cover}}
.zk .zgrp{{position:absolute;top:940px;left:0;right:0;text-align:center;font-size:30px;color:#7a5a36;font-family:{FONT_SANS}}}
.zk .zname{{position:absolute;top:972px;left:20px;right:20px;text-align:center;font-size:118px;font-weight:900;letter-spacing:.03em;line-height:1.1;white-space:nowrap}}
.zk .zlatin{{position:absolute;top:1110px;left:0;right:0;text-align:center;font-size:36px;font-style:italic;color:#6b4e2e;font-family:serif}}
.zk .zfeat{{position:absolute;top:1196px;left:70px;right:70px;font-size:56px;font-weight:700;line-height:1.5;text-align:center}}
.zk .zfeat b{{color:{red}}}
.zk .zochi{{position:absolute;top:1166px;left:50px;right:50px;font-size:76px;font-weight:900;line-height:1.35;text-align:center;background:{red};color:#fff6e6;padding:30px 20px;border-radius:12px;transform:rotate(-2deg);font-family:{FONT_SANS};box-shadow:0 10px 0 rgba(0,0,0,.35)}}
.zk .zcta{{position:absolute;left:40px;right:40px;top:1470px;text-align:center;font-family:{FONT_SANS};font-weight:900;font-size:44px;line-height:1.45}}
.zk .zcta b{{color:{red}}}
.zk .zfoot{{position:absolute;bottom:40px;left:30px;right:30px;text-align:center;font-size:24px;color:#7a5a36;font-family:{FONT_SANS}}}
.zk.hook{{background:transparent}}
.zk .zht{{position:absolute;left:40px;right:40px;font-family:{FONT_SANS};font-weight:900;color:#fff;text-align:center;
 text-shadow:0 0 18px #000,0 5px 0 #000,0 -2px 0 #000,3px 0 0 #000,-3px 0 0 #000}}
"""


def _page(s: dict, cfg: dict, plate: str) -> str:
    no = f'<em>No.{_esc(s.get("no"))}</em>' if s.get("no") else ""
    img = f'<img src="{plate}">' if plate else ""
    grp = f'<div class="zgrp">{_esc(s.get("group"))}</div>' if s.get("group") else ""
    latin = f'<div class="zlatin">{_esc(s.get("latin"))}</div>' if s.get("latin") else ""
    return (f'<div class="paper"></div><div class="ztag">虚構図鑑{no}</div><div class="zfic">創作です</div>'
            f'<div class="zpic">{img}</div>{grp}<div class="zname">{_esc(s.get("name"))}</div>{latin}')


def section_html(b, s: dict) -> str:
    """templates.py から呼ぶ。最後の画面（オチ）を slide01 に、ほかの画面は zx として同じHTMLに入れる。"""
    cfg = b.cfg
    plate = _uri(plate_path(s["plate"].strip())) if s.get("plate") else ""
    follow = s.get("follow") or cfg.get("matome_follow") or "フォローで毎日1種、新種がとどく"
    credit = (cfg.get("reel") or {}).get("credit") or CREDIT_DEFAULT
    ask = f'👻 {_esc(s.get("ask"))}<br>' if s.get("ask") else ""
    final = (f'<section class="s zk">{_page(s, cfg, plate)}<div class="zochi">{_esc(s.get("ochi"))}</div>'
             f'<div class="zcta">{ask}<b>{_esc(follow)}</b></div>'
             f'<div class="zfoot">※掲載内容はすべて創作です　{_esc(credit)}</div></section>')
    mid = (f'<section class="zx zk" data-zx="page">{_page(s, cfg, plate)}'
           f'<div class="zfeat">{_esc(s.get("feature"))}</div></section>')
    hook = (f'<section class="zx zk hook" data-zx="hook">'
            f'<div class="zht" style="top:230px;font-size:84px;line-height:1.3">{_esc(s.get("hook_top"))}</div>'
            f'<div class="zht" style="bottom:330px;font-size:104px;color:#ffe14a;line-height:1.25">{_esc(s.get("hook_bottom"))}</div>'
            f'</section>')
    return f'<style>{_css(cfg["theme"])}</style>{final}{mid}{hook}'


# ---------- 読み上げと動画 ----------

def _plain(text) -> str:
    return re.sub(r"<[^>]+>", "", str(text or "")).strip()


def voice_lines(s: dict) -> list[str]:
    v = s.get("voice")
    if isinstance(v, list) and len(v) == 3 and all(isinstance(x, str) and x.strip() for x in v):
        return [x.strip() for x in v]
    hook = (_plain(s.get("hook_top")) + "、" + _plain(s.get("hook_bottom"))).strip("、")
    return [hook, f"{_plain(s.get('name'))}。{_plain(s.get('feature'))}", _plain(s.get("ochi"))]


def _wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def _boing(n: int) -> "object":
    import numpy as np

    tt = np.arange(n) / SR
    f = 520 * np.exp(-tt * 5) + 180 + 25 * np.sin(2 * np.pi * 18 * tt)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.55


def make_reel(folder: Path, data: dict, cfg: dict, final_png: Path, page_png: Path, hook_png: Path,
              out_path: Path) -> float:
    """読み上げ付きのリールを作る。長さ（秒）を返す。"""
    import numpy as np
    from scipy.io import wavfile

    from . import music
    from .reel import ffmpeg_exe
    from .story import tts
    from .story.bgm import make_bgm

    s = slide_of(data)
    voice_cfg = dict((cfg.get("reel") or {}).get("voice") or {"style_id": 14})
    for k, v in (("speed", 1.0), ("pitch", 0.0), ("intonation", 1.1), ("pause", 1.1)):
        voice_cfg.setdefault(k, v)
    lines = voice_lines(s)
    voices = [tts.speak(t, voice_cfg) for t in lines]
    durs = [max(m, _wav_seconds(v) + 0.35) for m, v in zip(MIN_SECONDS, voices)]
    total = sum(durs) + LOOP
    n = int(SR * total)

    vtrack = np.zeros(n)
    active = np.zeros(n)
    starts, t0 = [], 0.0
    for i, data_w in enumerate(voices):
        _, v = wavfile.read(io.BytesIO(data_w))
        v = v.astype(np.float32) / 32768.0
        if v.ndim > 1:
            v = v.mean(axis=1)
        s0 = int((t0 + 0.12) * SR)
        e0 = min(n, s0 + len(v))
        vtrack[s0:e0] += v[: e0 - s0]
        active[s0:e0] = 1
        starts.append(t0)
        t0 += durs[i]
    vtrack *= 0.9 / (np.max(np.abs(vtrack)) or 1.0)
    k = int(0.12 * SR)
    smooth = np.convolve(active, np.ones(k) / k, mode="same")
    gain = 0.30 - 0.20 * np.clip(smooth * 1.5, 0, 1)  # 声の間は BGM を小さく
    bgm = music.bgm_array(folder.name, total, 0.6, mood="quiz")
    if bgm is None:
        bgm = make_bgm(total + 0.5) * 0.5
    bgm = np.asarray(bgm)[:n]
    if bgm.ndim == 1:
        bgm = np.stack([bgm, bgm], axis=1)
    if len(bgm) < n:
        bgm = np.pad(bgm, ((0, n - len(bgm)), (0, 0)))
    bgm = bgm / (np.max(np.abs(bgm)) or 1.0)
    mix = bgm * gain[:, None]
    mix[:, 0] += vtrack
    mix[:, 1] += vtrack
    ts = int(starts[2] * SR)
    L = min(int(0.32 * SR), n - ts)
    if L > 0:
        b = _boing(L)
        mix[ts:ts + L, 0] += b
        mix[ts:ts + L, 1] += b
    mix = np.clip(mix, -1, 1)

    d0, d1, d2 = durs
    opener = folder / OPENER
    scene = scene_path(s["scene"].strip()) if s.get("scene") else None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavfile.write(tmp / "audio.wav", SR, (mix * 32767).astype(np.int16))
        if opener.exists():
            # Gemini アプリの動画は横長なので、生き物のいるあたり（opener_focus。0＝左端〜1＝右端）を縦に切り出して全面に
            focus = float(s.get("opener_focus", 0.5))
            start = float(s.get("opener_start", 0))
            src = ["-ss", f"{start:.2f}", "-i", str(opener)]
            vf = f"scale=-2:1920,crop=1080:1920:'max(0,min(iw-1080,iw*{focus:.3f}-540))':0,setsar=1,fps=30"
            hook_v = f"[0:v]trim=duration={d0},setpts=PTS-STARTPTS,{vf}[bgv]"
            loop_v = f"[4:v]trim=duration={LOOP},setpts=PTS-STARTPTS,{vf},format=yuv420p[l]"
            loop_src = ["-ss", f"{start:.2f}", "-i", str(opener)]
        else:
            img = scene if scene and scene.exists() else page_png
            src = ["-i", str(img)]  # zoompan が1枚から秒数ぶんの絵を作る
            hook_v = (f"[0:v]scale=1080:1920,zoompan=z='min(1.0+0.0015*on,1.12)':d={int(d0 * FPS)}:s=1080x1920:fps=30,"
                      f"setsar=1[bgv]")
            loop_v = f"[4:v]scale=1080:1920,setsar=1,fps=30,trim=duration={LOOP},format=yuv420p[l]"
            loop_src = ["-loop", "1", "-t", str(LOOP), "-i", str(img)]
        fc = (f"{hook_v};[bgv][1:v]overlay=0:0,format=yuv420p[h];"
              f"[2:v]scale=1080:1920,zoompan=z='min(1.0+0.0005*on,1.04)':d={int(d1 * FPS)}:s=1080x1920:fps=30,format=yuv420p[p];"
              f"[3:v]scale=1080:1920,zoompan=z='1.0':d={int(d2 * FPS)}:s=1080x1920:fps=30,format=yuv420p[o];"
              f"{loop_v};[h][p][o][l]concat=n=4:v=1:a=0[out];[5:a]loudnorm=I=-14:TP=-1.5:LRA=11[au]")
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", *src,
               "-loop", "1", "-t", str(d0), "-i", str(hook_png),
               "-i", str(page_png), "-i", str(final_png), *loop_src, "-i", str(tmp / "audio.wav"),
               "-filter_complex", fc, "-map", "[out]", "-map", "[au]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
               "-movflags", "+faststart", "-t", f"{total:.3f}", str(out_path)]
        subprocess.run(cmd, check=True)
    return round(total, 2)


async def render_extras(page, folder: Path, data: dict, cfg: dict) -> float:
    """templates の HTML がページに読み込まれた状態で呼ぶ。つかみとページの画面を撮って、リールを作る。"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        hook_el = await page.query_selector('section.zx[data-zx="hook"]')
        page_el = await page.query_selector('section.zx[data-zx="page"]')
        await page_el.screenshot(path=str(tmp / "page.png"))
        # つかみの文字は動画に重ねるので、背景を透明にして撮る
        await page.evaluate("for (const el of [document.documentElement, document.body]) el.style.background = 'transparent'")
        await hook_el.screenshot(path=str(tmp / "hook.png"), omit_background=True)
        final = folder / "slide01.jpg"
        return make_reel(folder, data, cfg, final, tmp / "page.png", tmp / "hook.png", folder / "reel.mp4")


def render_key(folder: Path, data: dict) -> dict:
    """リールを作り直すかどうかの目印（絵・つかみの動画・作り方のコード）。"""
    return {"art": state(data), "opener": opener_digest(folder), "code": code_fingerprint()}


def needs_reel(folder: Path, data: dict, info: dict) -> bool:
    return is_zukan(data) and (info.get("zukan") != render_key(folder, data) or not (folder / "reel.mp4").exists())


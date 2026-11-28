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
  opener_start（動画の何秒目から使うか）も書ける（opener_focus・opener_start は、動画を縦に切り出していた
  ころの項目。今は動画を横長のまま真ん中に置き、上下の帯に字幕を出す形なので、使わない）
  動画があるときの流れ：動画（最大9秒。上下の帯に つかみ→名前と特徴→オチ の字幕と読み上げ）→ 図鑑のページ2秒 → 動画の冒頭へ
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
    caps = _caps_html(s, cfg, ask, follow, credit)
    return f'<style>{_css(cfg["theme"])}{CAP_CSS}</style>{final}{mid}{hook}{caps}'


# 動画があるときの字幕の画面（横長の動画は縦に切らず、真ん中に置く。上下の帯に文字）
VIDEO_TOP = 656  # 動画（1080×608）を置く高さ
CAP_CSS = f"""
.zcap{{position:relative;width:1080px;height:1920px;overflow:hidden;background:transparent}}
.zcap .bt,.zcap .bb{{position:absolute;left:0;right:0;background:radial-gradient(ellipse at 30% 20%,#f6ead0 0%,#ead7b0 70%,#dcc394 100%)}}
.zcap .bt{{top:0;height:{VIDEO_TOP}px;border-bottom:6px solid #3a2a1a}}
.zcap .bb{{top:{VIDEO_TOP + 608}px;bottom:0;border-top:6px solid #3a2a1a}}
.zcap .ct{{position:absolute;left:40px;right:40px;top:150px;bottom:24px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-family:{FONT_SANS};font-weight:900;color:#2b2118;line-height:1.25}}
.zcap .cb{{position:absolute;left:40px;right:40px;top:28px;bottom:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-family:{FONT_SANS};font-weight:900;color:#2b2118;line-height:1.35}}
.zcap .tg{{position:absolute;top:60px;left:56px;font-family:{FONT_SERIF};font-size:42px;font-weight:900;letter-spacing:.22em;color:#3a2a1a}}
.zcap .tg em{{font-style:normal;color:#c8402f;font-size:36px;letter-spacing:.05em;margin-left:8px}}
.zcap .fc{{position:absolute;top:70px;right:56px;font-size:26px;color:#7a5a36;border:2px solid #7a5a36;padding:3px 12px;border-radius:30px;font-family:{FONT_SANS}}}
.zcap .h1{{font-size:70px}}
.zcap .h2{{font-size:100px;color:#c8402f;margin-top:10px}}
.zcap .nm{{font-family:{FONT_SERIF};font-size:110px;letter-spacing:.03em;white-space:nowrap}}
.zcap .lt{{font-family:serif;font-style:italic;font-weight:400;font-size:34px;color:#6b4e2e;margin-top:6px}}
.zcap .gp{{font-size:30px;font-weight:700;color:#7a5a36;margin-bottom:6px}}
.zcap .ft{{font-family:{FONT_SERIF};font-size:58px;font-weight:700;line-height:1.5}}
.zcap .ft b{{color:#c8402f}}
.zcap .oc{{background:#c8402f;color:#fff6e6;font-size:70px;padding:24px 34px;border-radius:12px;transform:rotate(-2deg);box-shadow:0 10px 0 rgba(0,0,0,.35)}}
.zcap .ak{{font-size:44px;margin-top:34px}}
.zcap .tz{{font-size:46px;color:#7a5a36}}
.zcap .fo{{position:absolute;left:20px;right:20px;bottom:34px;text-align:center;font-size:24px;color:#7a5a36;font-family:{FONT_SANS}}}
"""


def _caps_html(s: dict, cfg: dict, ask: str, follow: str, credit: str) -> str:
    no = f'<em>No.{_esc(s.get("no"))}</em>' if s.get("no") else ""
    top_tag = f'<div class="tg">虚構図鑑{no}</div><div class="fc">創作です</div>'
    foot = f'<div class="fo">※掲載内容はすべて創作です　{_esc(credit)}</div>'
    grp = f'<div class="gp">{_esc(s.get("group"))}</div>' if s.get("group") else ""
    latin = f'<div class="lt">{_esc(s.get("latin"))}</div>' if s.get("latin") else ""
    name = f'{grp}<div class="nm">{_esc(s.get("name"))}</div>{latin}'

    def cap(key, top, bottom):
        return (f'<section class="zx zcap" data-zx="{key}"><div class="bt">{top_tag}<div class="ct">{top}</div></div>'
                f'<div class="bb"><div class="cb">{bottom}</div>{foot}</div></section>')

    c1 = cap("cap1", f'<div class="h1">{_esc(s.get("hook_top"))}</div><div class="h2">{_esc(s.get("hook_bottom"))}</div>',
             '<div class="tz">この生き物の正体は…</div>')
    c2 = cap("cap2", name, f'<div class="ft">{_esc(s.get("feature"))}</div>')
    ak = f'<div class="ak">👻 {_esc(s.get("ask"))}</div>' if s.get("ask") else ""
    c3 = cap("cap3", name, f'<div class="oc">{_esc(s.get("ochi"))}</div>{ak}')
    return c1 + c2 + c3


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


def _mix_audio(folder: Path, voices: list, starts: list, total: float, sfx_at: float):
    """読み上げ（starts 秒に置く）＋BGM（声の間は小さく）＋効果音。ステレオの配列を返す。"""
    import numpy as np
    from scipy.io import wavfile

    from . import music
    from .story.bgm import make_bgm

    n = int(SR * total)
    vtrack = np.zeros(n)
    active = np.zeros(n)
    for data_w, st in zip(voices, starts):
        _, v = wavfile.read(io.BytesIO(data_w))
        v = v.astype(np.float32) / 32768.0
        if v.ndim > 1:
            v = v.mean(axis=1)
        s0 = int(st * SR)
        e0 = min(n, s0 + len(v))
        if e0 > s0:
            vtrack[s0:e0] += v[: e0 - s0]
            active[s0:e0] = 1
    vtrack *= 0.9 / (np.max(np.abs(vtrack)) or 1.0)
    k = int(0.12 * SR)
    smooth = np.convolve(active, np.ones(k) / k, mode="same")
    gain = 0.30 - 0.20 * np.clip(smooth * 1.5, 0, 1)
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
    ts = int(sfx_at * SR)
    L = min(int(0.32 * SR), n - ts)
    if L > 0:
        b = _boing(L)
        mix[ts:ts + L, 0] += b
        mix[ts:ts + L, 1] += b
    return np.clip(mix, -1, 1)


def _video_seconds(path: Path) -> float:
    from .reel import ffmpeg_exe

    r = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 8.0


PAGE_SECONDS = 2.0  # 動画のあとに図鑑のページを見せる秒数
VIDEO_MAX = 9.0


def make_video_reel(folder: Path, data: dict, cfg: dict, final_png: Path, caps: list, out_path: Path) -> float:
    """動画が主役のリール。横長の動画を真ん中に置き、上下の帯に字幕（つかみ→名前と特徴→オチ）を出す。
    動画のあとに図鑑のページを少しだけ見せ、最後に動画の冒頭へ戻る（ループでつながる）。"""
    import numpy as np
    from scipy.io import wavfile

    from .reel import ffmpeg_exe
    from .story import tts

    s = slide_of(data)
    voice_cfg = dict((cfg.get("reel") or {}).get("voice") or {"style_id": 14})
    for k, v in (("speed", 1.0), ("pitch", 0.0), ("intonation", 1.1), ("pause", 1.1)):
        voice_cfg.setdefault(k, v)
    voices = [tts.speak(t, voice_cfg) for t in voice_lines(s)]
    lens = [_wav_seconds(v) for v in voices]
    opener = folder / OPENER
    vstart = 0.0  # 動画は最初から見せる
    vlen = min(VIDEO_MAX, max(3.0, _video_seconds(opener) - vstart))
    # 字幕と読み上げの区切り（1つ目の声のあとに2つ目、2つ目のあとにオチ）
    t1 = 0.15
    t2 = max(1.8, t1 + lens[0] + 0.25)
    t3 = max(t2 + 1.8, t2 + lens[1] + 0.25)
    vend = max(vlen, t3 + lens[2] + 0.5)  # 声が長いときは動画の最後の絵で止めて待つ
    total = vend + PAGE_SECONDS + LOOP
    mix = _mix_audio(folder, voices, [t1, t2, t3], total, t3)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavfile.write(tmp / "audio.wav", SR, (mix * 32767).astype(np.int16))
        hold = max(0.0, vend - vlen)
        vid = (f"[0:v]trim=start={vstart:.2f}:duration={vlen:.2f},setpts=PTS-STARTPTS,"
               f"scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1,fps={FPS}"
               + (f",tpad=stop_mode=clone:stop_duration={hold:.2f}" if hold > 0 else "") +
               f",pad=1080:1920:0:{VIDEO_TOP}:color=0x2b2118[v0];"
               f"[v0][1:v]overlay=0:0:enable='lt(t,{t2:.2f})'[v1];"
               f"[v1][2:v]overlay=0:0:enable='between(t,{t2:.2f},{t3:.2f})'[v2];"
               f"[v2][3:v]overlay=0:0:enable='gte(t,{t3:.2f})',format=yuv420p,trim=duration={vend:.2f}[main];"
               f"[4:v]scale=1080:1920,setsar=1,fps={FPS},trim=duration={PAGE_SECONDS},format=yuv420p[pg];"
               f"[5:v]trim=start={vstart:.2f}:duration={LOOP},setpts=PTS-STARTPTS,"
               f"scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1,fps={FPS},"
               f"pad=1080:1920:0:{VIDEO_TOP}:color=0x2b2118[l0];[l0][1:v]overlay=0:0,format=yuv420p[lp];"
               f"[main][pg][lp]concat=n=3:v=1:a=0[out];[6:a]loudnorm=I=-14:TP=-1.5:LRA=11[au]")
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(opener),
               "-loop", "1", "-i", str(caps[0]), "-loop", "1", "-i", str(caps[1]), "-loop", "1", "-i", str(caps[2]),
               "-loop", "1", "-t", str(PAGE_SECONDS), "-i", str(final_png), "-i", str(opener),
               "-i", str(tmp / "audio.wav"),
               "-filter_complex", vid, "-map", "[out]", "-map", "[au]",
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
        if (folder / OPENER).exists():
            caps = []
            for k in ("cap1", "cap2", "cap3"):
                el = await page.query_selector(f'section.zx[data-zx="{k}"]')
                await el.screenshot(path=str(tmp / f"{k}.png"), omit_background=True)
                caps.append(tmp / f"{k}.png")
            return make_video_reel(folder, data, cfg, final, caps, folder / "reel.mp4")
        return make_reel(folder, data, cfg, final, tmp / "page.png", tmp / "hook.png", folder / "reel.mp4")


def render_key(folder: Path, data: dict) -> dict:
    """リールを作り直すかどうかの目印（絵・つかみの動画・作り方のコード）。"""
    return {"art": state(data), "opener": opener_digest(folder), "code": code_fingerprint()}


def needs_reel(folder: Path, data: dict, info: dict) -> bool:
    return is_zukan(data) and (info.get("zukan") != render_key(folder, data) or not (folder / "reel.mp4").exists())


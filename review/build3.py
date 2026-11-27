"""虚構図鑑の試作リール 第3版（第2版へのGeminiのレビューと、聞き取りにくさを反映）。GitHub Actions で動かす。

- 約11秒に短縮。つかみは縦いっぱいの動画を2秒
- 読み上げ（VOICEVOX）と BGM を入れる
- つかみを「あるある」に。締めにコメントしたくなる一言
出力：review/v2/kyokou_v2.mp4
"""
from __future__ import annotations

import asyncio
import base64
import io
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HERE = ROOT / "review"
OUT = HERE / "v3" / "kyokou_v3.mp4"
SRC_VIDEO = HERE / "src" / "train.mp4"
ILLUST = HERE / "src" / "illust.jpg"
VOICE = {"style_id": 14, "speed": 1.0, "pitch": 0.0, "intonation": 1.1, "pause": 1.1}
SR = 44100

# (画面, 最低秒数, 読み上げ)
SCENES = [
    ("hook", 2.0, "月曜の朝、やる気が消えるのは、こいつのせい。"),
    ("page", 2.8, "ツリカワモドキ。つり革に化けて、つかんだ人のやる気を吸う。"),
    ("ochi", 2.6, "金曜の夜は、満腹で動かない。"),
]
LOOP = 0.5  # 最後に冒頭の動画へ戻す（ループのつなぎ目）

FONT_SANS = "'Noto Sans CJK JP','Noto Sans JP',sans-serif"
FONT_SERIF = "'Noto Serif CJK JP','Noto Serif JP',serif"
img64 = base64.b64encode(ILLUST.read_bytes()).decode()

BASE = f"""*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1920px;overflow:hidden;font-family:{FONT_SERIF};color:#3a2a1a}}
.paper{{position:absolute;inset:0;background:radial-gradient(ellipse at 30% 20%,#f6ead0 0%,#ead7b0 60%,#d6bb86 100%)}}
.tag{{position:absolute;top:70px;left:60px;font-size:44px;font-weight:900;letter-spacing:.3em}}
.fic{{position:absolute;top:80px;right:60px;font-size:28px;color:#7a5a36;border:2px solid #7a5a36;padding:4px 14px;border-radius:30px;font-family:{FONT_SANS}}}
.pic{{position:absolute;top:170px;left:0;right:0;height:900px;overflow:hidden}}
.pic img{{width:100%;height:100%;object-fit:cover;object-position:60% 50%}}
.name{{position:absolute;top:1100px;left:0;right:0;text-align:center;font-size:120px;font-weight:900;letter-spacing:.04em}}
.latin{{position:absolute;top:1250px;left:0;right:0;text-align:center;font-size:36px;font-style:italic;color:#6b4e2e;font-family:serif}}
.feat{{position:absolute;top:1340px;left:70px;right:70px;font-size:56px;font-weight:700;line-height:1.5;text-align:center}}
.feat b{{color:#c8402f}}
.ochi{{position:absolute;top:1300px;left:50px;right:50px;font-size:78px;font-weight:900;line-height:1.35;text-align:center;background:#c8402f;color:#fff6e6;padding:34px 20px;border-radius:12px;transform:rotate(-2deg);font-family:{FONT_SANS};box-shadow:0 10px 0 #7a2318}}
.foot{{position:absolute;bottom:60px;left:0;right:0;text-align:center;font-size:26px;color:#7a5a36;font-family:{FONT_SANS}}}
"""


def html(kind: str) -> str:
    if kind == "hook":
        return f"""<style>{BASE}
.t{{position:absolute;left:40px;right:40px;font-family:{FONT_SANS};font-weight:900;color:#fff;text-align:center;
 text-shadow:0 0 18px #000,0 5px 0 #000,0 -2px 0 #000,3px 0 0 #000,-3px 0 0 #000}}</style>
<div class=t style="top:230px;font-size:84px;line-height:1.3">月曜の朝<br>やる気が消えるのは</div>
<div class=t style="bottom:330px;font-size:104px;color:#ffe14a">こいつのせい。</div>"""
    page = f"""<div class=paper></div><div class=tag>虚構図鑑 <span style="font-size:38px;color:#c8402f">No.001</span></div><div class=fic>創作です</div>
<div class=pic><img src="data:image/jpeg;base64,{img64}"></div>
<div class=name>ツリカワモドキ</div><div class=latin>Pseudoansa matutina</div>"""
    if kind == "page":
        return f"<style>{BASE}</style>{page}<div class=feat>つり革に化けて<br>つかんだ人の<b>やる気</b>を吸う</div>"
    if kind == "ochi":
        return f"""<style>{BASE}
.cta{{position:absolute;left:40px;right:40px;bottom:150px;text-align:center;font-family:{FONT_SANS};font-weight:900;font-size:46px;line-height:1.45;color:#3a2a1a}}
.cta b{{color:#c8402f}}</style>{page}<div class=ochi>金曜の夜は<br>満腹で、動かない。</div>
<div class=cta>👻 今朝にぎった人は<b>コメントで除霊</b><br>フォローで毎日1種、新種がとどく</div>
<div class=foot>※掲載内容はすべて創作です　ナレーション VOICEVOX:冥鳴ひまり</div>"""
    return f"""<style>{BASE}
.e{{position:absolute;left:0;right:0;text-align:center;font-family:{FONT_SANS};font-weight:900}}</style>
<div class=paper style="background:#2b2118"></div>
<div class=e style="top:330px;font-size:88px;color:#ffe14a;line-height:1.35">今朝にぎった人は<br>コメントで除霊👻</div>
<div class=e style="top:820px;font-size:110px;color:#f6ead0;letter-spacing:.2em">虚構図鑑</div>
<div class=e style="top:1010px;font-size:60px;color:#f6ead0;line-height:1.5">フォローすると<br>明日も新種がとどく</div>
<div class=e style="bottom:110px;font-size:28px;color:#c9b38a;font-weight:400">※掲載内容はすべて創作です　ナレーション VOICEVOX:冥鳴ひまり</div>"""


async def shots(tmp: Path) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        from autopost.render import chrome_path
        exe = chrome_path()
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        for kind, _, _ in SCENES:
            await pg.set_content(html(kind))
            await pg.wait_for_timeout(400)
            await pg.screenshot(path=str(tmp / f"{kind}.png"), omit_background=(kind == "hook"))
        await b.close()


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    import numpy as np
    from scipy.io import wavfile
    from autopost import music
    from autopost.story import tts
    from autopost.story.bgm import make_bgm

    tmp = Path(tempfile.mkdtemp())
    asyncio.run(shots(tmp))
    durs, voices = [], []
    for i, (kind, mins, text) in enumerate(SCENES):
        data = tts.speak(text, VOICE)
        (tmp / f"v{i}.wav").write_bytes(data)
        d = max(mins, wav_seconds(data) + 0.35)
        durs.append(d)
        voices.append(data)
    total = sum(durs) + LOOP
    print("durations", [round(d, 2) for d in durs], "total", round(total, 2))
    n = int(SR * total)

    # 声のトラックと、声が鳴っている区間（BGMを下げるため）
    vtrack = np.zeros(n)
    active = np.zeros(n)
    starts = []
    t0 = 0.0
    for i, data in enumerate(voices):
        sr, v = wavfile.read(io.BytesIO(data))
        v = v.astype(np.float32) / 32768.0
        s0 = int((t0 + 0.12) * SR)
        e0 = min(n, s0 + len(v))
        vtrack[s0:e0] += v[: e0 - s0]
        active[s0:e0] = 1
        starts.append(t0)
        t0 += durs[i]
    peak = np.max(np.abs(vtrack)) or 1.0
    vtrack *= 0.9 / peak
    # BGM：声の間は小さく（0.10）、声のない所は少し大きく（0.30）。切り替えはなめらかに
    k = int(0.12 * SR)
    smooth = np.convolve(active, np.ones(k) / k, mode="same")
    gain = 0.30 - 0.20 * np.clip(smooth * 1.5, 0, 1)
    bgm = music.bgm_array("kyokou-v3", total, 0.6, mood="quiz")
    if bgm is None:
        bgm = make_bgm(total + 0.5) * 0.5
    bgm = bgm[:n]
    if len(bgm) < n:
        bgm = np.pad(bgm, ((0, n - len(bgm)), (0, 0)))
    bpk = np.max(np.abs(bgm)) or 1.0
    bgm = bgm / bpk
    mix = bgm * gain[:, None]
    mix[:, 0] += vtrack
    mix[:, 1] += vtrack
    # オチが出た瞬間の効果音（ポヨン）
    ts = int(starts[2] * SR)
    L = int(0.32 * SR)
    tt = np.arange(L) / SR
    f = 520 * np.exp(-tt * 5) + 180 + 25 * np.sin(2 * np.pi * 18 * tt)
    boing = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.55
    mix[ts:ts + L, 0] += boing[: max(0, min(L, n - ts))]
    mix[ts:ts + L, 1] += boing[: max(0, min(L, n - ts))]
    mix = np.clip(mix, -1, 1)
    wavfile.write(tmp / "voice_bgm.wav", SR, (mix * 32767).astype(np.int16))

    # 映像：つかみは動画を縦いっぱいに（生き物の位置に合わせて切り出し）
    d0, d1, d2 = durs
    fc = (
        f"[0:v]trim=start=5.0:duration={d0},setpts=PTS-STARTPTS,crop=405:720:540:0,scale=1080:1920,setsar=1,fps=30[vid];"
        f"[vid][1:v]overlay=0:0,format=yuv420p[h];"
        f"[2:v]scale=1080:1920,zoompan=z='min(1.0+0.0009*on,1.08)':d={int(d1*30)}:s=1080x1920:fps=30,format=yuv420p[p];"
        f"[3:v]scale=1080:1920,zoompan=z='1.08':d={int(d2*30)}:s=1080x1920:fps=30,format=yuv420p[o];"
        f"[4:v]trim=start=5.0:duration={LOOP},setpts=PTS-STARTPTS,crop=405:720:540:0,scale=1080:1920,setsar=1,fps=30,format=yuv420p[l];"
        f"[h][p][o][l]concat=n=4:v=1:a=0[out];"
        f"[5:a]loudnorm=I=-14:TP=-1.5:LRA=11[au]"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    from autopost.reel import ffmpeg_exe
    cmd = [ffmpeg_exe(), "-v", "error", "-y", "-i", str(SRC_VIDEO),
           "-loop", "1", "-t", str(d0), "-i", str(tmp / "hook.png"),
           "-i", str(tmp / "page.png"),
           "-i", str(tmp / "ochi.png"),
           "-i", str(SRC_VIDEO),
           "-i", str(tmp / "voice_bgm.wav"),
           "-filter_complex", fc, "-map", "[out]", "-map", "[au]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", "-t", str(total), str(OUT)]
    subprocess.run(cmd, check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

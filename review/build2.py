"""虚構図鑑の試作リール 第2版（Geminiのレビューを反映）。GitHub Actions で動かす。

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
OUT = HERE / "v2" / "kyokou_v2.mp4"
SRC_VIDEO = HERE / "src" / "train.mp4"
ILLUST = HERE / "src" / "illust.jpg"
VOICE = {"style_id": 14, "speed": 1.12, "pitch": 0.0, "intonation": 1.15, "pause": 1.2}
SR = 44100

# (画面, 最低秒数, 読み上げ)
SCENES = [
    ("hook", 2.0, "月曜の朝、やる気が消えるのは、こいつのせい。"),
    ("page", 3.2, "ツリカワモドキ。つり革に化けて、つかんだ人のやる気を吸う。"),
    ("ochi", 3.0, "金曜の夜は、満腹で動かない。"),
    ("end", 2.6, "今朝にぎった人は、コメントで除霊。"),
]

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
.ochi{{position:absolute;top:1330px;left:50px;right:50px;font-size:78px;font-weight:900;line-height:1.35;text-align:center;background:#c8402f;color:#fff6e6;padding:34px 20px;border-radius:12px;transform:rotate(-2deg);font-family:{FONT_SANS};box-shadow:0 10px 0 #7a2318}}
.foot{{position:absolute;bottom:60px;left:0;right:0;text-align:center;font-size:26px;color:#7a5a36;font-family:{FONT_SANS}}}
"""


def html(kind: str) -> str:
    if kind == "hook":
        return f"""<style>{BASE}
.t{{position:absolute;left:40px;right:40px;font-family:{FONT_SANS};font-weight:900;color:#fff;text-align:center;
 text-shadow:0 0 18px #000,0 5px 0 #000,0 -2px 0 #000,3px 0 0 #000,-3px 0 0 #000}}</style>
<div class=t style="top:230px;font-size:84px;line-height:1.3">月曜の朝<br>やる気が消えるのは</div>
<div class=t style="bottom:330px;font-size:104px;color:#ffe14a">こいつのせい。</div>"""
    page = f"""<div class=paper></div><div class=tag>虚構図鑑</div><div class=fic>創作です</div>
<div class=pic><img src="data:image/jpeg;base64,{img64}"></div>
<div class=name>ツリカワモドキ</div><div class=latin>Pseudoansa matutina</div>"""
    if kind == "page":
        return f"<style>{BASE}</style>{page}<div class=feat>つり革に化けて<br>つかんだ人の<b>やる気</b>を吸う</div>"
    if kind == "ochi":
        return f"<style>{BASE}</style>{page}<div class=ochi>金曜の夜は<br>満腹で、動かない。</div>"
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
    total = sum(durs)
    print("durations", [round(d, 2) for d in durs], "total", round(total, 2))

    # 音：BGM＋読み上げ（＋つかみだけ電車の音）
    bgm = music.bgm_array("kyokou-v2", total, 0.5, mood="quiz")
    if bgm is None:
        bgm = make_bgm(total + 0.5)[: int(SR * total)] * 0.35
    mix = np.zeros((int(SR * total) + SR, 2))
    mix[: len(bgm)] += bgm[: len(mix)] * 0.45
    t0 = 0.0
    for i, data in enumerate(voices):
        sr, v = wavfile.read(io.BytesIO(data))
        v = v.astype(np.float32) / 32768.0
        s = int((t0 + 0.12) * SR)
        mix[s:s + len(v), 0] += v * 1.0
        mix[s:s + len(v), 1] += v * 1.0
        t0 += durs[i]
    mix = mix[: int(SR * total)]
    mix = np.clip(mix, -1, 1)
    wavfile.write(tmp / "voice_bgm.wav", SR, (mix * 32767).astype(np.int16))

    # 映像：つかみは動画を縦いっぱいに（生き物の位置に合わせて切り出し）
    d0, d1, d2, d3 = durs
    fc = (
        f"[0:v]trim=start=5.0:duration={d0},setpts=PTS-STARTPTS,crop=405:720:540:0,scale=1080:1920,setsar=1,fps=30[vid];"
        f"[vid][1:v]overlay=0:0,format=yuv420p[h];"
        f"[2:v]scale=1080:1920,zoompan=z='min(1.0+0.0009*on,1.08)':d={int(d1*30)}:s=1080x1920:fps=30,format=yuv420p[p];"
        f"[3:v]scale=1080:1920,zoompan=z='1.08':d={int(d2*30)}:s=1080x1920:fps=30,format=yuv420p[o];"
        f"[4:v]fps=30,format=yuv420p,trim=duration={d3}[e];"
        f"[h][p][o][e]concat=n=4:v=1:a=0[out];"
        f"[0:a]atrim=start=5.0:duration={d0},asetpts=PTS-STARTPTS,volume=0.6,apad=whole_dur={total}[tr];"
        f"[5:a][tr]amix=inputs=2:normalize=0,afade=t=out:st={total-0.6}:d=0.6[au]"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(SRC_VIDEO),
           "-loop", "1", "-t", str(d0), "-i", str(tmp / "hook.png"),
           "-i", str(tmp / "page.png"),
           "-i", str(tmp / "ochi.png"),
           "-loop", "1", "-t", str(d3), "-i", str(tmp / "end.png"),
           "-i", str(tmp / "voice_bgm.wav"),
           "-filter_complex", fc, "-map", "[out]", "-map", "[au]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", "-t", str(total), str(OUT)]
    subprocess.run(cmd, check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

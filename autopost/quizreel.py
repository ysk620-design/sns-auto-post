"""テスト回（reel_style: "quiz"）のクイズリールを作る。

カルーセルのスライドをそのまま流すのではなく、リール用に文字をしぼった画面を作る。
  問題（3択）→ 正解の発表 を、reel_questions で選んだ問題の数だけくり返し → 最後の画面
各画面の秒数は readtime.py の「読み切れる時間」で計算する。
  問題の画面 ＝ 目の移動 ＋ 問題文と選択肢を読む時間 ＋ 選ぶための間（DECIDE 秒）
  正解の画面 ＝ 目の移動 ＋ 正解の英文と解説を読む時間
問題の画面の下には、残り時間のバーを出し、最後の3秒でカチカチ音、正解の発表でチャイムを鳴らす。

post.json の書き方（テスト回）:
  slides の 2〜6枚目：layout "cards"、tag "Q1"〜"Q5"、title が問題、cards が ["A. 英文", ""] の3つ
  答え合わせ：layout "table"、rows が ["Q1　B", "解説"] の5行
  最後：layout "cta"、body が判定の4段階（<br> 区切り）
  reel_style: "quiz"、reel_questions: リールで出す問題の番号（例 [1, 2, 3]。省略すると [1, 2, 3]）
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from . import readtime

W, H = 1080, 1920
FPS = 30
DECIDE = 1.5  # 選択肢を読み終えてから、答えを選ぶための間（秒）
TICKS = 3  # 問題の画面の最後の何秒でカチカチ音を鳴らすか
DEFAULT_PICK = [1, 2, 3]
LETTERS = "ABC"

_Q_TAG = re.compile(r"^Q([1-5])$")
_ANS = re.compile(r"Q\s*([1-5])\D*?([ABCＡＢＣ])")
_CHOICE = re.compile(r"^\s*([ABCＡＢＣ])[\.．:：)\s]\s*")


def _plain(text) -> str:
    return readtime.plain(text).strip()


def parse(data: dict) -> tuple[list[dict], list[str], list[str]]:
    """(問題のリスト, 判定の行, 直してほしい点) を返す。"""
    errors: list[str] = []
    slides = data.get("slides") or []
    qs: dict[int, dict] = {}
    for s in slides:
        m = _Q_TAG.match(str(s.get("tag", "")).strip())
        if s.get("layout") == "cards" and m:
            choices = []
            for item in s.get("cards") or []:
                main = item[0] if isinstance(item, (list, tuple)) and item else str(item)
                choices.append(_CHOICE.sub("", _plain(main)))
            qs[int(m.group(1))] = {"no": int(m.group(1)), "q": _plain(s.get("title", "")), "choices": choices}
    answers: dict[int, tuple[int, str]] = {}
    for s in slides:
        if s.get("layout") != "table":
            continue
        for row in s.get("rows") or []:
            left = str(row[0]) if isinstance(row, (list, tuple)) and row else str(row)
            m = _ANS.search(_plain(left))
            if m:
                letter = "ABC"["ABCＡＢＣ".index(m.group(2)) % 3]
                answers[int(m.group(1))] = (LETTERS.index(letter), _plain(row[1]) if len(row) > 1 else "")
    count = max(qs) if qs else 0
    if count < 2:
        errors.append("問題のスライド（layout cards・tag「Q1」「Q2」…）が2枚以上必要です")
    for n in range(1, count + 1):
        if n not in qs:
            errors.append(f"Q{n} のスライド（layout cards・tag「Q{n}」）がありません")
        elif len(qs[n]["choices"]) != 3 or not all(qs[n]["choices"]):
            errors.append(f"Q{n} の選択肢は3つにしてください（[\"A. 英文\", \"\"] の形）")
        if n not in answers:
            errors.append(f"答え合わせの表に Q{n} の答え（「Q{n}　B」の形）がありません")
    out = []
    for n in sorted(qs):
        if n in answers:
            q = dict(qs[n])
            q["answer"], q["explain"] = answers[n]
            out.append(q)
    levels: list[str] = []
    last = slides[-1] if slides else {}
    if last.get("layout") == "cta" and last.get("body"):
        levels = [x.strip() for x in re.split(r"<br\s*/?>|\n", str(last["body"]), flags=re.I) if _plain(x)]
    if len(levels) < 2 and data.get("type") != "reel_only":
        errors.append("最後のスライド（layout cta）の body に、判定の段階を <br> 区切りで書いてください")
    return out, [_plain(x) for x in levels], errors


def pick(data: dict) -> list[int]:
    p = data.get("reel_questions") or DEFAULT_PICK
    return [int(x) for x in p]


def validate(data: dict) -> list[str]:
    _, _, errors = parse(data)
    p = data.get("reel_questions", DEFAULT_PICK)
    count = len(parse(data)[0])
    if not (isinstance(p, list) and p and all(isinstance(x, int) and 1 <= x <= max(count, 1) for x in p)
            and len(set(p)) == len(p)):
        errors.append(f"reel_questions は 1〜{max(count, 1)} の問題番号のリストにしてください（例 [1, 2, 3]）")
    return errors


def plan(data: dict, follow: str = "") -> list[dict]:
    """リールの画面の並びと秒数。follow は最後の画面に出すフォローのお誘い（accounts/*.json の matome_follow）。"""
    questions, levels, errors = parse(data)
    if errors:
        raise RuntimeError("クイズリールを作れません: " + " / ".join(errors))
    by_no = {q["no"]: q for q in questions}
    chosen = [by_no[n] for n in pick(data)]
    screens = []
    for i, q in enumerate(chosen, 1):
        sec_q = readtime.screen_seconds(q["q"], q["choices"], extra=DECIDE, minimum=4.0)
        screens.append({"kind": "question", "q": q, "i": i, "n": len(chosen), "sec": sec_q})
        right = q["choices"][q["answer"]]
        screens.append({"kind": "answer", "q": q, "i": i, "n": len(chosen),
                        "sec": readtime.screen_seconds(right, q["explain"], minimum=2.5)})
    standalone = data.get("type") == "reel_only"
    full = len(chosen) == len(questions)
    if standalone:
        # リールだけの投稿：カルーセルがないので、コメントを呼びかけて終わる
        lines = [data.get("quiz_end_title") or "何問わかった？", "コメントで教えてね"]
        if not follow:
            lines.append("ほかの話もプロフィールから")
    elif full and levels:
        lines = ["あなたのネイティブ度は？"] + levels
    else:
        lines = ["続きの問題と判定は", "プロフィールの投稿で", "全問わかるか挑戦してね"]
        full = False
    # フォローのお誘いも読み終わるまで映す
    screens.append({"kind": "end", "lines": lines, "full": full and not standalone, "follow": follow,
                    "sec": readtime.screen_seconds(lines, follow, extra=0.5 if follow else 1.0, minimum=3.5)})
    return screens


# ---------- 画面を描く ----------

class _Painter:
    def __init__(self, theme: dict, title: str, handle: str):
        from .reel import find_font

        self.t = theme
        self.title = title
        self.handle = handle
        self.font_path = find_font()

    def font(self, size: int):
        from PIL import ImageFont

        return ImageFont.truetype(self.font_path, size, index=0)

    def fit(self, draw, text: str, size: int, min_size: int, width: int, lines: int = 2):
        """幅に収まるように折り返し、行数が多ければ文字を小さくする。"""
        while True:
            f = self.font(size)
            wrapped = self.wrap(draw, text, f, width)
            # 最後の行が「と？」のように2〜3字だけになる折り返しは読みにくいので、文字を小さくして避ける
            orphan = len(wrapped) > 1 and len(wrapped[-1].strip()) <= 3
            if (len(wrapped) <= lines and not orphan) or size <= min_size:
                return f, wrapped
            size -= 4

    @staticmethod
    def wrap(draw, text: str, font, width: int) -> list[str]:
        out = []
        for para in text.split("\n"):
            words = re.findall(r"[A-Za-z0-9'’\.,!?\-]+|\s+|.", para)
            line = ""
            for w in words:
                if line and draw.textlength(line + w, font=font) > width:
                    out.append(line.rstrip())
                    line = w.lstrip()
                else:
                    line += w
            if line.strip():
                out.append(line.rstrip())
        return out

    def base(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (W, H), self.t["base"])
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, W, 250), fill=self.t["main"])
        f, lines = self.fit(d, self.title, 54, 36, W - 120, 1)
        d.text((W // 2, 140), lines[0] if lines else "", font=f, fill="#ffffff", anchor="mm")
        d.text((W // 2, H - 160), self.handle, font=self.font(34), fill=self.t["muted"], anchor="mm")
        return img, d

    def question(self, s: dict, reveal: bool, out: Path) -> dict:
        img, d = self.base()
        q = s["q"]
        pill = f"Q{s['i']} / {s['n']}" if s["n"] > 1 else "Q"
        pf = self.font(40)
        pw = d.textlength(pill, font=pf) + 64
        d.rounded_rectangle((80, 400, 80 + pw, 472), radius=36, fill=self.t["accent"])
        d.text((80 + pw / 2, 436), pill, font=pf, fill="#ffffff", anchor="mm")
        f, lines = self.fit(d, q["q"], 72, 48, W - 160, 3)
        y = 520
        for ln in lines:
            d.text((80, y), ln, font=f, fill=self.t["main"])
            y += int(f.size * 1.35)
        y = max(y + 70, 820)
        green = "#2e9e6b"
        for k, choice in enumerate(q["choices"]):
            right = k == q["answer"]
            cf, cl = self.fit(d, choice, 62, 40, 620, 2)
            hgt = max(170, 64 + len(cl) * int(cf.size * 1.3))
            box = (80, y, 940, y + hgt)
            if reveal and right:
                d.rounded_rectangle(box, radius=34, fill=green)
                fg, circle = "#ffffff", "#ffffff"
            elif reveal:
                d.rounded_rectangle(box, radius=34, fill="#ecebe6", outline="#d6d4cc", width=4)
                fg, circle = "#a8a8a8", "#c9c9c9"
            else:
                d.rounded_rectangle(box, radius=34, fill="#ffffff", outline=self.t["main"], width=5)
                fg, circle = self.t["main"], self.t["main"]
            cy = y + hgt // 2
            d.ellipse((115, cy - 40, 195, cy + 40), outline=circle, width=5,
                      fill=None if not (reveal and right) else green)
            d.text((155, cy), LETTERS[k], font=self.font(44), fill=circle, anchor="mm")
            ty = cy - (len(cl) * int(cf.size * 1.3)) // 2
            for ln in cl:
                d.text((230, ty), ln, font=cf, fill=fg)
                ty += int(cf.size * 1.3)
            if reveal:
                mark = "○" if right else "×"
                d.text((890, cy), mark, font=self.font(56), fill="#ffffff" if right else "#c9c9c9", anchor="mm")
            y += hgt + 40
        bar = {}
        if reveal:
            ef, el = self.fit(d, q["explain"], 48, 34, 780, 3)
            hgt = 70 + len(el) * int(ef.size * 1.4)
            d.rounded_rectangle((80, y + 16, 1000 - 60, y + 16 + hgt), radius=28, fill=self.t["accent_soft"])
            ty = y + 16 + 35
            for ln in el:
                d.text((120, ty), ln, font=ef, fill=self.t["main"])
                ty += int(ef.size * 1.4)
        else:
            by = min(y + 50, 1500)
            d.text((80, by), "考えてみて", font=self.font(36), fill=self.t["muted"])
            bar = {"x": 80, "y": by + 64, "w": 860, "h": 24}
            d.rounded_rectangle((80, by + 64, 940, by + 88), radius=12, fill=self.t["accent"])
        img.save(out)
        return bar

    def end(self, s: dict, out: Path) -> None:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (W, H), self.t["main"])
        d = ImageDraw.Draw(img)
        lines = s["lines"]
        follow = s.get("follow") or ""
        y = 520 if follow else 420
        head = self.font(66)
        d.text((W // 2, y), lines[0], font=head, fill="#ffffff", anchor="mm")
        y += 140
        for ln in lines[1:]:
            f, wl = self.fit(d, ln, 50 if s["full"] else 62, 34, W - 180, 2)
            for w in wl:
                d.text((W // 2, y), w, font=f, fill=self.t["accent_soft"] if s["full"] else "#ffffff", anchor="mm")
                y += int(f.size * 1.45)
            y += 34
        if not follow:
            tail = "何問わかった？コメントで教えてね" if s["full"] else "▶ " + self.handle
            d.text((W // 2, min(y + 80, 1500)), tail, font=self.font(42), fill="#ffffff", anchor="mm")
            img.save(out)
            return
        if s["full"]:
            d.text((W // 2, y + 30), "何問わかった？コメントで教えてね", font=self.font(40), fill="#ffffff", anchor="mm")
            y += 90
        # フォローのボタン（見終わった人に、フォローする理由を最後に見せる）
        by = min(y + 110, 1380)
        f, wl = self.fit(d, follow, 50, 36, W - 260, 2)
        lh = int(f.size * 1.4)
        bh = lh * len(wl) + 150
        d.rounded_rectangle((90, by, W - 90, by + bh), radius=44, fill=self.t["accent_soft"])
        ty = by + 50 + lh // 2
        for w in wl:
            d.text((W // 2, ty), w, font=f, fill=self.t["main"], anchor="mm")
            ty += lh
        d.text((W // 2, ty + 20), "＋ " + self.handle + " をフォロー", font=self.font(38), fill=self.t["main"], anchor="mm")
        img.save(out)


# ---------- 音 ----------

def _sfx(screens: list[dict], total: float, sr: int = 44100):
    import numpy as np

    out = np.zeros(int(sr * (total + 0.5)), np.float32)

    def tone(start: float, freqs, dur: float, vol: float):
        n = int(sr * dur)
        t = np.arange(n) / sr
        wave = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
        env = np.exp(-t * (18 / dur))
        s = int(sr * start)
        out[s:s + n] += (wave * env * vol)[: max(0, len(out) - s)]

    t0 = 0.0
    for sc in screens:
        if sc["kind"] == "question":
            for k in range(TICKS):
                tone(t0 + sc["sec"] - TICKS + k, [1500], 0.06, 0.35)
        elif sc["kind"] == "answer":
            tone(t0 + 0.02, [880, 1320], 0.5, 0.45)
            tone(t0 + 0.14, [1320, 1760], 0.6, 0.35)
        t0 += sc["sec"]
    return out


def make_quiz_reel(data: dict, theme: dict, title: str, handle: str, out_path: Path, follow: str = "") -> float:
    """クイズリールを書き出して、長さ（秒）を返す。"""
    import numpy as np
    from scipy.io import wavfile

    from .reel import ffmpeg_exe
    from .story.bgm import SR, make_bgm

    screens = plan(data, follow)
    total = sum(s["sec"] for s in screens)
    painter = _Painter(theme, title, handle)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS)]
        for i, s in enumerate(screens):
            png = tmp / f"s{i:02d}.png"
            n = max(1, round(s["sec"] * FPS))
            clip = tmp / f"p{i:02d}.mp4"
            if s["kind"] == "end":
                painter.end(s, png)
                bar = {}
            else:
                bar = painter.question(s, s["kind"] == "answer", png)
            cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-i", str(png)]
            if bar:
                # 残り時間のバー：背景と同じ色の箱を右から左へ動かして、バーを短くしていく
                cmd += ["-f", "lavfi", "-i", f"color=c={theme['base']}:s={bar['w'] + 20}x{bar['h'] + 8}:r={FPS}",
                        "-filter_complex",
                        f"[0:v][1:v]overlay=x='{bar['x']}+{bar['w']}*(1-t/{s['sec']})':y={bar['y'] - 4}:eval=frame"]
            cmd += ["-frames:v", str(n)] + enc + [str(clip)]
            subprocess.run(cmd, check=True)
            parts.append(clip)
        (tmp / "parts.txt").write_text("".join(f"file '{c}'\n" for c in parts), encoding="utf-8")

        bgm = make_bgm(total + 0.5)[: int(SR * total)] * 0.3
        sfx = _sfx(screens, total, SR)[: len(bgm)]
        mix = bgm + np.stack([sfx, sfx], 1)[: len(bgm)]
        fade = int(SR * 0.8)
        mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
        wavfile.write(tmp / "mix.wav", SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "parts.txt"),
             "-i", str(tmp / "mix.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-shortest", "-movflags", "+faststart", str(out_path)],
            check=True,
        )
    return round(total, 1)

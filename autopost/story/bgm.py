"""オリジナルのポップBGMを作る（自作なので著作権の心配なし）。"""
import numpy as np
from scipy.signal import lfilter

SR = 44100


def make_bgm(dur: float, bpm: float = 112, seed: int = 7) -> np.ndarray:
    """dur 秒のBGM（ステレオ、-1〜1 の float 配列）を返す。"""
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    N = int(SR * (dur + 1))
    L = np.zeros(N); R = np.zeros(N)

    def hz(m): return 440 * 2 ** ((m - 69) / 12)
    def env(n, a=0.005, d=0.25):
        t = np.arange(n) / SR
        e = np.minimum(1, t / a) * np.exp(-t / d)
        return e
    def osc(f, n, kind="sq", duty=0.5):
        t = np.arange(n) / SR
        ph = (f * t) % 1
        if kind == "sq": return np.where(ph < duty, 1.0, -1.0)
        if kind == "tri": return 4 * np.abs(ph - 0.5) - 1
        return np.sin(2 * np.pi * f * t)
    def add(buf, start, sig, pan=0.0, g=1.0):
        s = int(start * SR); e = min(N, s + len(sig))
        if s >= N: return
        L[s:e] += sig[:e - s] * g * (1 - pan) / 2 * 2
        R[s:e] += sig[:e - s] * g * (1 + pan) / 2 * 2
    def lp(x, a=0.15):  # 簡易ローパス
        return lfilter([a], [1, a - 1], x)

    # I-V-vi-IV in C
    prog = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
    # 弾むメロディ（8分音符、Noneは休符）
    mel = [[72, None, 76, 79, 76, None, 74, 72], [71, None, 74, 79, 74, None, 72, 71],
           [72, None, 76, 81, 79, 76, 74, None], [72, 74, 76, None, 77, 76, 74, 72]]
    bars = int(dur / (beat * 4)) + 2
    for b in range(bars):
        t0 = b * beat * 4
        root, chord = prog[b % 4]
        intro = b < 1
        for i in range(8):  # ベース（8分）
            n = int(SR * beat / 2 * 0.9)
            note = root + (12 if i % 2 else 0)
            add(L, t0 + i * beat / 2, lp(osc(hz(note), n, "tri"), 0.3) * env(n, 0.003, 0.18), 0, 0.5)
        for i in (1, 3, 5, 7):  # 裏拍のコード
            n = int(SR * beat * 0.45)
            s = sum(osc(hz(m), n, "sq", 0.25) for m in chord) / 3
            add(L, t0 + i * beat / 2, lp(s, 0.2) * env(n, 0.003, 0.08), 0.3, 0.22)
        if not intro:  # メロディ
            for i, m in enumerate(mel[b % 4]):
                if m is None: continue
                n = int(SR * beat / 2 * 0.95)
                s = lp(osc(hz(m), n, "sq", 0.5), 0.35) * env(n, 0.004, 0.16)
                add(L, t0 + i * beat / 2, s, -0.25, 0.20)
                add(L, t0 + i * beat / 2 + beat * 0.75, s * 0.35, 0.4, 0.20)  # ディレイ風
        for i in range(4):  # キック
            n = int(SR * 0.25); t = np.arange(n) / SR
            k = np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
            add(L, t0 + i * beat, k, 0, 0.9)
        if not intro:
            for i in (1, 3):  # クラップ
                n = int(SR * 0.18)
                c = rng.uniform(-1, 1, n) * env(n, 0.001, 0.05)
                add(L, t0 + i * beat, lp(c, 0.6), 0, 0.35)
        for i in range(8):  # ハイハット
            n = int(SR * 0.05)
            h = rng.uniform(-1, 1, n); h = h - lp(h, 0.5)
            add(L, t0 + i * beat / 2, h * env(n, 0.001, 0.015), 0.5 if i % 2 else -0.5, 0.25 if i % 2 else 0.12)

    n = int(SR * dur)
    mix = np.stack([L[:n], R[:n]], 1)
    fade = int(SR * 1.5)
    mix[:int(SR * 0.3)] *= np.linspace(0, 1, int(SR * 0.3))[:, None]
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.2) * 0.85
    return mix

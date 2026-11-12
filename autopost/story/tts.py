"""VOICEVOX で台本を1画面ずつ読み上げる。

VOICEVOX 本体は scripts/setup_voicevox.sh で ~/.cache/voicevox（環境変数 VOICEVOX_DIR で変更可）に入れる。
音声を使うときは「VOICEVOX:冥鳴ひまり」のように、声のクレジット表記が必要。
"""
from __future__ import annotations

import os
from pathlib import Path

_synth = None


def voicevox_dir() -> Path:
    return Path(os.environ.get("VOICEVOX_DIR") or Path.home() / ".cache" / "voicevox")


def available() -> bool:
    try:
        import voicevox_core  # noqa: F401
    except ImportError:
        return False
    d = voicevox_dir()
    return any(d.glob("models/*.vvm")) and any(d.glob("onnxruntime/lib/libvoicevox_onnxruntime.so*"))


def _synthesizer():
    global _synth
    if _synth is None:
        from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

        d = voicevox_dir()
        lib = sorted(d.glob("onnxruntime/lib/libvoicevox_onnxruntime.so*"))[-1]
        dic = next(p for p in d.glob("open_jtalk_dic*") if p.is_dir())
        syn = Synthesizer(Onnxruntime.load_once(filename=str(lib)), OpenJtalk(str(dic)))
        for f in sorted(d.glob("models/*.vvm")):
            with VoiceModelFile.open(f) as m:
                syn.load_voice_model(m)
        _synth = syn
    return _synth


def speak(text: str, voice: dict) -> bytes:
    """text を読み上げた wav（44.1kHz・モノラル）を返す。"""
    syn = _synthesizer()
    sid = int(voice["style_id"])
    q = syn.create_audio_query(text, sid)
    for ap in q.accent_phrases:  # 読点などの間を伸ばす
        pm = ap["pause_mora"] if isinstance(ap, dict) else ap.pause_mora
        if not pm:
            continue
        if isinstance(pm, dict):
            pm["vowel_length"] *= float(voice["pause"])
        else:
            pm.vowel_length *= float(voice["pause"])
    q.speed_scale = float(voice["speed"])
    q.pitch_scale = float(voice["pitch"])
    q.intonation_scale = float(voice["intonation"])
    q.pre_phoneme_length, q.post_phoneme_length = 0.05, 0.1
    q.output_sampling_rate, q.output_stereo = 44100, False
    return syn.synthesis(q, sid)

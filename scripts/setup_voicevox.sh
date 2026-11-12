#!/usr/bin/env bash
# リールの読み上げ音声に使う VOICEVOX（音声合成）を用意する。
# 使う声は「冥鳴ひまり」（1.vvm）。音声を使うときは「VOICEVOX:冥鳴ひまり」のクレジット表記が必要。
# 利用規約：https://github.com/VOICEVOX/voicevox_vvm/blob/main/TERMS.txt
set -euo pipefail

core="0.16.2"
ort="1.17.3"
dir="${VOICEVOX_DIR:-$HOME/.cache/voicevox}"
mkdir -p "$dir/models" "$dir/onnxruntime"

python -c "import voicevox_core" 2>/dev/null || pip install -q \
  "https://github.com/VOICEVOX/voicevox_core/releases/download/${core}/voicevox_core-${core}-cp310-abi3-manylinux_2_34_x86_64.whl"
python -c "import numpy, scipy" 2>/dev/null || pip install -q numpy scipy

if ! ls "$dir"/onnxruntime/lib/libvoicevox_onnxruntime.so* > /dev/null 2>&1; then
  curl -fsSL --retry 3 "https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-${ort}/voicevox_onnxruntime-linux-x64-${ort}.tgz" \
    | tar -xz -C "$dir/onnxruntime" --strip-components=1
fi

if [ ! -d "$dir/open_jtalk_dic_utf_8-1.11" ]; then
  curl -fsSL --retry 3 "https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz" \
    | tar -xz -C "$dir"
fi

[ -s "$dir/models/1.vvm" ] || curl -fsSL --retry 3 -o "$dir/models/1.vvm" \
  "https://github.com/VOICEVOX/voicevox_vvm/releases/download/${core}/1.vvm"

python -c "from autopost.story import tts; assert tts.available(); print('VOICEVOX の準備ができました')"

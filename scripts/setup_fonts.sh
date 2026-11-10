#!/usr/bin/env bash
# スライド画像に使うフォント（Noto Sans CJK JP と絵文字）を用意する。
# apt でのインストールは時間がかかることがあるので、公式リポジトリから直接ダウンロードする。
set -euo pipefail

dir="${HOME}/.local/share/fonts"
mkdir -p "$dir"

cjk="https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese"
for weight in Regular Medium Bold Black; do
  file="$dir/NotoSansCJKjp-$weight.otf"
  [ -s "$file" ] || curl -fsSL --retry 3 -o "$file" "$cjk/NotoSansCJKjp-$weight.otf"
done

emoji="$dir/NotoColorEmoji.ttf"
[ -s "$emoji" ] || curl -fsSL --retry 3 -o "$emoji" \
  "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/2D/fonts/NotoColorEmoji.ttf"

fc-cache -f "$dir" > /dev/null
fc-list | grep -E "Noto Sans CJK JP|Noto Color Emoji" | head -3

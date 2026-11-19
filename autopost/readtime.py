"""画面の文字量から「読み切れる表示時間（秒）」を計算する。

リールは見る人が止められない前提で、字幕の研究と日本人の英語学習者の読む速さを基準にする。

- 日本語：1秒6字（JP_CPS）
  映画字幕の「1秒4字」は、6字まで増やしても視線の停留時間（読む負担）が変わらず、8字で負担が増えた
  （豊倉・山田 2017「字幕翻訳における文字数制限の妥当性についての検証〜1秒4文字は妥当か?〜」）。
  Netflix の日本語字幕の上限（翻訳字幕 4字/秒、日本語音声の字幕 7字/秒）の間でもある。
  参考：大学生の黙読の平均は1分653字＝約11字/秒（小林・川嶋 2018）。画面を見続ける動画では、それより遅く見積もる
- 英語：1分100語（EN_WPM）
  日本人の大学生（CEFR A2 前後）の英文を読む速さは 93〜118語/分（日本大学の速読研究の先行研究まとめ）。
  100語/分までが「普通の読み」の区切り（安藤 1979、門田ほか 2010）。リールの読者は「英語をやり直したい大人」なので、この値にする
- 数字：2けた以上の半角数字は1字を0.5字として数える（字幕の慣習）
- 記号・絵文字・句読点は数えない
- 画面が切り替わってから、目が文字の始まりを見つけるまで：BASE 秒を足す（1回の注視は約0.24秒、数回ぶん）
"""
from __future__ import annotations

import re

JP_CPS = 6.0
EN_WPM = 100.0
BASE = 0.8
MIN_SEC = 2.0
MAX_SEC = 12.0  # これを超える画面は、文字が多すぎる（validate で注意を出す）

_TAG = re.compile(r"<[^>]+>")
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_DIGITS = re.compile(r"[0-9０-９]")
_JP = re.compile(r"[぀-ヿ㐀-鿿豈-﫿ｦ-ﾟ々〆ヵヶー]")


def plain(text) -> str:
    text = re.sub(r"<br\s*/?>", " ", str(text or ""), flags=re.I)
    return _TAG.sub("", text)


def count(text) -> tuple[float, int]:
    """(日本語の字数, 英単語の数) を返す。数字は0.5字。"""
    t = plain(text)
    words = len(_EN_WORD.findall(t))
    t = _EN_WORD.sub(" ", t)
    jp = len(_JP.findall(t)) + 0.5 * len(_DIGITS.findall(t))
    return jp, words


def reading_seconds(*texts) -> float:
    """読むのにかかる秒数（BASE を含まない）。"""
    jp = en = 0.0
    for t in texts:
        if isinstance(t, (list, tuple)):
            for x in t:
                a, b = count(x)
                jp += a
                en += b
        else:
            a, b = count(t)
            jp += a
            en += b
    return jp / JP_CPS + en / (EN_WPM / 60)


def screen_seconds(*texts, extra: float = 0.0, minimum: float = MIN_SEC) -> float:
    """1画面の表示秒数（目の移動 BASE ＋ 読む時間 ＋ extra）。0.1秒単位に切り上げる。"""
    sec = BASE + reading_seconds(*texts) + extra
    return round(max(minimum, -(-sec * 10 // 1) / 10), 1)


# スライドのうち、読ませたい文字の項目（tag・foot・ページ番号・ボタンは数えない）
_SLIDE_FIELDS = ("kicker", "top", "ng", "bottom", "big", "sub", "badge", "label", "title", "body", "note",
                 "question", "answer", "cta")


def slide_texts(s: dict) -> list[str]:
    out = [s[k] for k in _SLIDE_FIELDS if isinstance(s.get(k), str)]
    for key in ("cards", "rows"):
        for item in s.get(key) or []:
            if isinstance(item, (list, tuple)):
                out += [str(x) for x in item]
            elif isinstance(item, dict):
                out += [str(item.get("main", "")), str(item.get("sub", ""))]
            else:
                out.append(str(item))
    out += [str(p) for p in s.get("points") or []]
    return out


def slide_seconds(s: dict) -> float:
    return screen_seconds(slide_texts(s))

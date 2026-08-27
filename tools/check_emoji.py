# -*- coding: utf-8 -*-
"""index.html の絵文字が、2012年iPad（iOS 10.3.3）で表示できる世代かを検査する。

背景（2026-08-26実測）:
  ねるまえの札に使った 🧹（U+1F9F9）が実機で ☒（豆腐＝字が無い印）になった。
  U+1F9xx 帯は Unicode 11.0（2018年）で、2016年で更新が止まった端末には存在しない。
  同じ理由で 🧸（U+1F9F8）も休日の札で ☒ になっていた（公開済み・未検証だった）。

考え方:
  「新しい絵文字を禁止リストで数え上げる」のではなく、
  **許可した符号位置だけを通す（default-deny）**。
  新しい絵文字を使いたくなったら、この表へ意識して足す＝その時に世代を確認する。
  実機で表示を確認できたものだけを「確認済」に格上げする。

終了コード: 0=合格 / 1=不合格（表に無い絵文字がある）
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), 'index.html')

# 許可する符号位置。コメントは「世代」と「実機で見えた実績」。
ALLOW = {
    0x1F45F: '👟 Unicode6.0 実機OK',
    0x1F4A7: '💧 Unicode6.0 実機OK',
    0x1F455: '👕 Unicode6.0 実機OK',
    0x1F374: '🍴 Unicode6.0 実機OK',
    0x1F375: '🍵 Unicode6.0（同世代の他の絵文字が実機OK）',
    0x1F35A: '🍚 Unicode6.0 実機OK',
    0x1F6C1: '🛁 Unicode6.0 実機OK',
    0x270F: '✏ Unicode1.1 実機OK',
    0x1F601: '😁 Unicode6.0 実機OK',
    0x1F4A6: '💦 Unicode6.0 実機OK',
    0x1F43E: '🐾 Unicode6.0 実機OK',
    0x1F392: '🎒 Unicode6.0 実機OK',
    0x1F4E6: '📦 Unicode6.0（同世代の他の絵文字が実機OK）',
    0x1F319: '🌙 Unicode6.0 実機OK',
    0x2668: '♨ Unicode1.1 実機OK',
    0x1F31E: '🌞 Unicode6.0',
    0x1F4AE: '💮 Unicode6.0 実機OK',
    0x2B50: '⭐ Unicode5.1 実機OK',
    0x1F338: '🌸 Unicode6.0 実機OK',
    0x2728: '✨ Unicode6.0 実機OK',
    0x1F389: '🎉 Unicode6.0 実機OK',
    0x1F381: '🎁 Unicode6.0 実機OK',
    0x23F0: '⏰ Unicode6.0 実機OK',
    0x2705: '✅ Unicode6.0',
    0x2699: '⚙ Unicode4.1 実機OK',
    0x270B: '✋ Unicode6.0 v7から公開中',
    0xFE0F: '（絵文字表示の指定・字ではない）',
    0x200D: '（つなぎ文字・字ではない）',
}

# 絵文字が住んでいる帯（ここに入る文字だけを検査対象にする）
RANGES = [
    (0x2190, 0x21FF), (0x2300, 0x23FF), (0x2460, 0x24FF), (0x25A0, 0x27BF),
    (0x2900, 0x297F), (0x2B00, 0x2BFF), (0x1F000, 0x1FAFF), (0xFE00, 0xFE0F),
    (0x200D, 0x200D), (0x2600, 0x26FF),
]

# 記号として昔から使っている文字（絵文字ではない）は素通しする
PLAIN_OK = set(range(0x2460, 0x2470)) | {  # ①②③…
    0x25B6, 0x23EA, 0x23E9, 0x23EE, 0x23ED, 0x2714, 0x2715, 0x2716,
    0x2728, 0x2261, 0x2776, 0x279C, 0x2192, 0x2190, 0x2b1b,
    0x21C4, 0x25CB, 0x25EF,
}


def in_range(cp):
    for a, b in RANGES:
        if a <= cp <= b:
            return True
    return False


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    # HTMLの数値文字参照（&#9654; など）は素通し＝ここでは実体の文字だけを見る
    bad = {}
    for i, ch in enumerate(src):
        cp = ord(ch)
        if not in_range(cp):
            continue
        if cp in ALLOW or cp in PLAIN_OK:
            continue
        line = src.count('\n', 0, i) + 1
        bad.setdefault(cp, []).append(line)

    if bad:
        sys.stderr.write('NG: 2012年iPadで出ない可能性がある文字が %d 種あります\n' % len(bad))
        for cp in sorted(bad):
            lines = ', '.join(str(x) for x in bad[cp][:5])
            sys.stderr.write('  U+%05X %s  行 %s\n' % (cp, chr(cp), lines))
        sys.stderr.write('対処: 古い世代（Unicode 6.0以前）の絵文字へ替えるか、\n')
        sys.stderr.write('      世代を確認したうえで tools/check_emoji.py の ALLOW へ足す。\n')
        sys.exit(1)

    sys.stdout.write('PASS: 絵文字はすべて許可した世代のものです\n')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""index.html の ZUKAN の表と、img/zukan/ の絵が1対1で過不足ないかを検査する。

背景:
  ずかんの枠は「表に書いた id」から絵のファイル名を組み立てる。
  綴りを1文字まちがえるだけで、その枠だけ絵が出なくなる（画面では気づきにくい）。

考え方:
  **表に載っている物だけを通す（default-deny）**。
  表に無い絵がフォルダに残っていても不合格にする＝消し忘れを溜めない。
  check_emoji.py と同じ方式。

終了コード: 0=合格 / 1=不合格
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
INDEX = os.path.join(REPO, 'index.html')
IMG_DIR = os.path.join(REPO, 'img', 'zukan')

# ZUKAN = [ ... ] の中身だけを取り出す
BLOCK = re.compile(r'var\s+ZUKAN\s*=\s*\[(.*?)\n\];', re.S)
ENTRY = re.compile(r"\{\s*id\s*:\s*'([^']+)'\s*,\s*name\s*:\s*'([^']+)'\s*,\s*note\s*:\s*'([^']+)'\s*\}", re.S)
START = re.compile(r"var\s+ZUKAN_START\s*=\s*\[([^\]]*)\]")


def main():
    src = io.open(INDEX, encoding='utf-8').read()

    m = BLOCK.search(src)
    if not m:
        print('NG: index.html に ZUKAN の表が見つからない')
        return 1
    entries = ENTRY.findall(m.group(1))
    if not entries:
        print('NG: ZUKAN の表から1件も読み取れない（書き方が変わった可能性）')
        return 1

    ng = []
    ids = []
    for bid, name, note in entries:
        if bid in ids:
            ng.append(u'id が重複: ' + bid)
        ids.append(bid)
        if not name.strip():
            ng.append(u'name が空: ' + bid)
        if not note.strip():
            ng.append(u'note が空: ' + bid)

    if not os.path.isdir(IMG_DIR):
        print('NG: 絵のフォルダが無い: ' + IMG_DIR)
        return 1

    want = set()
    for bid in ids:
        want.add(bid + '.png')
        want.add(bid + '_s.png')

    have = set(f for f in os.listdir(IMG_DIR) if f.endswith('.png'))

    for f in sorted(want - have):
        ng.append(u'絵が無い: img/zukan/' + f)
    for f in sorted(have - want):
        ng.append(u'表に無い絵が残っている: img/zukan/' + f)

    # はじめから入れておく虫が、表に載っているか
    ms = START.search(src)
    if not ms:
        ng.append(u'ZUKAN_START が見つからない')
    else:
        for bid in re.findall(r"'([^']+)'", ms.group(1)):
            if bid not in ids:
                ng.append(u'ZUKAN_START の ' + bid + u' が ZUKAN の表に無い')

    if ng:
        print('NG: むしずかんの検査に不合格（%d件）' % len(ng))
        for line in ng:
            print('  - ' + line)
        return 1

    print('PASS: むしずかん %d種・絵 %d枚 が過不足なく そろっています' % (len(ids), len(want)))
    return 0


sys.exit(main())

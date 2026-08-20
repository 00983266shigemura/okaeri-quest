# -*- coding: utf-8 -*-
"""index.html の APP_VERSION と version.txt の数字が一致しているか確かめる。

一致していないと、しげのiPadに直しが届かない（version.txt が小さい場合）か、
新しいファイルを取りに行き続ける空振りが起きる（version.txt が大きい場合）。
公開の前にこれを実行し、PASS を確認する。

終了コード: 0=一致 / 1=不一致・読み取り失敗
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, 'index.html')
VERSION = os.path.join(ROOT, 'version.txt')


def fail(msg):
    sys.stdout.write('FAIL: %s\n' % msg)
    sys.exit(1)


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    m = re.search(r'^var APP_VERSION = (\d+);$', src, re.M)
    if not m:
        fail('index.html に APP_VERSION の行が見つかりません')
    app = int(m.group(1))

    if not os.path.exists(VERSION):
        fail('version.txt がありません')
    raw = io.open(VERSION, encoding='utf-8').read().strip()
    if not re.match(r'^\d+$', raw):
        fail('version.txt の中身が数字だけではありません: %r' % raw)
    ver = int(raw)

    if app != ver:
        fail('数字が食い違っています: index.html=%d / version.txt=%d' % (app, ver))

    sys.stdout.write('PASS: 版数は一致しています (=%d)\n' % app)


if __name__ == '__main__':
    main()

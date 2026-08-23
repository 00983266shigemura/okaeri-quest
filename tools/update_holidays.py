# -*- coding: utf-8 -*-
"""index.html に埋め込んだ祝日一覧(JP_HOLIDAYS)を、holidays-jp のAPIから最新化する。

- 取得元: https://holidays-jp.github.io/api/v1/date.json
  （内閣府発表にもとづく日本の祝日。前年・今年・翌年の3年分を返す）
- 失敗時・データが疑わしい時は index.html を一切書き換えずに終了する
  （壊れた祝日表で公開しないため。前回の値がそのまま残る＝安全側）。
- 変更が無ければ何も書かない（無駄なコミットを作らないため）。
- update_video_lists.py と同じ作法（1行だけを正規表現で書き換える）。

終了コード: 0=正常(変更あり/なしを問わず) / 1=失敗(書き換えなし)
"""
import datetime
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), 'index.html')
API = 'https://holidays-jp.github.io/api/v1/date.json'
LINE_RE = re.compile(r'^var JP_HOLIDAYS = (.*);$', re.M)
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def fail(msg):
    sys.stderr.write('NG: %s\n' % msg)
    sys.exit(1)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'okaeri-quest-updater'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                fail('取得失敗 HTTP %s: %s' % (r.status, url))
            return r.read().decode('utf-8', 'replace')
    except Exception as e:
        fail('取得できませんでした (%s): %s' % (e, url))


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    m = LINE_RE.search(src)
    if not m:
        fail('index.html に JP_HOLIDAYS の行が見つかりません')

    try:
        data = json.loads(fetch(API))
    except ValueError as e:
        fail('祝日データを読み取れません: %s' % e)
    if not isinstance(data, dict):
        fail('祝日データの形が想定外です（辞書ではない）')

    # データの妥当性検査。1つでも欠けたら書き換えない（前回の値を守る）
    keys = sorted(data.keys())
    if len(keys) < 30 or len(keys) > 200:
        fail('祝日の件数が想定外です: %d件' % len(keys))
    for k in keys:
        if not DATE_RE.match(k):
            fail('日付の形が想定外です: %s' % k)
    today = datetime.date.today().isoformat()
    if keys[-1] < today:
        fail('祝日データが古すぎます（最終日 %s < 今日 %s）' % (keys[-1], today))

    new_line = 'var JP_HOLIDAYS = ' + json.dumps(
        {k: 1 for k in keys}, separators=(",", ":")) + ';'
    if new_line == m.group(0):
        sys.stdout.write('変更なし\n')
        return

    out = src[:m.start()] + new_line + src[m.end():]
    if LINE_RE.search(out) is None:
        fail('書き換え後の検算に失敗しました')
    io.open(INDEX, 'w', encoding='utf-8').write(out)
    sys.stdout.write('祝日一覧を更新しました（%d件）\n' % len(keys))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""index.html に埋め込んだ動画一覧(VIDEO_LISTS)を、各チャンネルのRSSから最新化する。

- 対象チャンネルは index.html の現在の VIDEO_LISTS から自動で読み取る
  （list の "UU..." を "UC..." に戻したものがチャンネルID）。
- 失敗時は index.html を一切書き換えずに終了する（壊れた状態で公開しないため）。
- 変更が無ければ何も書かない（無駄なコミットを作らないため）。

終了コード: 0=正常(変更あり/なしを問わず) / 1=失敗(書き換えなし)
"""
import io
import json
import os
import re
import sys
import html
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), 'index.html')
FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id=%s'
MAX_ITEMS = 15
LINE_RE = re.compile(r'^var VIDEO_LISTS = (.*);$', re.M)


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


def parse_feed(xml):
    items = []
    for entry in re.findall(r'<entry>(.*?)</entry>', xml, re.S):
        mid = re.search(r'<yt:videoId>([\w-]+)</yt:videoId>', entry)
        mti = re.search(r'<title>(.*?)</title>', entry, re.S)
        if mid and mti:
            items.append({'id': mid.group(1), 't': html.unescape(mti.group(1)).strip()})
        if len(items) >= MAX_ITEMS:
            break
    return items


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    m = LINE_RE.search(src)
    if not m:
        fail('index.html に VIDEO_LISTS の行が見つかりません')

    try:
        lists = json.loads(m.group(1))
    except ValueError as e:
        fail('VIDEO_LISTS を読み取れません: %s' % e)
    if not lists:
        fail('VIDEO_LISTS が空です')

    updated = {}
    for key in sorted(lists.keys()):
        playlist = lists[key].get('list', '')
        if not playlist.startswith('UU'):
            fail('%s の再生リストIDが想定外です: %s' % (key, playlist))
        channel = 'UC' + playlist[2:]
        items = parse_feed(fetch(FEED % channel))
        if not items:
            fail('%s (%s) から動画を取得できませんでした' % (key, channel))
        updated[key] = {'list': playlist, 'items': items}
        sys.stdout.write('%s: %d本\n' % (key, len(items)))

    new_line = 'var VIDEO_LISTS = ' + json.dumps(
        updated, ensure_ascii=False, separators=(",", ":")) + ';'
    if new_line == m.group(0):
        sys.stdout.write('変更なし\n')
        return

    out = src[:m.start()] + new_line + src[m.end():]
    if LINE_RE.search(out) is None:
        fail('書き換え後の検算に失敗しました')
    io.open(INDEX, 'w', encoding='utf-8').write(out)
    sys.stdout.write('更新しました\n')


if __name__ == '__main__':
    main()

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
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), 'index.html')
FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id=%s'
OEMBED = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json'
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


def embeddable(vid):
    """動画側で埋め込みが禁止・非公開・削除されていないかを、YouTube公式の照会口(oEmbed)で確かめる。

    401/403/404 = 埋め込み不可・見られない動画として除外する
    （2026-08-28実測: ぷち一覧の1本が401=どの端末でも再生できないまま一覧に居座っていた）。
    通信エラー等は判定不能=残す（安全側。一覧を空にしないことを優先）。
    """
    req = urllib.request.Request(OEMBED % vid, headers={'User-Agent': 'okaeri-quest-updater'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return False
        return True
    except Exception:
        return True


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
        kept = [it for it in items if embeddable(it['id'])]
        if len(kept) < len(items):
            sys.stdout.write('%s: 埋め込み不可 %d本を除外\n' % (key, len(items) - len(kept)))
        if not kept:
            fail('%s (%s) は埋め込み可の動画が0本でした' % (key, channel))
        updated[key] = {'list': playlist, 'items': kept}
        sys.stdout.write('%s: %d本\n' % (key, len(kept)))

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

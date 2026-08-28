# -*- coding: utf-8 -*-
"""ごほうび動画の一覧を、しげの再生リストの「いまの中身」に合わせる。

しげの操作は、YouTubeの再生リストへ **保存する / 外す** だけ。
アプリの一覧は毎朝それに合わせて作り直される（CCの改修もpushも要らない）。

設計の要点（2026-08-28・査読の指摘を受けて「貯める方式」を捨てた）:
  - **貯めない。** 毎回、再生リストのいまの中身をそのまま写す。
    貯める方式は、しげが再生リストから **外した動画を落とせない**（外した動画は
    YouTube上では生きているので、埋め込み可否の検査を通ってしまう）。
    それでは「飽きたら入れ替える」ができず、この道具の目的を果たさない。
  - 写すだけなので、足したぶんも外したぶんも翌朝そのまま効く。
  - RSSが返すのは再生リストの先頭15本まで。**しげには「並び替え＝追加日の新しい順」に
    しておいてもらう**（そうすれば足した動画が必ず先頭に入る）。
  - 動画側が埋め込みを禁止・非公開・削除したものは、YouTube公式の照会口(oEmbed)で落とす
    （どの端末でも再生できないため。2026-08-28に1本が実在）。

安全側の作り:
  - 取得に失敗したら index.html を一切書き換えずに終了する
  - 判定できなかった動画は残す（一覧を空にしないことを優先）
  - 変更が無ければ何も書かない

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
FEED = 'https://www.youtube.com/feeds/videos.xml?playlist_id=%s'
OEMBED = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json'
UA = 'okaeri-quest-updater'
LINE_RE = re.compile(r'^var VIDEO_LISTS = (.*);$', re.M)
MAX_ITEMS = 15


def fail(msg):
    sys.stderr.write('NG: %s\n' % msg)
    sys.exit(1)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                fail('取得失敗 HTTP %s: %s' % (r.status, url))
            return r.read().decode('utf-8', 'replace')
    except Exception as e:
        fail('取得できませんでした (%s): %s' % (e, url))


def embeddable(vid):
    """動画側が埋め込みを許しているか。401/403/404=不可。判定できない時は残す（安全側）。"""
    req = urllib.request.Request(OEMBED % vid, headers={'User-Agent': UA})
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
        if not re.match(r'^(UU|PL)[\w-]+$', playlist):
            fail('%s の再生リストIDが想定外です: %s' % (key, playlist))

        items = parse_feed(fetch(FEED % playlist))
        if not items:
            fail('%s (%s) から動画を取得できませんでした' % (key, playlist))

        kept = [it for it in items if embeddable(it['id'])]
        if len(kept) < len(items):
            sys.stdout.write('%s: 見られない動画 %d本を外しました\n'
                             % (key, len(items) - len(kept)))
        if not kept:
            fail('%s (%s) は見られる動画が0本でした' % (key, playlist))

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

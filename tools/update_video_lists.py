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
CHANNEL_FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id=%s'
PLAYLIST_FEED = 'https://www.youtube.com/feeds/videos.xml?playlist_id=%s'
OEMBED = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json'
UA = 'okaeri-quest-updater'
LINE_RE = re.compile(r'^var VIDEO_LISTS = (.*);$', re.M)
PER_SOURCE = 15      # 1つの供給源から取る本数（RSSが返す上限）
MAX_ITEMS = 30       # 1つの枠に載せる上限（複数チャンネルを混ぜたときの合計）


def feed_url(src):
    """供給源のIDから、取りにいくRSSのURLを決める。

    UU…＝チャンネルの投稿一覧。UCへ戻して **チャンネルのRSS** を使う。
      こちらは2026-08-26まで毎朝動いていた実績がある（便のログで実測）。
    PL…＝しげが作った再生リスト。再生リストのRSSを使う。
    実績のある経路をわざわざ変えない、というのがこの分岐の趣旨。
    """
    if src.startswith('UU'):
        return CHANNEL_FEED % ('UC' + src[2:])
    return PLAYLIST_FEED % src


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
    """1件ずつから 動画ID・題名・公開日 を取り出す。公開日は複数チャンネルを混ぜて
    新しい順に並べるために使う（RSSは供給源ごとにしか並んでいないため）。"""
    items = []
    for entry in re.findall(r'<entry>(.*?)</entry>', xml, re.S):
        mid = re.search(r'<yt:videoId>([\w-]+)</yt:videoId>', entry)
        mti = re.search(r'<title>(.*?)</title>', entry, re.S)
        mpu = re.search(r'<published>([^<]+)</published>', entry)
        if mid and mti:
            items.append({'id': mid.group(1),
                          't': html.unescape(mti.group(1)).strip(),
                          'pub': mpu.group(1).strip() if mpu else ''})
        if len(items) >= PER_SOURCE:
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
        conf = lists[key]
        primary = conf.get('list', '')
        # 供給源は複数書ける（channels）。書いていなければ list の1つだけを使う。
        srcs = conf.get('channels') or [primary]
        if not srcs or not all(re.match(r'^(UU|PL)[\w-]+$', s) for s in srcs):
            fail('%s の供給源IDが想定外です: %s' % (key, srcs))

        merged, seen = [], set()
        for s in srcs:
            got = parse_feed(fetch(feed_url(s)))
            if not got:
                fail('%s (%s) から動画を取得できませんでした' % (key, s))
            for it in got:
                if it['id'] not in seen:      # 同じ動画が複数の供給源にあっても1本にする
                    seen.add(it['id'])
                    merged.append(it)
            if len(srcs) > 1:
                sys.stdout.write('%s: %s から %d本\n' % (key, s, len(got)))

        # 新しい順に並べる（複数チャンネルを混ぜても公開日で一列にする）
        merged.sort(key=lambda e: (e.get('pub', ''), e['id']), reverse=True)

        kept = [it for it in merged if embeddable(it['id'])]
        if len(kept) < len(merged):
            sys.stdout.write('%s: 見られない動画 %d本を外しました\n'
                             % (key, len(merged) - len(kept)))
        if not kept:
            fail('%s は見られる動画が0本でした' % key)

        kept = kept[:MAX_ITEMS]
        out_conf = {'list': primary}
        if conf.get('channels'):
            out_conf['channels'] = srcs
        out_conf['items'] = [{'id': e['id'], 't': e['t']} for e in kept]
        updated[key] = out_conf
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

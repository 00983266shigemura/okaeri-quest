# -*- coding: utf-8 -*-
"""ごほうび動画の一覧を、登録したチャンネルの最新に合わせる（毎朝1回）。

しげの操作は、index.html の VIDEO_SOURCES にチャンネルを足す・やめるだけ。
子どもは「どの チャンネルに する？」の画面で、その枠のチャンネルから選ぶ。

設計の要点（2026-08-28）:
  - **貯めない。** 毎回、チャンネルのいまの新着をそのまま写す。
    貯める方式は「一覧から外れたもの」を落とせず、中身の入れ替えができない（査読で撤回）。
  - **チャンネルごとに分けて持つ**（混ぜない）。選択画面で子どもが選べるようにするため。
  - 各チャンネルの中は公開が新しい順。
  - 動画側が埋め込みを禁止・非公開・削除したものは、YouTube公式の照会口(oEmbed)で落とす
    （どの端末でも再生できないため。2026-08-28に1本が実在）。
  - 題名の絵文字は落とす（clean_title）。題名はYouTube側の文字で、こちらでは選べないため。

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




def clean_title(t):
    """題名から絵文字・記号を取り除く。

    題名はYouTube側の文字なので、こちらでは選べない。2012年iPadに無い世代の絵文字が
    入っていると、子どもの画面で ☒（字が無い印）になる（2026-08-26に実際に発生）。
    絵文字を消しても題名の意味は残るので、まるごと落とすのがいちばん確実。
    許可表を足していく方式では、新しい題名が来るたびに毎回止まってしまう。
    """
    out = []
    for ch in t:
        o = ord(ch)
        if (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF
                or o in (0xFE0F, 0xFE0E, 0x20E3) or 0x2190 <= o <= 0x21FF
                or 0x2B00 <= o <= 0x2BFF or 0x3030 == o or 0x303D == o
                or 0x2000 <= o <= 0x200D or 0x2049 == o or 0x203C == o):
            continue
        out.append(ch)
    s = ''.join(out)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s or '(だいめい なし)'


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
                          't': clean_title(html.unescape(mti.group(1))),
                          'pub': mpu.group(1).strip() if mpu else ''})
        if len(items) >= PER_SOURCE:
            break
    return items


def read_sources(src):
    """index.html の VIDEO_SOURCES（しげが決める枠とチャンネルの表）を読む。

    JavaScriptの書き方のままなので、キーを二重引用符でくくってJSONとして読み直す。
    ここを正本にすることで、チャンネルの追加・削除は index.html の1箇所で済む。
    """
    m = re.search(r'^var VIDEO_SOURCES = (\{[\s\S]*?\n\});$', src, re.M)
    if not m:
        fail('index.html に VIDEO_SOURCES が見つかりません')
    body = m.group(1)
    body = re.sub(r'/\*[\s\S]*?\*/', '', body)         # コメントを外す
    body = re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', body)   # キーを引用符で囲む
    body = body.replace("'", '"')
    body = re.sub(r',\s*([}\]])', r'\1', body)          # 末尾のコンマを外す
    try:
        data = json.loads(body)
    except ValueError as e:
        fail('VIDEO_SOURCES を読み取れません: %s' % e)
    frames = {}
    for key, arr in data.items():
        if not isinstance(arr, list) or not arr:
            fail('VIDEO_SOURCES の %s が空です' % key)
        for s in arr:
            if not s.get('id') or not s.get('name'):
                fail('VIDEO_SOURCES の %s に id か name がありません' % key)
        frames[key] = arr
    if not frames:
        fail('VIDEO_SOURCES に枠がありません')
    return frames


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    m = LINE_RE.search(src)
    if not m:
        fail('index.html に VIDEO_LISTS の行が見つかりません')

    frames = read_sources(src)

    updated = {}
    for key in sorted(frames.keys()):
        out_sources = []
        for chan in frames[key]:
            sid, sname = chan['id'], chan['name']
            if not re.match(r'^(UU|PL)[\w-]+$', sid):
                fail('%s の供給源IDが想定外です: %s' % (key, sid))

            got = parse_feed(fetch(feed_url(sid)))
            if not got:
                fail('%s / %s (%s) から動画を取得できませんでした' % (key, sname, sid))

            # 新しい順に並べる（RSSの順に頼らず公開日で決める）
            got.sort(key=lambda e: (e.get('pub', ''), e['id']), reverse=True)

            kept = [it for it in got if embeddable(it['id'])]
            if len(kept) < len(got):
                sys.stdout.write('%s / %s: 見られない動画 %d本を外しました\n'
                                 % (key, sname, len(got) - len(kept)))
            if not kept:
                fail('%s / %s は見られる動画が0本でした' % (key, sname))

            kept = kept[:MAX_ITEMS]
            out_sources.append({'id': sid, 'name': sname,
                                'items': [{'id': e['id'], 't': e['t']} for e in kept]})
            sys.stdout.write('%s / %s: %d本\n' % (key, sname, len(kept)))

        updated[key] = {'sources': out_sources}

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

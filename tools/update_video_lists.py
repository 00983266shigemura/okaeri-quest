# -*- coding: utf-8 -*-
"""ごほうび動画の一覧を、登録したチャンネルの動画から作る（毎朝1回）。

しげの操作は、index.html の VIDEO_SOURCES にチャンネルを足す・やめるだけ。
子どもは「どの チャンネルに する？」の画面で、その枠のチャンネルから選ぶ。

なぜ「ためる」のか（2026-08-28に方針を変えた理由）:
  YouTubeの公式の窓口(RSS)は **新しい15本しか返さない**（実測）。
  毎回それだけを写すと、一覧は永遠に15本のままで、チャンネルに何百本あっても届かない。
  そこで、いちど見た動画は videos_pool.json に **ためて減らさない**。
  毎朝の新着15本を足していくので、日がたつほど一覧が厚くなる。

  ためる方式は8/28の設計では一度捨てた。理由は「しげが再生リストから外した動画を
  落とせない」だった。**いまはチャンネル方式＝しげが動画を1本ずつ出し入れしない**ので、
  その欠点は当てはまらない。チャンネルごと変えたいときは VIDEO_SOURCES を書き替える。

見られなくなった動画の扱い:
  埋め込み禁止・非公開・削除は oEmbed で毎朝みる。**ためた記録からは消さず、印だけ付けて
  一覧から外す**。翌朝また見て、戻っていれば一覧へ戻す。
  （消してしまうと、一時的な失敗で古い動画が永久に失われるため）

安全側の作り:
  - 取得に失敗したら index.html を一切書き換えずに終了する
  - 判定できなかった動画は「見られる」扱いにする（一覧を空にしないことを優先）
  - 変更が無ければ何も書かない

終了コード: 0=正常(変更あり/なしを問わず) / 1=失敗(書き換えなし)
"""
import datetime
import io
import json
import os
import re
import sys
import html
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, 'index.html')
POOL = os.path.join(ROOT, 'videos_pool.json')
CHANNEL_FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id=%s'
PLAYLIST_FEED = 'https://www.youtube.com/feeds/videos.xml?playlist_id=%s'
OEMBED = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json'
UA = 'okaeri-quest-updater'
LINE_RE = re.compile(r'^var VIDEO_LISTS = (.*);$', re.M)
MAX_ITEMS = 60       # 1つのチャンネルから一覧に載せる上限
POOL_MAX = 200       # ためておく上限（これを超えたら公開が古いものから捨てる）


def fail(msg):
    sys.stderr.write('NG: %s\n' % msg)
    sys.exit(1)


def say(msg):
    sys.stdout.write(msg + '\n')


def feed_url(src):
    """UU…＝チャンネルのRSS（2026-08-26まで毎朝動いていた実績あり）。PL…＝再生リストのRSS。"""
    if src.startswith('UU'):
        return CHANNEL_FEED % ('UC' + src[2:])
    return PLAYLIST_FEED % src


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
    """動画側が埋め込みを許しているか。401/403/404=不可。判定できない時は「可」（安全側）。"""
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
    許可表を足していく方式では、新しい題名が来るたびに毎回止まってしまう。
    """
    out = []
    for ch in t:
        o = ord(ch)
        if (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF
                or o in (0xFE0F, 0xFE0E, 0x20E3) or 0x2190 <= o <= 0x21FF
                or 0x2B00 <= o <= 0x2BFF or o == 0x3030 or o == 0x303D
                or 0x2000 <= o <= 0x200D or o == 0x2049 or o == 0x203C):
            continue
        out.append(ch)
    s = ''.join(out)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s or '(だいめい なし)'


def parse_feed(xml):
    items = []
    for entry in re.findall(r'<entry>(.*?)</entry>', xml, re.S):
        mid = re.search(r'<yt:videoId>([\w-]+)</yt:videoId>', entry)
        mti = re.search(r'<title>(.*?)</title>', entry, re.S)
        mpu = re.search(r'<published>([^<]+)</published>', entry)
        if mid and mti:
            items.append({'id': mid.group(1),
                          't': clean_title(html.unescape(mti.group(1))),
                          'pub': mpu.group(1).strip() if mpu else ''})
    return items


def read_sources(src):
    """index.html の VIDEO_SOURCES（しげが決める枠とチャンネルの表）を読む。"""
    m = re.search(r'^var VIDEO_SOURCES = (\{[\s\S]*?\n\});$', src, re.M)
    if not m:
        fail('index.html に VIDEO_SOURCES が見つかりません')
    body = m.group(1)
    body = re.sub(r'/\*[\s\S]*?\*/', '', body)
    body = re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', body)
    body = body.replace("'", '"')
    body = re.sub(r',\s*([}\]])', r'\1', body)
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


def order_key(e):
    """並びの決め手。公開日があればそれ、無ければ初回に取った並び順(seq)を使う。

    公開日ありは 1、無しは 0 を先頭に置くので、RSSで取れた新しい動画が必ず上に来る。
    """
    if e.get('pub'):
        return (1, e['pub'], e['id'])
    return (0, '%08d' % int(e.get('seq', 0)), e['id'])


def load_pool():
    if not os.path.exists(POOL):
        return {}
    try:
        return json.loads(io.open(POOL, encoding='utf-8').read())
    except ValueError as e:
        fail('videos_pool.json を読み取れません: %s' % e)


def main():
    src = io.open(INDEX, encoding='utf-8').read()
    m = LINE_RE.search(src)
    if not m:
        fail('index.html に VIDEO_LISTS の行が見つかりません')

    frames = read_sources(src)
    pool = load_pool()
    today = datetime.date.today().isoformat()

    updated = {}
    for key in sorted(frames.keys()):
        out_sources = []
        for chan in frames[key]:
            sid, sname = chan['id'], chan['name']
            if not re.match(r'^(UU|PL)[\w-]+$', sid):
                fail('%s の供給源IDが想定外です: %s' % (key, sid))

            fresh = parse_feed(fetch(feed_url(sid)))
            if not fresh:
                fail('%s / %s (%s) から動画を取得できませんでした' % (key, sname, sid))

            entries = [e for e in pool.get(sid, []) if e.get('id')]
            known = set(e['id'] for e in entries)
            added = 0
            for it in fresh:
                if it['id'] not in known:
                    entries.append({'id': it['id'], 't': it['t'],
                                    'pub': it.get('pub', ''), 'added': today, 'ok': True})
                    known.add(it['id'])
                    added += 1
            if added:
                say('%s / %s: 新着 %d本' % (key, sname, added))

            # 見られるかを毎朝みる。記録は消さず印だけ付ける（一時的な失敗で失わないため）
            back, gone = 0, 0
            for e in entries:
                now_ok = embeddable(e['id'])
                if now_ok and not e.get('ok', True):
                    back += 1
                if not now_ok and e.get('ok', True):
                    gone += 1
                e['ok'] = now_ok
            if gone:
                say('%s / %s: 見られなくなった %d本を一覧から外した（記録は残す）' % (key, sname, gone))
            if back:
                say('%s / %s: また見られるようになった %d本を戻した' % (key, sname, back))

            # 公開が新しい順。ためる上限を超えたら古いものから捨てる。
            # 初回の蓄えはページから取ったため公開日が無い＝そのときの並び順(seq)で代用する
            # （seqが大きいほど新しい）。公開日のあるものは常にそれを優先する。
            entries.sort(key=order_key, reverse=True)
            if len(entries) > POOL_MAX:
                entries = entries[:POOL_MAX]
            pool[sid] = entries

            usable = [e for e in entries if e.get('ok', True)][:MAX_ITEMS]
            if not usable:
                fail('%s / %s は見られる動画が0本でした' % (key, sname))

            out_sources.append({'id': sid, 'name': sname,
                                'items': [{'id': e['id'], 't': e['t']} for e in usable]})
            say('%s / %s: %d本（ためている数 %d）' % (key, sname, len(usable), len(entries)))

        updated[key] = {'sources': out_sources}

    new_line = 'var VIDEO_LISTS = ' + json.dumps(
        updated, ensure_ascii=False, separators=(",", ":")) + ';'
    pool_txt = json.dumps(pool, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    old_pool = io.open(POOL, encoding='utf-8').read() if os.path.exists(POOL) else ''

    if new_line == m.group(0) and pool_txt == old_pool:
        say('変更なし')
        return

    out = src[:m.start()] + new_line + src[m.end():]
    if LINE_RE.search(out) is None:
        fail('書き換え後の検算に失敗しました')
    io.open(INDEX, 'w', encoding='utf-8').write(out)
    io.open(POOL, 'w', encoding='utf-8').write(pool_txt)
    say('更新しました')


if __name__ == '__main__':
    main()

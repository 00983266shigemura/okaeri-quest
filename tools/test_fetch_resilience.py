# -*- coding: utf-8 -*-
"""毎朝の便（動画・祝日の自動更新）の発火試験（2026-10-14 v34）。

ネットには出ない。RSS・埋め込み判定の窓口を差し替え、本物の index.html と videos_pool.json の
「写し」を作業用フォルダに置いて、本物の関数をそのまま動かす。リポジトリのファイルは触らない。

使い方: python3 tools/test_fetch_resilience.py
終了コード: 0=全件PASS / 1=FAILあり
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import fetch_state  # noqa: E402
import update_video_lists as uvl  # noqa: E402

T = {'pass': 0, 'fail': 0, 'log': []}


def ok(name, cond, extra=''):
    if cond:
        T['pass'] += 1
        T['log'].append('PASS ' + name)
    else:
        T['fail'] += 1
        T['log'].append('FAIL ' + name + ('  [' + str(extra) + ']' if extra != '' else ''))


SOURCES = {}   # sid -> 'ok' / 'fail' / 'empty'
NEWVIDS = {}   # sid -> 新着として返す [(id, title)]
EMBED = {}     # 動画id -> False（見られない）。無ければ見られる
CALLS = {'fetch': 0}


def fake_fetch_once(url):
    CALLS['fetch'] += 1
    m = re.search(r'(?:channel_id=UC|playlist_id=)([\w-]+)', url)
    sid = 'UU' + m.group(1) if 'channel_id' in url else m.group(1)
    mode = SOURCES.get(sid, 'ok')
    if mode == 'fail':
        raise IOError('HTTP Error 404: Not Found')
    if mode == 'flaky':
        SOURCES[sid] = 'ok'
        raise IOError('HTTP Error 404: Not Found')
    if mode == 'empty':
        return '<feed></feed>'
    # 指定が無いチャンネルは「いつもの1本」を返す（RSSが空だと取れなかった扱いになるため）
    items = NEWVIDS.get(sid, [('BASE_' + sid[-4:], 'いつもの どうが')])
    body = ''.join('<entry><yt:videoId>%s</yt:videoId><title>%s</title><published>2026-10-1%dT00:00:00+00:00</published></entry>'
                   % (vid, t, i) for i, (vid, t) in enumerate(items))
    return '<feed>%s</feed>' % body


def fake_embeddable(vid):
    CALLS['embed'] = CALLS.get('embed', 0) + 1
    return EMBED.get(vid, True)


class Work(object):
    """作業用フォルダに写しを置き、モジュールの置き場をそこへ向ける。"""
    def __init__(self):
        self.d = tempfile.mkdtemp(prefix='okq_test_')
        shutil.copy(os.path.join(ROOT, 'index.html'), self.d)
        shutil.copy(os.path.join(ROOT, 'videos_pool.json'), self.d)
        uvl.INDEX = os.path.join(self.d, 'index.html')
        uvl.POOL = os.path.join(self.d, 'videos_pool.json')
        fetch_state.STATE = os.path.join(self.d, 'fetch_state.json')

    def index(self):
        return io.open(uvl.INDEX, encoding='utf-8').read()

    def lists(self):
        line = uvl.LINE_RE.search(self.index()).group(1)
        return json.loads(line)

    def pool(self):
        return json.loads(io.open(uvl.POOL, encoding='utf-8').read())

    def state(self):
        return fetch_state.load(fetch_state.STATE)

    def done(self):
        shutil.rmtree(self.d)


def run_main():
    """本物の main() を動かす。終了コードを返す。"""
    try:
        uvl.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def reset():
    SOURCES.clear()
    NEWVIDS.clear()
    EMBED.clear()
    CALLS['fetch'] = 0
    CALLS['embed'] = 0
    uvl.API_KEY = ''
    API['mode'].clear()
    API['items'].clear()
    API['vstat'].clear()
    API['urls'][:] = []
    API['status_mode'] = 'ok'


REAL_API_GET = uvl.api_get
API = {'mode': {}, 'status_mode': 'ok', 'urls': [], 'items': {}, 'vstat': {}}
FAKE_KEY = 'AIzaFAKEKEY_okq_test_0123456789abcdef'


def fake_api_get(url):
    """公式APIの差し替え。playlistItems＝API['mode'][sid]、videos＝API['status_mode'] と API['vstat'] で答える。"""
    API['urls'].append(url)
    if 'playlistItems' in url:
        sid = re.search(r'playlistId=([\w-]+)', url).group(1)
        mode = API['mode'].get(sid, 'ok')
        if mode in ('key', 'quota', 'other'):
            raise uvl.ApiError(mode, 'API HTTP %s' % {'key': '400 API_KEY_INVALID', 'quota': '403 quotaExceeded',
                                                     'other': '500'}[mode])
        if mode == 'empty':
            return {'items': []}
        vids = API['items'].get(sid, [('API_' + sid[-4:], 'APIの どうが')])
        out = [{'snippet': {'title': t, 'resourceId': {'videoId': v}},
                'contentDetails': {'videoId': v, 'videoPublishedAt': '2026-11-0%dT00:00:00Z' % (i + 1)}}
               for i, (v, t) in enumerate(vids)]
        # 非公開・削除の項目（公開日の欄が無い）も混ぜる＝取り込まれないこと
        out.append({'snippet': {'title': 'Private video', 'resourceId': {'videoId': 'PRIV_' + sid[-4:]}},
                    'contentDetails': {'videoId': 'PRIV_' + sid[-4:]}})
        return {'items': out}
    if 'videos?' in url:
        if API['status_mode'] != 'ok':
            raise uvl.ApiError(API['status_mode'], 'API HTTP 500')
        ids = re.search(r'&id=([\w,-]+)', url).group(1).split(',')
        items = []
        for v in ids:
            st = API['vstat'].get(v, {})
            if st == 'missing':
                continue
            items.append({'id': v, 'status': {'embeddable': st.get('embeddable', True),
                                              'privacyStatus': st.get('privacy', 'public')},
                          'snippet': {'title': st.get('title', 'だいめい ' + v)}})
        return {'items': items}
    raise AssertionError('想定外のURL: ' + url)


uvl.fetch_once = fake_fetch_once
uvl.embeddable = fake_embeddable
uvl.api_get = fake_api_get
uvl.API_KEY = ''      # 既定は鍵なし（今までの試験はRSSだけの動き）
uvl.time.sleep = lambda s: None

real_sources = None


def sids():
    src = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    fr = uvl.read_sources(src)
    out = []
    for k in sorted(fr.keys()):
        for c in fr[k]:
            out.append((k, c['id'], c['name']))
    return out


def items_of(lists, sid):
    for k in lists:
        for s in lists[k]['sources']:
            if s['id'] == sid:
                return [it['id'] for it in s['items']]
    return None


ALL = sids()
S0 = ALL[0][1]     # 失敗させるチャンネル（むしおかだいき）


# ---------- T1 ふだんの日＝全部取れる ----------
reset()
w = Work()
before = w.lists()
for _, sid, _n in ALL:
    NEWVIDS[sid] = [('NEW_' + sid[-4:], 'あたらしい どうが')]
rc = run_main()
ok('T1-1 終了コード0', rc == 0, rc)
ok('T1-2 全チャンネルに新着が入る', all(('NEW_' + sid[-4:]) in (items_of(w.lists(), sid) or []) for _, sid, _n in ALL))
ok('T1-3 帳面は作らない（失敗なし）', not os.path.exists(fetch_state.STATE))
w.done()

# ---------- T2 1つだけ404＝ほかは更新・そのチャンネルは前回のまま ----------
reset()
w = Work()
before_lists = w.lists()
before_pool = w.pool()
SOURCES[S0] = 'fail'
for _, sid, _n in ALL:
    NEWVIDS[sid] = [('NEW_' + sid[-4:], 'あたらしい どうが')]
rc = run_main()
ok('T2-1 1つ失敗しても終了コード0（便を止めない）', rc == 0, rc)
ok('T2-2 失敗したチャンネルの一覧は前回と同じ', items_of(w.lists(), S0) == items_of(before_lists, S0),
   (len(items_of(w.lists(), S0) or []), len(items_of(before_lists, S0) or [])))
ok('T2-3 失敗したチャンネルのためた記録は前回と同じ', w.pool().get(S0) == before_pool.get(S0))
ok('T2-4 ほかのチャンネルは新着が入る',
   all(('NEW_' + sid[-4:]) in (items_of(w.lists(), sid) or []) for _, sid, _n in ALL if sid != S0))
st = w.state()
ok('T2-5 帳面に失敗が残る', S0 in st and st[S0]['fail_since'] == fetch_state.today(), st)
ok('T2-6 帳面にチャンネル名が残る', st.get(S0, {}).get('name') == ALL[0][2], st.get(S0))
ok('T2-7 失敗した1本だけ3回取り直す（ほかは1回）', CALLS['fetch'] == len(ALL) + len(uvl.RETRY_WAITS), CALLS['fetch'])
w.done()

# ---------- T3 全部404＝一覧は1文字も変わらない ----------
reset()
w = Work()
idx_before = w.index()
pool_before = io.open(uvl.POOL, encoding='utf-8').read()
for _, sid, _n in ALL:
    SOURCES[sid] = 'fail'
rc = run_main()
ok('T3-1 全部失敗しても終了コード0', rc == 0, rc)
ok('T3-2 index.html は1文字も変わらない', w.index() == idx_before)
ok('T3-3 videos_pool.json も変わらない', io.open(uvl.POOL, encoding='utf-8').read() == pool_before)
ok('T3-4 帳面に4つとも残る', len(w.state()) == len(ALL), w.state())
w.done()

# ---------- T4 1回目だけ404（すぐ取り直せる）＝失敗にしない ----------
reset()
w = Work()
SOURCES[S0] = 'flaky'
rc = run_main()
ok('T4-1 取り直しで取れたら失敗扱いにしない', rc == 0 and not os.path.exists(fetch_state.STATE))
w.done()

# ---------- T5 見直しで一覧が0本＝前回の記録へ戻す ----------
reset()
w = Work()
before_pool = w.pool()
for e in before_pool[S0]:
    EMBED[e['id']] = False
EMBED['BASE_' + S0[-4:]] = False      # 新しく来た1本も見られない＝0本になる
rc = run_main()
ok('T5-1 終了コード0', rc == 0, rc)
ok('T5-2 0本にはしない（前回の一覧のまま）', items_of(w.lists(), S0) == [e['id'] for e in before_pool[S0] if e.get('ok', True)][:uvl.MAX_ITEMS])
ok('T5-3 ためた記録の印も前回のまま', w.pool()[S0] == before_pool[S0])
ok('T5-4 帳面に失敗が残る', S0 in w.state())
w.done()

# ---------- T6 回復したら帳面から消える／外したチャンネルの記録は消える ----------
reset()
w = Work()
io.open(fetch_state.STATE, 'w', encoding='utf-8').write(json.dumps({
    S0: {'fail_since': '2026-10-01', 'alerted': '2026-10-03', 'why': 'x', 'name': 'n'},
    'UUgone': {'fail_since': '2026-10-01', 'alerted': None, 'why': 'x', 'name': 'もう外した'},
    'holidays': {'fail_since': '2026-10-01', 'alerted': None, 'why': 'x', 'name': '祝日一覧'}}))
rc = run_main()
st = w.state()
ok('T6-1 回復したチャンネルは帳面から消える', S0 not in st, st)
ok('T6-2 外したチャンネルの記録は消える', 'UUgone' not in st, st)
ok('T6-3 祝日の記録は動画の段では消さない', 'holidays' in st, st)
w.done()

# ---------- T7 題名の逃がし（</script> と U+2028） ----------
reset()
w = Work()
NEWVIDS[S0] = [('EVIL1', u'わるい &lt;/script&gt;&lt;script&gt;alert(1) だいめい'), ('EVIL2', u'かいぎょう もじ')]
rc = run_main()
line = uvl.LINE_RE.search(w.index()).group(0)
ok('T7-1 書き出した行に「<」が無い', '<' not in line)
ok('T7-2 書き出した行に U+2028 が無い', u' ' not in line)
ok('T7-3 読み直すと題名は元どおり', any(u'</script>' in it['t'] for s in w.lists()['main']['sources'] for it in s['items']))
w.done()

# ---------- T8 壊れたデータ＝書き換えずに終了コード1 ----------
reset()
w = Work()
src = w.index().replace('var VIDEO_LISTS = ', 'var VIDEO_LISTX = ')
io.open(uvl.INDEX, 'w', encoding='utf-8').write(src)
rc = run_main()
ok('T8-1 一覧の行が無ければ終了コード1', rc == 1, rc)
ok('T8-2 書き換えない', w.index() == src)
w.done()
reset()
w = Work()
io.open(fetch_state.STATE, 'w', encoding='utf-8').write('{こわれた')
idx_before = w.index()
rc = run_main()
ok('T8-3 帳面が壊れていたら終了コード1', rc == 1, rc)
ok('T8-4 そのときも書き換えない', w.index() == idx_before)
w.done()


# ---------- T11 前回の一覧が無いチャンネルの失敗＝その日のうちに知らせる（査読の指摘1） ----------
reset()
w = Work()
src = w.index().replace("{ id: 'UU6cXcs9jEmAx9qPx6ubWWkg', name: 'けいのちゃんねる' }",
                        "{ id: 'UU6cXcs9jEmAx9qPx6ubWWkg', name: 'けいのちゃんねる' },\n    { id: 'UUwrongIDwrongIDwrongID00', name: 'あたらしいチャンネル' }")
io.open(uvl.INDEX, 'w', encoding='utf-8').write(src)
SOURCES['UUwrongIDwrongIDwrongID00'] = 'fail'
rc = run_main()
st = w.state()
ok('T11-1 便は止めない', rc == 0, rc)
ok('T11-2 すぐ知らせる印が付く', st.get('UUwrongIDwrongIDwrongID00', {}).get('urgent') is True, st)
al = fetch_state.due_alerts(st, fetch_state.today())
ok('T11-3 その日のうちに知らせる', [k for k, _ in al] == ['UUwrongIDwrongIDwrongID00'], al)
ok('T11-4 前回の一覧があるチャンネルの失敗は すぐには知らせない',
   fetch_state.due_alerts({'UUx': {'fail_since': fetch_state.today(), 'alerted': None, 'why': 'x'}}, fetch_state.today()) == [])
w.done()

# ---------- T13 名指しで足した1本（pin）は 新着が来ても沈まない（v37・査読の指摘1） ----------
GEORGE, PINNED = 'UUFpGG2WBt673bR-ISOHs4kQ', 'zWXHkTywWks'


def flood(w, drop_pin):
    """新着を 一覧の上限より多く（MAX_ITEMS+10本）・ためる上限を超えるほど 何日ぶんか流しこむ。"""
    if drop_pin:
        p = w.pool()
        for e in p[GEORGE]:
            e.pop('pin', None)
        io.open(uvl.POOL, 'w', encoding='utf-8').write(json.dumps(p, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
    rounds = (uvl.POOL_MAX // (uvl.MAX_ITEMS + 10)) + 1
    for r in range(rounds):
        NEWVIDS[GEORGE] = [('G%02d_%03d' % (r, i), 'あたらしい はなし') for i in range(uvl.MAX_ITEMS + 10)]
        run_main()


reset()
w = Work()
ok('T13-0 前提＝蓄えの指定の1本に pin が付いている',
   any(e['id'] == PINNED and e.get('pin') for e in w.pool().get(GEORGE, [])))
flood(w, False)
ids = items_of(w.lists(), GEORGE) or []
ok('T13-1 新着が上限より多く来ても 一覧に残る', PINNED in ids, len(ids))
ok('T13-2 いつも いちばん上', ids[:1] == [PINNED], ids[:3])
ok('T13-3 ためる上限で捨てられない', any(e['id'] == PINNED for e in w.pool()[GEORGE]), len(w.pool()[GEORGE]))
ok('T13-4 ためる数は上限まで', len(w.pool()[GEORGE]) <= uvl.POOL_MAX, len(w.pool()[GEORGE]))
w.done()
reset()
w = Work()
flood(w, True)
ok('T13-5 負の対照＝pin が無いと 一覧から外れる', PINNED not in (items_of(w.lists(), GEORGE) or []))
ok('T13-6 負の対照＝pin が無いと 蓄えからも消える', not any(e['id'] == PINNED for e in w.pool()[GEORGE]))
w.done()

# ---------- T14 公式API（2026-11-06）＝①API ②RSS ③前回の一覧 ----------
S1 = ALL[1][1]


def api_on():
    uvl.API_KEY = FAKE_KEY


# T14-1 ふだんの日＝APIで取れる・RSSは呼ばない・非公開は取り込まない
reset()
w = Work()
api_on()
for _, sid, _n in ALL:
    SOURCES[sid] = 'fail'          # RSSは落ちている（いまの実情）
rc = run_main()
ok('T14-1 APIで取れたら終了コード0', rc == 0, rc)
ok('T14-2 全チャンネルにAPIの新着が入る',
   all(('API_' + sid[-4:]) in (items_of(w.lists(), sid) or []) for _, sid, _n in ALL))
ok('T14-3 APIで取れた日はRSSを呼ばない', CALLS['fetch'] == 0, CALLS['fetch'])
ok('T14-4 非公開・削除（公開日の欄が無い）は取り込まない',
   not any(e['id'].startswith('PRIV_') for v in w.pool().values() for e in v))
ok('T14-5 帳面は作らない（失敗なし）', not os.path.exists(fetch_state.STATE), w.state() if os.path.exists(fetch_state.STATE) else '')
ok('T14-6 見られるかの照会は1チャンネル1回（50本まとめ）',
   len([u for u in API['urls'] if 'videos?' in u]) == sum(-(-len(w.pool()[sid]) // 50) for _, sid, _n in ALL),
   len([u for u in API['urls'] if 'videos?' in u]))
w.done()

# T14-7 APIが失敗したチャンネルだけRSSで取る・帳面にAPIの失敗が残る（知らせは3日後）
reset()
w = Work()
api_on()
API['mode'][S0] = 'other'
NEWVIDS[S0] = [('RSS_' + S0[-4:], 'RSSの どうが')]
rc = run_main()
st = w.state()
ok('T14-7 APIが失敗してもRSSで取れる', ('RSS_' + S0[-4:]) in (items_of(w.lists(), S0) or []))
ok('T14-8 チャンネルとしては失敗にしない', S0 not in st, st)
ok('T14-9 APIの失敗は帳面に残る', fetch_state.API_STATE_KEY in st and not st[fetch_state.API_STATE_KEY].get('urgent'), st)
ok('T14-10 一時的な失敗はその日には知らせない', fetch_state.due_alerts(dict(st), fetch_state.today()) == [])
w.done()

# T14-11 鍵の誤り×RSS成功＝覆い隠しが起きる組でも、その日のうちに知らせる
reset()
w = Work()
api_on()
for _, sid, _n in ALL:
    API['mode'][sid] = 'key'
rc = run_main()
st = w.state()
ok('T14-11 鍵の誤りでもRSSで取れれば便は続く', rc == 0 and all(sid not in st for _, sid, _n in ALL), st)
ok('T14-12 鍵の誤りは すぐ知らせる印', st.get(fetch_state.API_STATE_KEY, {}).get('urgent') is True, st)
al = fetch_state.due_alerts(dict(st), fetch_state.today())
ok('T14-13 その日のうちに知らせる', [k for k, _ in al] == [fetch_state.API_STATE_KEY], al)
ok('T14-14 理由に「鍵の誤り」と書く', '鍵の誤り' in st.get(fetch_state.API_STATE_KEY, {}).get('why', ''), st)
w.done()

# T14-15 割当の超過＝別の文言・すぐには知らせない
reset()
w = Work()
api_on()
API['mode'][S0] = 'quota'
rc = run_main()
st = w.state()
ok('T14-15 割当の超過は別の文言', '割当の超過' in st.get(fetch_state.API_STATE_KEY, {}).get('why', ''), st)
ok('T14-16 割当の超過はその日には知らせない', not st.get(fetch_state.API_STATE_KEY, {}).get('urgent'), st)
w.done()

# T14-17 帳面の掃除でAPIの記録が消えない（外したチャンネルの記録だけ消す）
reset()
w = Work()
api_on()
API['mode'][S0] = 'key'
io.open(fetch_state.STATE, 'w', encoding='utf-8').write(json.dumps({
    'UUgone': {'fail_since': '2026-10-01', 'alerted': None, 'why': 'x', 'name': 'もう外した'}}))
rc = run_main()
st = w.state()
ok('T14-17 掃除でAPIの記録は消えない', fetch_state.API_STATE_KEY in st and 'UUgone' not in st, st)
# 1チャンネルだけの400/403（非公開化など）＝鍵の誤りとはみない・その日には知らせない（実装査読の指摘1）
ok('T14-38 1チャンネルだけの403は急ぎの印を付けない', not st.get(fetch_state.API_STATE_KEY, {}).get('urgent'), st)
ok('T14-39 1チャンネルだけの403は「一部の再生リスト」と書く', '一部の再生リスト' in st.get(fetch_state.API_STATE_KEY, {}).get('why', ''), st)
w.done()

# T14-40 急ぎの印は翌日の判定で外れる（実装査読の指摘2）
s2 = {}
fetch_state.mark_fail(s2, 'k', 'x', day='2026-11-07', urgent=True)
fetch_state.mark_fail(s2, 'k', 'y', day='2026-11-08', urgent=False)
ok('T14-40 直ったあとの非急ぎの失敗で印が外れる', 'urgent' not in s2['k'] and s2['k']['fail_since'] == '2026-11-07', s2)

# T14-18 APIが0本の答え＝失敗とみなしRSSへ
reset()
w = Work()
api_on()
API['mode'][S0] = 'empty'
NEWVIDS[S0] = [('RSS_' + S0[-4:], 'RSSの どうが')]
rc = run_main()
ok('T14-18 APIが0本ならRSSへ回る', ('RSS_' + S0[-4:]) in (items_of(w.lists(), S0) or []) and CALLS['fetch'] == 1, CALLS['fetch'])
w.done()

# T14-19 APIもRSSも失敗＝前回の一覧のまま
reset()
w = Work()
api_on()
before_lists = w.lists()
API['mode'][S0] = 'other'
SOURCES[S0] = 'fail'
rc = run_main()
ok('T14-19 両方失敗なら前回の一覧のまま', rc == 0 and items_of(w.lists(), S0) == items_of(before_lists, S0))
ok('T14-20 チャンネルの失敗として帳面に残る', 'APIもRSSも' in w.state().get(S0, {}).get('why', ''), w.state())
w.done()

# T14-21 見られるか＝埋め込み禁止・非公開・答えに無い（削除）の3つとも「見られない」・題名は取り直す
reset()
w = Work()
api_on()
pool0 = [e['id'] for e in w.pool()[S1] if e.get('ok', True)]
API['vstat'][pool0[0]] = {'embeddable': False}
API['vstat'][pool0[1]] = {'privacy': 'private'}
API['vstat'][pool0[2]] = 'missing'
API['vstat'][pool0[3]] = {'title': 'あたらしい だいめい'}
rc = run_main()
ids = items_of(w.lists(), S1) or []
ok('T14-21 埋め込み禁止は外す', pool0[0] not in ids)
ok('T14-22 非公開は外す', pool0[1] not in ids)
ok('T14-23 答えに無い（削除）は外す', pool0[2] not in ids)
ok('T14-24 ほかは残る', pool0[3] in ids and pool0[4] in ids)
ok('T14-25 外した動画も記録は残す（印だけ）', all(any(e['id'] == v and e.get('ok') is False for e in w.pool()[S1]) for v in pool0[:3]))
ok('T14-26 題名を取り直す', any(e['id'] == pool0[3] and e['t'] == 'あたらしい だいめい' for e in w.pool()[S1]))
ok('T14-27 照会を使った日はoEmbedを呼ばない', CALLS['embed'] == 0, CALLS['embed'])
w.done()

# T14-28 見られるかの照会が失敗＝oEmbedへ戻る・帳面に残る
reset()
w = Work()
api_on()
API['status_mode'] = 'other'
pool0 = [e['id'] for e in w.pool()[S1] if e.get('ok', True)]
EMBED[pool0[0]] = False
rc = run_main()
ok('T14-28 照会が失敗したらoEmbedで調べる', pool0[0] not in (items_of(w.lists(), S1) or []))
ok('T14-29 照会の失敗も帳面に残る', fetch_state.API_STATE_KEY in w.state(), w.state())
w.done()

# T14-30 鍵が無い日は今までどおり（APIを呼ばない・APIの記録を持たない）
reset()
w = Work()
io.open(fetch_state.STATE, 'w', encoding='utf-8').write(json.dumps({
    fetch_state.API_STATE_KEY: {'fail_since': '2026-11-01', 'alerted': None, 'why': 'x', 'name': 'YouTube公式API'}}))
rc = run_main()
ok('T14-30 鍵が無ければAPIを呼ばない', API['urls'] == [], API['urls'][:2])
ok('T14-31 鍵が無ければAPIの記録は消える', not os.path.exists(fetch_state.STATE) or fetch_state.API_STATE_KEY not in w.state())
w.done()

# T14-32 鍵が漏れない＝本物の api_get を、通信だけ差し替えて動かす
class _Resp(object):
    status = 200

    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


SEEN = []


def fake_urlopen(req, timeout=None):
    SEEN.append(req)
    if 'bad' in req.full_url:
        import email.message
        raise uvl.urllib.error.HTTPError(req.full_url, 400, 'Bad Request', email.message.Message(),
                                         io.BytesIO(json.dumps({'error': {'code': 400, 'errors': [{'reason': 'badRequest'}],
                                                                          'details': [{'reason': 'API_KEY_INVALID'}]}}).encode('utf-8')))
    return _Resp(json.dumps({'items': []}).encode('utf-8'))


real_urlopen = uvl.urllib.request.urlopen
uvl.urllib.request.urlopen = fake_urlopen
uvl.API_KEY = FAKE_KEY
out = io.StringIO()
_stdout = sys.stdout
sys.stdout = out
try:
    REAL_API_GET(uvl.API_ITEMS % 'UUok')
    err = None
    try:
        REAL_API_GET(uvl.API_ITEMS % 'UUbad')
    except uvl.ApiError as e:
        err = e
finally:
    sys.stdout = _stdout
    uvl.urllib.request.urlopen = real_urlopen
    uvl.API_KEY = ''
ok('T14-32 鍵はヘッダで送る', all(r.get_header('X-goog-api-key') == FAKE_KEY for r in SEEN) and len(SEEN) == 2, len(SEEN))
ok('T14-33 URLに鍵が載らない', all(FAKE_KEY not in r.full_url for r in SEEN))
ok('T14-34 400の鍵の誤りを key と見分ける', err is not None and err.kind == 'key' and 'API_KEY_INVALID' in err.why, err and err.why)
ok('T14-35 エラー文と出力に鍵が出ない', err is not None and FAKE_KEY not in err.why and FAKE_KEY not in out.getvalue())

# T14-36 便全体の出力に鍵が出ない（鍵の誤りの日を通しで）
reset()
w = Work()
api_on()
for _, sid, _n in ALL:
    API['mode'][sid] = 'key'
out = io.StringIO()
sys.stdout = out
try:
    run_main()
finally:
    sys.stdout = _stdout
st_txt = io.open(fetch_state.STATE, encoding='utf-8').read() if os.path.exists(fetch_state.STATE) else ''
ok('T14-36 便の出力と帳面に鍵の文字列が0回', FAKE_KEY not in out.getvalue() and FAKE_KEY not in st_txt)
ok('T14-36b 前提＝鍵の誤りの日は帳面がある（空の帳面で上を素通りさせない）', fetch_state.API_STATE_KEY in st_txt)
w.done()

# T14-37 知らせの文（公式APIの行は「使えていません」）
d = tempfile.mkdtemp(prefix='okq_api_')
io.open(os.path.join(d, 'fetch_state.json'), 'w', encoding='utf-8').write(json.dumps({
    fetch_state.API_STATE_KEY: {'fail_since': '2026-11-07', 'alerted': None, 'why': '鍵の誤りかAPIが有効でない（…）',
                                'name': 'YouTube公式API', 'urgent': True}}))
alerts = os.path.join(d, 'alerts.txt')
r = subprocess.run([sys.executable, os.path.join(HERE, 'fetch_health.py'), 'record', '--holidays', 'success',
                    '--alerts', alerts, '--state', os.path.join(d, 'fetch_state.json'), '--day', '2026-11-07'],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
txt = io.open(alerts, encoding='utf-8').read()
ok('T14-37 公式APIの知らせは その日に・「使えていません」と書く', r.returncode == 0 and '使えていません' in txt and 'YOUTUBE_API_KEY' in txt, txt)
shutil.rmtree(d)


# ---------- T12 日付は日本時間 ----------
import datetime as _dt  # noqa: E402
jst_now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=9))).date().isoformat()
ok('T12-1 fetch_state.today() は日本時間の日付', fetch_state.today() == jst_now, (fetch_state.today(), jst_now))


# ---------- T9 知らせるか（日付で数える・同じ日の再実行で増えない・7日おき） ----------
def health(day, hol, d):
    alerts = os.path.join(d, 'alerts.txt')
    cmd = [sys.executable, os.path.join(HERE, 'fetch_health.py'), 'record', '--holidays', hol,
           '--alerts', alerts, '--state', os.path.join(d, 'fetch_state.json'), '--day', day]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = io.open(alerts, encoding='utf-8').read() if os.path.exists(alerts) else ''
    return r.returncode, [l for l in txt.splitlines() if l.strip()]


def final(videos, d):
    cmd = [sys.executable, os.path.join(HERE, 'fetch_health.py'), 'final', '--videos', videos,
           '--alerts', os.path.join(d, 'alerts.txt')]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode('utf-8')


d = tempfile.mkdtemp(prefix='okq_health_')
seq = [('2026-10-12', 'failure', 0), ('2026-10-13', 'failure', 0), ('2026-10-14', 'failure', 1),
       ('2026-10-14', 'failure', 0), ('2026-10-15', 'failure', 0), ('2026-10-20', 'failure', 0),
       ('2026-10-21', 'failure', 1), ('2026-10-22', 'success', 0), ('2026-10-23', 'failure', 0),
       ('2026-10-24', 'failure', 0), ('2026-10-25', 'failure', 1)]
names = ['1日目', '2日目', '3日目＝知らせる', '3日目の再実行＝知らせない', '4日目', '9日目',
         '10日目＝7日おきに もういちど', '回復', 'また失敗1日目', '2日目', '3日目＝新しい失敗として知らせる']
for (day, hol, want), nm in zip(seq, names):
    rc, al = health(day, hol, d)
    ok('T9 %s %s' % (day, nm), rc == 0 and len(al) == want, (rc, al))
    if want:
        ok('T9 %s 知らせの文に名前が入る' % day, '祝日一覧' in al[0], al)
    frc, out = final('success', d)
    ok('T9 %s 最後の段の終了コード' % day, frc == (1 if want else 0), (frc, out))
st = json.loads(io.open(os.path.join(d, 'fetch_state.json'), encoding='utf-8').read())
ok('T9-y 帳面に知らせた日が残る', st['holidays']['alerted'] == '2026-10-25', st)
rc, al = health('2026-10-26', 'skipped', d)
ok('T9-z 祝日の段が走らなかった日は数えない（記録はそのまま）',
   json.loads(io.open(os.path.join(d, 'fetch_state.json'), encoding='utf-8').read())['holidays']['fail_since'] == '2026-10-23')
frc, out = final('failure', d)
ok('T10-1 動画の段が壊れて止まった日は最後の段で失敗させる', frc == 1 and '壊れて' in out, out)
shutil.rmtree(d)

print('RESULT total=%d PASS=%d FAIL=%d' % (T['pass'] + T['fail'], T['pass'], T['fail']))
for l in T['log']:
    if not l.startswith('PASS'):
        print(l)
if '-v' in sys.argv:
    print('\n'.join(T['log']))
sys.exit(0 if T['fail'] == 0 else 1)

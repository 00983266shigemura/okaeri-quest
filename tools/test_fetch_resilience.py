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


uvl.fetch_once = fake_fetch_once
uvl.embeddable = fake_embeddable
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
ok('T2-7 取り直しは3回', CALLS['fetch'] >= 3)
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

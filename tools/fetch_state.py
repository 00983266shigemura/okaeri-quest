# -*- coding: utf-8 -*-
"""毎朝の便の「取得の失敗が何日つづいているか」を覚えておく小さな帳面（fetch_state.json）。

なぜ要るのか（2026-10-14）:
  YouTubeのRSSは、ときどき1つのチャンネルだけ 404 を返す（10/6・10/12〜14 に実測）。
  v33までは1つ失敗すると便ぜんぶが止まり、祝日の更新まで止まり、毎回 失敗メールが来ていた。
  v34からは、失敗したチャンネルは前回の一覧のまま続ける。
  ただし、それだけだと「ずっと取れていない」ことに気づけない。そこで失敗の続き具合だけを覚えておき、
  長く続いたときだけ知らせる。

覚えるのは「失敗している物」だけ（成功したら消す）:
  { "<チャンネルIDか holidays>": {"fail_since": "YYYY-MM-DD", "alerted": "YYYY-MM-DD" か null, "why": "..."} }
  成功している日は何も書かない＝毎朝のコミットは増えない。

日付で数える理由:
  同じ日に手で再実行しても数が増えない（回数で数えると二重に数える）。
"""
import datetime
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, 'fetch_state.json')

ALERT_AFTER_DAYS = 2    # 失敗した最初の日から2日後（＝3日つづけて失敗）に知らせる
REMIND_EVERY_DAYS = 7   # 直らないあいだは7日おきに もういちど知らせる
HOLIDAYS_KEY = 'holidays'


JST = datetime.timezone(datetime.timedelta(hours=9))
BROKEN_HINT = 'fetch_state.json を消して もういちど実行すれば直ります（消えるのは失敗の記録だけ）'


def today():
    """日本時間の日付。GitHubの便はUTCで動くため、そのままだと1日ずれる。"""
    return datetime.datetime.now(JST).date().isoformat()


def load(path=None):
    """読めなければ例外（壊れた帳面で上書きしない＝呼び出し側が失敗として扱う）。
    path を省いたときは、その時点の STATE を使う（試験で置き場を差し替えられるように）。"""
    path = path or STATE
    if not os.path.exists(path):
        return {}
    data = json.loads(io.open(path, encoding='utf-8').read())
    if not isinstance(data, dict):
        raise ValueError('fetch_state.json の形が想定外です')
    return data


def save(state, path=None):
    path = path or STATE
    txt =json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    old = io.open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old == txt:
        return False
    if not state and old is None:
        return False          # 失敗が1つも無く、帳面もまだ無い＝作らない
    io.open(path, 'w', encoding='utf-8').write(txt)
    return True


def mark_ok(state, key):
    state.pop(key, None)


def mark_fail(state, key, why, name=None, day=None, urgent=False):
    """name＝知らせに出す名前（チャンネル名など）。IDだけでは何のことか分からないため。
    urgent＝前回の一覧が無く、代わりに出せる物が無い失敗（新しく足したチャンネルのID違いなど）。
    3日待たずに その日のうちに知らせる。"""
    day = day or today()
    cur = state.get(key)
    if cur and cur.get('fail_since'):
        cur['why'] = why
        if name:
            cur['name'] = name
        if urgent:
            cur['urgent'] = True
        return
    state[key] = {'fail_since': day, 'alerted': None, 'why': why, 'name': name or key}
    if urgent:
        state[key]['urgent'] = True


def days_between(a, b):
    da = datetime.date.fromisoformat(a)
    db = datetime.date.fromisoformat(b)
    return (db - da).days


def due_alerts(state, day=None):
    """いま知らせるべき物の一覧を返し、知らせた日を帳面に書く。

    知らせる＝失敗が ALERT_AFTER_DAYS 日以上つづき、まだ知らせていないか、
    前に知らせてから REMIND_EVERY_DAYS 日以上たった物。
    """
    day = day or today()
    out = []
    for key in sorted(state.keys()):
        e = state[key]
        since = e.get('fail_since')
        if not since:
            continue
        if days_between(since, day) < ALERT_AFTER_DAYS and not e.get('urgent'):
            continue
        last = e.get('alerted')
        if last and last >= since and days_between(last, day) < REMIND_EVERY_DAYS:
            continue
        e['alerted'] = day
        out.append((key, e))
    return out

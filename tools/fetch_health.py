# -*- coding: utf-8 -*-
"""毎朝の便の最後に、取得の失敗を「知らせるべきか」を決める（2026-10-14 v34）。

2つの段で使う（.github/workflows/update-videos.yml）:
  record --holidays <outcome> --alerts <ファイル>
      祝日の取得の結果を帳面（fetch_state.json）へ書き、
      いま知らせるべき失敗（3日つづいた・前の知らせから7日たった）をファイルへ書き出す。
      知らせた日も帳面へ書く＝このあとのコミットで残り、同じ失敗を毎朝は知らせない。
  final --videos <outcome> --alerts <ファイル>
      コミットのあとに走る。知らせる物があるか、動画の段が壊れて止まっていたら、
      この段を失敗させる＝GitHubの「Run failed」メールが届く（届くことは10/6・10/12〜14で実測済みの経路）。

知らせ方を「便を失敗させる」にした理由:
  新しい通知の仕組みを足さず、いま実際に届いているメールの経路をそのまま使うため。
  一時的な失敗（1〜2日）ではメールを出さない。長くつづいたときは7日おきに思い出させる。

終了コード: record=0（帳面が壊れていたら1） / final=0（知らせなし）か1（知らせあり・壊れあり）
"""
import argparse
import io
import os
import sys

import fetch_state


def cmd_record(a):
    try:
        state = fetch_state.load(a.state)
    except ValueError as e:
        print('::error::fetch_state.json を読み取れません: %s' % e)
        return 1
    if a.holidays == 'success':
        fetch_state.mark_ok(state, fetch_state.HOLIDAYS_KEY)
    elif a.holidays in ('failure', ''):
        fetch_state.mark_fail(state, fetch_state.HOLIDAYS_KEY, '祝日一覧が取れない（%s）' % (a.holidays or '結果なし'),
                              name='祝日一覧', day=a.day)
    # skipped・cancelled は数えない（祝日の段が走っていない日は、取れたとも取れないとも言えない）

    for key in sorted(state.keys()):
        e = state[key]
        print('::warning::取れていない: %s（%s から・%s）' % (e.get('name', key), e.get('fail_since'), e.get('why', '')))

    alerts = fetch_state.due_alerts(state, a.day)
    fetch_state.save(state, a.state)
    lines = []
    for key, e in alerts:
        lines.append('%s が %s から取れていません（%s）。前回の一覧のまま使っています。'
                     % (e.get('name', key), e.get('fail_since'), e.get('why', '')))
    io.open(a.alerts, 'w', encoding='utf-8').write(''.join(l + '\n' for l in lines))
    print('知らせる物: %d件' % len(lines))
    return 0


def cmd_final(a):
    lines = []
    if os.path.exists(a.alerts):
        lines = [l for l in io.open(a.alerts, encoding='utf-8').read().splitlines() if l.strip()]
    bad = False
    for l in lines:
        print('::error::' + l)
        bad = True
    if a.videos == 'failure':
        print('::error::動画一覧の段が壊れて止まりました（データの形がおかしい等）。index.html の動画一覧は書き換えていません。')
        bad = True
    if not bad:
        print('知らせる物はありません')
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')
    r = sub.add_parser('record')
    r.add_argument('--holidays', default='')
    r.add_argument('--alerts', required=True)
    r.add_argument('--state', default=None)
    r.add_argument('--day', default=None)
    f = sub.add_parser('final')
    f.add_argument('--videos', default='')
    f.add_argument('--alerts', required=True)
    a = p.parse_args()
    if a.cmd == 'record':
        return cmd_record(a)
    if a.cmd == 'final':
        return cmd_final(a)
    p.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())

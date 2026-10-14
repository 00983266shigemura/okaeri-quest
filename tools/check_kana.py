# -*- coding: utf-8 -*-
"""子どもの画面に漢字が混ざっていないかを確かめる。

なぜこの道具があるか（2026-10-15 しげ指示・原文のまま）:
  「混入している漢字をひらがな、カタカナに直して」

考え方:
  index.html のうち、コメントを除いた文字（画面の文言・JSの文字列）に漢字があれば落とす。
  漢字を使ってよいのは、目印で囲んだ「おうちのひと用」の範囲だけ。
    HTML: <!-- KANA-CHECK-OFF … -->  …  <!-- KANA-CHECK-ON … -->
    JS:   /* KANA-CHECK-OFF … */      …  /* KANA-CHECK-ON … */
  目印の範囲に子どもの画面（id="scr…"）が入っていたら、それも落とす
  （範囲を広げて検査を黙らせる抜け道を塞ぐ）。
  動画の題名（var VIDEO_LISTS の1行）は YouTube の題名そのもので毎朝の便が書き換えるため、
  この検査の対象外（別の扱い）。

使い方:
  python3 tools/check_kana.py              本物の index.html を検査
  python3 tools/check_kana.py --selftest   負の対照つきの自己試験

終了コード: 0=PASS / 1=FAIL
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), 'index.html')
KANJI = re.compile(u'[㐀-䶿一-鿿豈-﫿々〆]')


def strip_comments(line, in_block):
    """1行からコメントを除いた文字列と、行末でブロックコメントの中にいるかを返す。"""
    out = []
    j = 0
    n = len(line)
    while j < n:
        if in_block:
            k1 = line.find('*/', j)
            k2 = line.find('-->', j)
            ends = [x for x in (k1, k2) if x != -1]
            if not ends:
                return u''.join(out), True
            e = min(ends)
            j = e + (2 if e == k1 else 3)
            in_block = False
            continue
        if line.startswith('/*', j) or line.startswith('<!--', j):
            in_block = True
            j += 2
            continue
        if line.startswith('//', j) and (j == 0 or line[j - 1] not in u':"\''):
            break
        out.append(line[j])
        j += 1
    return u''.join(out), in_block


def check(text):
    """問題の一覧を返す（空なら合格）。"""
    problems = []
    allowed = False
    in_block = False
    offs = 0
    for i, ln in enumerate(text.split('\n'), 1):
        if 'KANA-CHECK-OFF' in ln:
            if allowed:
                problems.append(u'%d行: KANA-CHECK-OFF が二重' % i)
            allowed = True
            offs += 1
            continue
        if 'KANA-CHECK-ON' in ln:
            if not allowed:
                problems.append(u'%d行: KANA-CHECK-ON に対応する OFF が無い' % i)
            allowed = False
            continue
        body, in_block = strip_comments(ln, in_block)
        if allowed:
            if re.search(r'id="scr', body):
                problems.append(u'%d行: 漢字を許す範囲に子どもの画面がある: %s' % (i, body.strip()[:80]))
            continue
        if body.lstrip().startswith('var VIDEO_LISTS'):
            continue
        ks = KANJI.findall(body)
        if ks:
            problems.append(u'%d行: 漢字 [%s] %s' % (i, u''.join(sorted(set(ks))), body.strip()[:100]))
    if allowed:
        problems.append(u'KANA-CHECK-OFF が閉じていない')
    if offs == 0:
        problems.append(u'目印が1つも無い（作りが変わった）')
    return problems


def selftest():
    good = io.open(INDEX, encoding='utf-8').read()
    cases = [
        (u'正常系＝本物の index.html', good, True),
        (u'負の対照＝子どもの画面のボタンに漢字',
         good.replace(u'>ふつうの ひ<', u'>ふつうの日<', 1), False),
        (u'負の対照＝JSの文字列に漢字',
         good.replace(u"'すみ '", u"'済 '", 1), False),
        (u'負の対照＝子どもの画面を許す範囲へ入れる',
         good.replace(u'<div class="screen" id="scrWelcome">',
                      u'<!-- KANA-CHECK-OFF -->\n<div class="screen" id="scrWelcome">', 1), False),
    ]
    ok = ng = 0
    for name, text, want_pass in cases:
        if text == good and not want_pass:
            print(u'FAIL %s（差し替えが当たらない＝試験が空振り）' % name)
            ng += 1
            continue
        passed = not check(text)
        if passed == want_pass:
            print(u'PASS ' + name)
            ok += 1
        else:
            print(u'FAIL ' + name)
            ng += 1
    print('selftest PASS=%d FAIL=%d' % (ok, ng))
    return 0 if ng == 0 else 1


def main():
    if '--selftest' in sys.argv:
        return selftest()
    problems = check(io.open(INDEX, encoding='utf-8').read())
    for p in problems:
        print(u'NG ' + p)
    if problems:
        print('check_kana FAIL（%d件）' % len(problems))
        return 1
    print('check_kana PASS（子どもの画面に漢字なし）')
    return 0


if __name__ == '__main__':
    sys.exit(main())

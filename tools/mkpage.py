# -*- coding: utf-8 -*-
"""試験用・目視用の複製ページを作る唯一の道具。

なぜこの道具があるか（2026-09-16 しげ指示・原文のまま）:
  「裏側でアプリをテストするときに効果音が鳴らないようにして。
    これに限らず、すべてのテストで同じようにして。」

考え方:
  「鳴った音をあとで止める」のではなく、**鳴らないページしか作れない**ようにする。
  複製を作る道が この1本しか無く、その道に無音化が焼き込んであるので、忘れようがない。

無音化のしくみ（3段・すべて index.html 本体には触らない）:
  1. アプリの音はすべて ensureAudio() を通る（tone/noiseBurst/sparkle が入口で呼ぶ）。
     ここを塞げば、いまある音も、あとで足す音も、自動的に無音になる。
  2. 音の入口そのもの（AudioContext）を「使うと失敗する」形へ差し替える。
     ensureAudio を通らない書き方が現れたら、黙って鳴るのではなく目に見えて失敗する。
  3. 動画の枠（YouTube の iframe）を作らない＝別ドメインから出る音も止める。

出力の検査:
  作ったページに無音化の目印が入っているかを必ず確かめ、無ければ書かずに失敗する
  （--selftest で、目印を抜いた版が正しく落ちることまで確かめられる）。

使い方:
  python3 tools/mkpage.py --out _preview.html
  python3 tools/mkpage.py --out _test.html --inject /path/to/tests.js
  python3 tools/mkpage.py --out _preview_v30.html --from 1a228e9
  python3 tools/mkpage.py --selftest

終了コード: 0=成功 / 1=失敗
"""
import argparse
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
INDEX = os.path.join(REPO, 'index.html')
ANCHOR = u"\n})();\n</script>"
MARK = u'/* OKAERI-TESTPAGE-SILENCE v1 */'

SILENCE = MARK + u"""
/* ===== 無音化（試験用・目視用の複製だけ。公開物には入らない）=====
   しげ指示 2026-09-16「裏側でアプリをテストするときに効果音が鳴らないようにして。
   これに限らず、すべてのテストで同じようにして。」
   正本の考え方＝鳴った音を止めるのではなく、鳴らないページしか作れないようにする。 */
window.__audioAsked = 0;    /* 音を出そうとした回数（＝無音化が効いている証拠になる） */
window.__audioMade = 0;     /* 音の入口を実際に作った回数。0でなければ無音化の抜け道がある */
AC = null;
actx = null;
ensureAudio = function(){ window.__audioAsked++; return null; };
(function(){
  function blocked(){
    window.__audioMade++;
    throw new Error('この複製では音を出せません（tools/mkpage.py の無音化）');
  }
  try { window.AudioContext = blocked; } catch(e) {}
  try { window.webkitAudioContext = blocked; } catch(e) {}
})();
/* 動画の枠は作らない＝別ドメイン（YouTube）から出る音も止める */
mountPlayer = function(){};
"""


def read_index(from_commit):
    if from_commit:
        out = subprocess.check_output(
            ['/usr/bin/git', '-C', REPO, 'show', from_commit + ':index.html'])
        return out.decode('utf-8')
    return io.open(INDEX, encoding='utf-8').read()


def build(from_commit, inject_path, silence=True):
    """複製の中身を作って返す。silence=False は自己試験の負の対照でだけ使う。"""
    s = read_index(from_commit)
    if s.count(ANCHOR) != 1:
        raise RuntimeError('差し込み口が1つではありません（index.html の作りが変わった）')
    extra = u''
    if inject_path:
        extra = io.open(inject_path, encoding='utf-8').read()
    head = SILENCE if silence else u'/* 無音化なし（自己試験の負の対照） */'
    return s.replace(ANCHOR, u"\n\n" + head + u"\n\n" + extra + ANCHOR)


def verify(text):
    """無音化が入っているか。入っていなければ理由を返す（Noneなら合格）。"""
    if MARK not in text:
        return '無音化の目印が入っていません'
    for need in [u'ensureAudio = function', u'window.AudioContext = blocked',
                 u'mountPlayer = function(){}']:
        if need not in text:
            return u'無音化の一部が欠けています: ' + need
    return None


def selftest():
    ok = 0
    ng = 0

    def check(name, cond):
        nonlocal_ok = None  # noqa: F841  (py2互換のため使わない)
        if cond:
            print('PASS ' + name)
        else:
            print('FAIL ' + name)
        return cond

    good = build(None, None, silence=True)
    if check('正常系＝無音化が入る', verify(good) is None):
        ok += 1
    else:
        ng += 1
    bad = build(None, None, silence=False)
    if check('負の対照＝無音化を抜くと検査が落ちる', verify(bad) is not None):
        ok += 1
    else:
        ng += 1
    if check('公開物 index.html には無音化が入っていない',
             MARK not in io.open(INDEX, encoding='utf-8').read()):
        ok += 1
    else:
        ng += 1
    print('selftest PASS=%d FAIL=%d' % (ok, ng))
    return 0 if ng == 0 else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='')
    p.add_argument('--inject', default='')
    p.add_argument('--from', dest='from_commit', default='')
    p.add_argument('--selftest', action='store_true')
    a = p.parse_args()

    if a.selftest:
        return selftest()
    if not a.out:
        print('NG: --out が要ります')
        return 1

    text = build(a.from_commit, a.inject or None, silence=True)
    why = verify(text)
    if why:
        print('NG: ' + why + '（書き込みません）')
        return 1
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    io.open(out, 'w', encoding='utf-8').write(text)
    print('OK: %s（%d字・無音化あり）' % (out, len(text)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""むしずかんの絵の下ごしらえ（ChatGPTが描いた1024pxのPNG → アプリが使う小さなPNG）。

やること:
  1. 透明な余白を切り落とす（虫の実体だけにする）
  2. 正方形にそろえて、まわりに一定の余白を足す
  3. 表示用の大きさ（240px）へ縮める
  4. 同じ形から「真っ黒なシルエット版」を作る（形はアルファ＝不透明さだけから作る）
  5. 色数を減らして軽くする（2012年iPadの読み込みを軽くするため）

出力: <リポジトリ>/img/zukan/<id>.png（カラー）と <id>_s.png（シルエット）
確認用に <リポジトリ>/tools/_zukan_preview_color.png と _sil.png も作る（git管理外）。

使い方:
    python3 tools/make_zukan_assets.py [元絵のフォルダ]
    （フォルダを省いたら ~/Downloads/むしずかん を見る）

元絵のファイル名は下の IDS の左側に合わせる。
2冊目を作るときは IDS に行を足すだけでよい。
"""
import os
import sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_DIR = os.path.join(REPO, 'img', 'zukan')
DEFAULT_SRC = os.path.join(os.path.expanduser('~'), 'Downloads', u'むしずかん')

SIZE = 240            # 表示用の1辺（px）
PAD = 8               # まわりの余白（px）
SIL_RGB = (26, 26, 26)  # シルエットの色。無彩色＝赤緑の見え方に左右されない
COLORS_FULL = 96      # カラー版の色数
COLORS_SIL = 32       # シルエット版の色数（輪郭のなめらかさ用）

# 元絵のファイル名 -> アプリでの id（index.html の ZUKAN と一致させる）
IDS = [
    ('01_kabutomushi.png', 'kabuto'),
    ('02_nokogiri_kuwagata.png', 'nokogiri'),
    ('03_miyama_kuwagata.png', 'miyama'),
    ('04_ookuwagata.png', 'ookuwa'),
    ('05_kokuwagata.png', 'kokuwa'),
    ('06_hirata_kuwagata.png', 'hirata'),
    ('07_nijiiro_kuwagata.png', 'nijiiro'),
    ('08_hercules_ookabuto.png', 'hercules'),
    ('09_caucasus_ookabuto.png', 'caucasus'),
    ('10_atlas_ookabuto.png', 'atlas'),
    ('11_elephas_zoukabuto.png', 'elephas'),
    ('12_giraffa_nokogiri_kuwagata.png', 'giraffa'),
]


def prepare(path):
    """透明な余白を切り、正方形にそろえ、SIZE へ縮めた RGBA を返す。"""
    im = Image.open(path).convert('RGBA')
    box = im.getchannel('A').getbbox()
    if box is None:
        raise ValueError('中身が空（全部が透明）: ' + path)
    im = im.crop(box)
    w, h = im.size
    side = max(w, h)
    square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - w) // 2, (side - h) // 2))
    inner = SIZE - PAD * 2
    square = square.resize((inner, inner), Image.LANCZOS)
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(square, (PAD, PAD))
    return out


def silhouette(rgba):
    """同じ形を1色で塗りつぶした版。形はアルファだけから作るので、絵の中身に依らない。"""
    sil = Image.new('RGBA', rgba.size, SIL_RGB + (0,))
    sil.putalpha(rgba.getchannel('A'))
    return sil


def save_small(rgba, path, colors):
    """色数を減らして保存する（見た目はほぼ変わらず、大きさは1/5以下になる）。"""
    rgba.quantize(colors=colors, method=Image.FASTOCTREE).save(path, optimize=True)


def sheet(images, path):
    """確認用に4列で1枚に並べる（白い紙の上に置いた見え方）。"""
    rows = (len(images) + 3) // 4
    out = Image.new('RGB', (SIZE * 4, SIZE * max(rows, 1)), (255, 255, 255))
    for i, im in enumerate(images):
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        out.paste(bg.convert('RGB'), ((i % 4) * SIZE, (i // 4) * SIZE))
    out.save(path)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.isdir(src):
        print('元絵のフォルダが見つからない: ' + src)
        return 1
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    missing = [f for f, _ in IDS if not os.path.isfile(os.path.join(src, f))]
    if missing:
        print('元絵が足りない: ' + ', '.join(missing))
        return 1

    colors, sils, total = [], [], 0
    for fname, bid in IDS:
        rgba = prepare(os.path.join(src, fname))
        sil = silhouette(rgba)
        pc = os.path.join(OUT_DIR, bid + '.png')
        ps = os.path.join(OUT_DIR, bid + '_s.png')
        save_small(rgba, pc, COLORS_FULL)
        save_small(sil, ps, COLORS_SIL)
        colors.append(rgba)
        sils.append(sil)
        n = os.path.getsize(pc) + os.path.getsize(ps)
        total += n
        print('%-10s %6d B（カラー＋シルエット）' % (bid, n))

    sheet(colors, os.path.join(HERE, '_zukan_preview_color.png'))
    sheet(sils, os.path.join(HERE, '_zukan_preview_sil.png'))
    print('合計 %d B / %d 種 -> %s' % (total, len(IDS), OUT_DIR))
    return 0


sys.exit(main())

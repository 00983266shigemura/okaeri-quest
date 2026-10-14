/* ============================================================
   v31 発火試験（そら 対 パパ の きょうそう）
   本物の index.html の中（IIFEの内側）へ差し込んで、本物の関数をそのまま呼ぶ。
   再実装のコピーではない＝実装が変われば試験も落ちる。
   読み取りはすべて「無ければ FAIL」で受けて、例外で試験が止まらないようにする。
   ============================================================ */
var T = { pass: 0, fail: 0, log: [] };
function ok(name, cond, extra){
  if (cond) { T.pass++; T.log.push('PASS ' + name); }
  else { T.fail++; T.log.push('FAIL ' + name + (extra !== undefined ? ('  [' + extra + ']') : '')); }
}
function eq(name, a, b){ ok(name, a === b, 'actual=' + a + ' expected=' + b); }
function step(name, fn){
  try { fn(); }
  catch (e) { T.fail++; T.log.push('FAIL ' + name + '  [例外 ' + e + ']'); }
}

/* ---- 保存された設定を捨てて、この版の DEFAULT_SETTINGS から作り直す ----
   同じ番地で前の版を動かしていると、端末に残った古い設定がそのまま使われ、
   札の定義を変えても試験に反映されない（負の対照が空振りする）。
   load() は state が入ったままだと入れ替えないので、先に空にしてから呼ぶ。 */
state = null;
try { window.localStorage.clear(); } catch(e) {}
load();

/* ---- 環境の差し替え（時刻・音・確認・待ち時間） ---- */
var _setTimeout = window.setTimeout;
window.setTimeout = function(f){ try { f(); } catch(e) { T.log.push('ERR in setTimeout: ' + e); } return 0; };

/* 音は差し替えない。本物の snd* をそのまま鳴らしにいかせて、
   tools/mkpage.py の無音化が本当に効いているかを T11 で確かめる。
   絵を描く処理だけは、試験を速くするために止める（音とは関係ない）。 */
confetti = function(){};
drawHanamaru = function(){};

var FAKE_MIN = 17 * 60 + 0;     /* 17:00 */
nowMin = function(){ return FAKE_MIN; };
todayStr = function(){ return '2026-09-16'; };

var ANSWER = true, LASTCONFIRM = '', CONFIRMLOG = [];
askConfirm = function(msg, y, n, cb){ LASTCONFIRM = msg; CONFIRMLOG.push(msg); cb(ANSWER); };

/* ---- 道具（無いものは null／-1／(なし) を返す＝例外にしない） ---- */
/* vs＝「パパと競争する？」の こたえ。省略＝どのクエストも はい（v31〜v32の試験をそのまま使う）／
   'ask'＝まだ聞いていない／'solo'＝どのクエストも いいえ */
function setDay(rest, phase, vs){
  calcRestDay = function(){ return rest; };
  state.today = null;
  state.stamps = 0; state.lastStampDate = ''; state.lastBugDate = '';
  ensureToday();
  state.today.rest = rest;
  if (vs === 'ask') state.today.vs = {};
  else if (vs === 'solo') state.today.vs = { morning: false, main: false, main2: false, after: false };
  else state.today.vs = { morning: true, main: true, main2: true, after: true };
  if (phase) state.today.phase = phase;
  partsOpen = {};
  save();
  render();
}
function rowsOf(id){
  var box = $(id), out = [], i, c;
  if (!box) return out;
  for (i = 0; i < box.childNodes.length; i++) {
    c = box.childNodes[i];
    if (c.className === 'vsRow') out.push(c);
  }
  return out;
}
function rowLen(id, i){ var r = rowsOf(id)[i]; return r ? r.childNodes.length : -1; }
function cardAt(id, i, who){
  var rows = rowsOf(id);
  if (!rows[i]) return null;
  var cs = rows[i].childNodes;
  if (cs.length === 1) return cs[0];
  return (who === 'papa') ? cs[1] : cs[0];
}
function cardCls(id, i, who){ var c = cardAt(id, i, who); return c ? c.className : '(なし)'; }
function cardWho(id, i, who){
  var c = cardAt(id, i, who);
  var n = c && c.childNodes[0];
  return (n && n.textContent) || '(なし)';
}
function click(el){
  var ev = document.createEvent('MouseEvents');
  ev.initEvent('click', true, true);
  el.dispatchEvent(ev);
}
function tap(id, i, who){
  var c = cardAt(id, i, who);
  if (!c) { T.log.push('WARN no card ' + id + ' ' + i + ' ' + who); return; }
  click(c);
}
function partBtns(card){
  var out = [], all, i;
  if (!card) return out;
  all = card.getElementsByTagName('div');
  for (i = 0; i < all.length; i++) {
    if (all[i].className.indexOf('partBtn') === 0) out.push(all[i]);
  }
  return out;
}
/* 中が分かれる札も、できたになるまで面倒を見て押し切る（そら側） */
function tapFull(kind, id, i){
  var guard = 0, card, bs, k, pushed;
  if (doneFor(kind, 'sora')[i]) return;
  tap(id, i, 'sora');
  while (!doneFor(kind, 'sora')[i] && guard++ < 10) {
    card = cardAt(id, i, 'sora');
    if (!card) break;
    bs = partBtns(card);
    if (bs.length === 0) break;
    pushed = false;
    for (k = 0; k < bs.length; k++) {
      if (bs[k].className.indexOf('done') < 0) { click(bs[k]); pushed = true; break; }
    }
    if (!pushed) break;
  }
}
function tapAllSora(kind, id){
  var n = tasksOf(kind).length, i;
  for (i = 0; i < n; i++) { if (!doneFor(kind, 'sora')[i]) tapFull(kind, id, i); }
}
function tapAllPapa(kind, id){
  var n = tasksOf(kind).length, i;
  for (i = 0; i < n; i++) { if (!doneFor(kind, 'papa')[i]) tap(id, i, 'papa'); }
}
function txt(id){ var e = $(id); return (e && e.textContent) || ''; }
function nth(id, i){ var e = $(id); var c = e && e.childNodes[i]; return (c && c.textContent) || '(なし)'; }
function nlen(id){ var e = $(id); return e ? e.childNodes.length : -1; }
function headText(id, i){
  var box = $(id), h = box && box.childNodes[0], c = h && h.childNodes[i];
  return (c && c.textContent) || '(なし)';
}

/* ============================================================
   T1 画面の作り＝そら／パパ の2れつ
   ============================================================ */
step('T1', function(){
  setDay(false, 'morning');
  var box = $('morningCards'), heads = 0, i;
  for (i = 0; i < box.childNodes.length; i++) {
    if (box.childNodes[i].className === 'vsHead') heads++;
  }
  eq('T1-1 れつの見出しは1つ', heads, 1);
  eq('T1-2 見出しの左は そら', headText('morningCards', 0), 'そら');
  eq('T1-3 見出しの右は パパ', headText('morningCards', 1), 'パパ');
  eq('T1-4 行の数＝札の数（平日の朝は8）', rowsOf('morningCards').length, 8);
  eq('T1-5 ふつうの行はカード2枚', rowLen('morningCards', 0), 2);
  eq('T1-6 れんらくちょうの行はカード1枚', rowLen('morningCards', 4), 1);
  ok('T1-7 れんらくちょうの札に both が付く',
     cardCls('morningCards', 4, 'sora').indexOf('both') >= 0, cardCls('morningCards', 4, 'sora'));
  eq('T1-8 左の札の名前は そら', cardWho('morningCards', 0, 'sora'), 'そら');
  eq('T1-9 右の札の名前は パパ', cardWho('morningCards', 0, 'papa'), 'パパ');
  eq('T1-10 共通の札の名前は そらと パパ', cardWho('morningCards', 4, 'sora'), 'そらと パパ');
});

/* ============================================================
   T2 ふたり共通の札（れんらくちょう）
   ============================================================ */
step('T2', function(){
  setDay(false, 'morning');
  tap('morningCards', 4, 'sora');
  ok('T2-1 共通の札を押すと そらが できた', state.today.doneMorning[4] === true);
  ok('T2-2 共通の札を押すと パパも できた', state.today.pMorning[4] === true);
  eq('T2-3 ほかの札は動かない', !!state.today.pMorning[0], false);
  ANSWER = true;
  tap('morningCards', 4, 'sora');
  ok('T2-4 とりけすと そらが もどる', !state.today.doneMorning[4]);
  ok('T2-5 とりけすと パパも もどる', !state.today.pMorning[4]);
});

/* ============================================================
   T3 パパの札＝押すだけ
   ============================================================ */
step('T3a', function(){
  setDay(false, 'morning');
  tap('morningCards', 0, 'papa');
  ok('T3-1 パパの札はパパだけ できた', state.today.pMorning[0] === true);
  ok('T3-2 そらの札は動かない', !state.today.doneMorning[0]);
  tap('morningCards', 2, 'papa');
  ok('T3-3 中が分かれる札も パパは1回で できた', state.today.pMorning[2] === true);
  eq('T3-4 パパの札に中のボタンは無い', partBtns(cardAt('morningCards', 2, 'papa')).length, 0);
  ANSWER = true;
  tap('morningCards', 0, 'papa');
  ok('T3-5 パパの札も とりけせる', !state.today.pMorning[0]);
});
step('T3b', function(){
  setDay(false, 'main2');
  LASTCONFIRM = '';
  tap('main2Cards', 1, 'papa');
  ok('T3-6 パパのおふろは2択を出さない', LASTCONFIRM === '', 'confirm=' + LASTCONFIRM);
  ok('T3-7 パパのおふろで できた', state.today.pMain2[1] === true);
  ok('T3-8 パパのおふろで せんとうにならない', state.today.sento === false);
  tap('main2Cards', 0, 'papa');
  ok('T3-9 パパのごはんで たちあるきの記録は動かない', state.today.walked === false);
  eq('T3-10 どうがタイムは30ふんのまま', rewardMinToday(), 30);
});

/* ============================================================
   T4 かちの判定
   ============================================================ */
step('T4a', function(){
  setDay(false, 'morning');
  ok('T4-1 はじめは かちは きまっていない', winnerOf('morning') === null);
  tapAllPapa('morning', 'morningCards');
  eq('T4-2 パパが先にそろえると パパの かち', winnerOf('morning'), 'papa');
  eq('T4-3 パパが勝っても画面は進まない', state.today.phase, 'morning');
  ok('T4-4 そらはまだ できていない', !allDoneFor('morning', 'sora'));
  ok('T4-5 共通の札は そらの側も できた', state.today.doneMorning[4] === true);
  tapAllSora('morning', 'morningCards');
  eq('T4-6 そらがそろえると 画面が進む', state.today.phase, 'morningEnd');
  eq('T4-7 かちは パパのまま（あとから追い越さない）', winnerOf('morning'), 'papa');
  eq('T4-8 いってらっしゃいの画面に かちの1行', txt('mEndWin'), '🏆 パパの かち！');
});
step('T4b', function(){
  setDay(false, 'morning');
  tapAllSora('morning', 'morningCards');
  eq('T4-9 そらが先にそろえると そらの かち', winnerOf('morning'), 'sora');
  eq('T4-10 画面も進む', state.today.phase, 'morningEnd');
  eq('T4-11 かちの1行は そら', txt('mEndWin'), '🏆 そらの かち！');
});
step('T4c', function(){
  setDay(true, 'main');
  eq('T4-12 休日はクエスト②の札が0枚', main2TaskList().length, 0);
  ok('T4-13 札が0枚のクエストで かちは きまらない', allDoneFor('main2', 'papa') === false);
});

/* ============================================================
   T5 とくてん表（そら ○／○　パパ ○／○）
   ============================================================ */
step('T5', function(){
  setDay(false, 'morning');
  eq('T5-1 はじめは 2つの表示', nlen('hdProgM'), 2);
  ok('T5-2 左は そら 0／8', nth('hdProgM', 0).indexOf('そら 0／8') === 0, nth('hdProgM', 0));
  ok('T5-3 右は パパ 0／8', nth('hdProgM', 1).indexOf('パパ 0／8') === 0, nth('hdProgM', 1));
  tap('morningCards', 0, 'papa');
  ok('T5-4 パパを1つ押すと パパ 1／8', nth('hdProgM', 1).indexOf('パパ 1／8') === 0, nth('hdProgM', 1));
  ok('T5-5 そらは 0／8 のまま', nth('hdProgM', 0).indexOf('そら 0／8') === 0, nth('hdProgM', 0));
  tapAllPapa('morning', 'morningCards');
  eq('T5-6 かちが きまると 3つめの行が出る', nlen('hdProgM'), 3);
  eq('T5-7 その行は トロフィーと名前', nth('hdProgM', 2), '🏆 パパの かち！');
});

/* ============================================================
   T6 ごほうびは そらがクリアしたときだけ
   ============================================================ */
step('T6', function(){
  setDay(false, 'main');
  tapAllPapa('main', 'mainCards');
  eq('T6-1 パパがクエスト①を終えても画面はそのまま', state.today.phase, 'main');
  eq('T6-2 クエスト①の かちは パパ', winnerOf('main'), 'papa');
  tapAllSora('main', 'mainCards');
  eq('T6-3 そらが終えてクエスト②へ', state.today.phase, 'main2');
  tapAllPapa('main2', 'main2Cards');
  eq('T6-4 パパがクエスト②を終えても どうがタイムへ行かない', state.today.phase, 'main2');
  ok('T6-5 クエスト②の かちは パパ', winnerOf('main2') === 'papa');
  ANSWER = true;   /* ごはん＝たちあるかなかった／おふろ＝せんとう */
  tapAllSora('main2', 'main2Cards');
  eq('T6-6 そらが終えると はなまる（celeb1）', state.today.phase, 'celeb1');
  ok('T6-7 はなまるに かちの1行が出る', txt('celebLines').indexOf('🏆 パパの かち！') >= 0, txt('celebLines'));
  ok('T6-8 せんとうボーナスは そらの2択で効く', state.today.sento === true);
  eq('T6-9 どうがタイムは35ふん', rewardMinToday(), 35);
  eq('T6-10 はなまるの次は どうがタイム', celeb1Contents().btn, 'どうがタイムへ ▶');
  ok('T6-11 見られる分数が0より多い', rewardMinToday() > 0, 'mins=' + rewardMinToday());
});

/* ============================================================
   T7 ごはんの2択（そら側）は いままでどおり効く
   ============================================================ */
step('T7', function(){
  setDay(false, 'main2');
  ANSWER = false;   /* 「たちあるいた －5ふん」を選ぶ */
  tapFull('main2', 'main2Cards', 0);
  ok('T7-1 たちあるいた が記録される', state.today.walked === true);
  eq('T7-2 どうがタイムが5ふん みじかくなる', rewardMinToday(), 25);
  ANSWER = true;
  tap('main2Cards', 0, 'sora');        /* とりけす */
  ok('T7-3 とりけすと たちあるきも もどる', state.today.walked === false);
  eq('T7-4 どうがタイムは30ふんに もどる', rewardMinToday(), 30);
});

/* ============================================================
   T8 おやすみクエストと きょうの けっか
   ============================================================ */
step('T8', function(){
  setDay(false, 'after');
  state.today.win = { morning: 'sora', main: 'sora', main2: 'papa' };
  ANSWER = true;
  tapAllPapa('after', 'afterCards');
  eq('T8-1 パパがおやすみクエストを終えても進まない', state.today.phase, 'after');
  tapAllSora('after', 'afterCards');
  eq('T8-2 そらが終えると できました（celeb2）', state.today.phase, 'celeb2');
  ok('T8-3 できました に かちの1行', txt('celebLines').indexOf('🏆 パパの かち！') >= 0, txt('celebLines'));
  var tl = winTally();
  eq('T8-4 そらの かち回数', tl.sora, 2);
  eq('T8-5 パパの かち回数', tl.papa, 2);
  state.today.phase = 'night';
  nightDrawn = '';
  render();
  eq('T8-6 おやすみ画面の けっか', txt('nightScore'), 'きょうの きょうそう　そら 2かい　パパ 2かい');
});

/* ============================================================
   T9 これまでの作りが こわれていないか（回帰）
   ============================================================ */
step('T9a', function(){
  setDay(false, 'morning');
  eq('T9-1 平日の朝は札8枚', morningTaskList().length, 8);
  setDay(true, 'morning');
  eq('T9-2 休日の朝は札4枚', morningTaskList().length, 4);
  eq('T9-3 休日の朝も2れつ', rowLen('morningCards', 0), 2);
  setDay(false, 'main');
  eq('T9-4 クエスト①は5枚', mainTaskList().length, 5);
  eq('T9-5 クエスト②は4枚', main2TaskList().length, 4);
  setDay(true, 'main');
  eq('T9-6 休日のクエストは6枚', mainTaskList().length, 6);
  eq('T9-7 休日のクエストも2れつ', rowsOf('mainCards').length, 6);
  ANSWER = true;
  tapAllSora('main', 'mainCards');
  eq('T9-8 休日も はなまるまで通る', state.today.phase, 'celeb1');
});
step('T9b', function(){
  setDay(false, 'after');
  ANSWER = true;
  tapAllSora('after', 'afterCards');
  eq('T9-9 おやすみクエストの次は celeb2', state.today.phase, 'celeb2');
  state.today.phase = 'stamp';
  render();
  eq('T9-10 スタンプが1つ増える', state.stamps, 1);
  state.today.phase = 'zukan';
  render();
  eq('T9-11 むしずかんの枠は12', nlen('zkGrid'), ZUKAN.length);
  state.today.phase = 'night';
  nightDrawn = '';
  render();
  ok('T9-12 おやすみ画面が出る', $('scrNight').className.indexOf('on') >= 0);
});
/* T9c・T9d は v33 で中身を入れかえた（しげ指示「ごほうび動画までの実行期限をすべてなくして」）。
   v32までは「20:30を過ぎたら ピタゴラなし」「20:15を過ぎたら どうがタイム0ふん」を確かめていた。 */
step('T9c', function(){
  FAKE_MIN = 20 * 60 + 45;
  setDay(false, 'after');
  ANSWER = true;
  tapAllSora('after', 'afterCards');
  eq('T9-13 20:45に おえても ピタゴラタイムへ進む（ねる時間の しめきりは無い）', state.today.phase, 'celeb2');
  ok('T9-14 ピタゴラタイムの ことばが出る', txt('celebLines').indexOf('ピタゴラタイム') >= 0, txt('celebLines'));
  FAKE_MIN = 17 * 60;
});
step('T9d', function(){
  FAKE_MIN = 20 * 60 + 30;
  setDay(false, 'main2');
  ANSWER = true;
  tapAllSora('main2', 'main2Cards');
  eq('T9-15 20:30に おえても どうがタイムは みじかくならない', celeb1Contents().btn, 'どうがタイムへ ▶');
  ok('T9-15b はなまるの分数は35ふん（せんとう）', txt('celebLines').indexOf('どうがタイム 35ふん！') >= 0, txt('celebLines'));
  FAKE_MIN = 17 * 60;
});
step('T9e', function(){
  setDay(false, 'morning');
  delete state.today.pMorning;
  delete state.today.win;
  ensureToday();
  ok('T9-16 古い「きょう」にパパの入れ物が足される', !!state.today.pMorning);
  ok('T9-17 古い「きょう」に しょうはいの入れ物が足される', !!state.today.win);
  render();
  eq('T9-18 描き直しても札は8枚', rowsOf('morningCards').length, 8);
});


/* ============================================================
   T10 査読の指摘3件（2026-09-16・design-reviewer）への直しの試験
   ============================================================ */
step('T10a', function(){
  /* 指摘1＝とりけしで かち が もどらない（パパ側） */
  setDay(false, 'morning');
  tapAllPapa('morning', 'morningCards');
  eq('T10-1 パパが先にそろえて かち', winnerOf('morning'), 'papa');
  ANSWER = true;
  tap('morningCards', 0, 'papa');                  /* 押しまちがいを とりけす */
  ok('T10-2 パパは未完了にもどる', !allDoneFor('morning', 'papa'));
  ok('T10-3 かちも もどる', winnerOf('morning') === null, 'win=' + winnerOf('morning'));
  eq('T10-4 とくてん表から 🏆の行が消える', nlen('hdProgM'), 2);
  tapAllPapa('morning', 'morningCards');
  eq('T10-5 押し直せば また パパの かち', winnerOf('morning'), 'papa');
  tapAllSora('morning', 'morningCards');
  eq('T10-6 そらが終えれば画面は進む', state.today.phase, 'morningEnd');
});
step('T10b', function(){
  /* 指摘1＝そら側のとりけし（ふたり共通の札）でも もどる */
  setDay(false, 'morning');
  tapAllSora('morning', 'morningCards');
  eq('T10-7 そらが先にそろえて かち', winnerOf('morning'), 'sora');
  state.today.phase = 'morning';
  render();
  ANSWER = true;
  tap('morningCards', 4, 'sora');                  /* れんらくちょう＝ふたり共通の札 */
  ok('T10-8 そらもパパも未完了にもどる',
     !allDoneFor('morning', 'sora') && !allDoneFor('morning', 'papa'));
  ok('T10-9 かちも もどる', winnerOf('morning') === null, 'win=' + winnerOf('morning'));
});
step('T10c', function(){
  /* 指摘2＝休日⇄平日の切替が 朝の かち まで消す。
     本物のボタン（設定画面の「きょうの クエストを 切りかえる」）をそのまま押す。 */
  setDay(false, 'main');
  state.today.win = { morning: 'sora', main: 'papa' };
  state.today.doneMorning = [1, 1, 1, 1, 1, 1, 1, 1];
  state.today.pMorning = [1, 1, 1, 1, 1, 1, 1, 1];
  save();
  var _confirm = window.confirm, _alert = window.alert, alerted = false;
  window.confirm = function(){ return true; };
  window.alert = function(){ alerted = true; };
  click($('btnToggleRest'));
  window.confirm = _confirm; window.alert = _alert;
  ok('T10-10 切替はできた（注意文は出ない）', alerted === false);
  ok('T10-11 休日パターンに変わった', state.today.rest === true);
  eq('T10-12 朝の かち は残る', winnerOf('morning'), 'sora');
  ok('T10-13 やり直すクエストの かち は消える', winnerOf('main') === null, 'main=' + winnerOf('main'));
  eq('T10-14 きょうの かぞえも減らない', winTally().sora, 1);
});
step('T10d', function(){
  /* 指摘3＝版が上がった当日、そらが押していた ふたり共通の札を パパへ写す */
  setDay(false, 'morning');
  state.today.doneMorning[4] = true;   /* v30の端末＝れんらくちょうだけ済み */
  state.today.pMorning = [];           /* v30には パパの入れ物が無い */
  delete state.today.win;
  ensureToday();
  ok('T10-15 ふたり共通の札が パパへ写る', state.today.pMorning[4] === true,
     'pMorning[4]=' + state.today.pMorning[4]);
  render();
  tapAllPapa('morning', 'morningCards');
  ok('T10-16 その日も パパは勝てる', allDoneFor('morning', 'papa'));
  eq('T10-17 かちは パパ', winnerOf('morning'), 'papa');
});


/* ============================================================
   T11 テストのあいだ 音が出ないこと（2026-09-16 しげ指示）
   本物の snd* を呼ばせたうえで、音の入口が1回も作られていないことを確かめる。
   ============================================================ */
step('T11', function(){
  ok('T11-1 無音化が入っている', typeof window.__audioMade === 'number',
     '__audioMade=' + window.__audioMade);
  var before = window.__audioAsked;
  setDay(false, 'morning');
  tap('morningCards', 0, 'papa');          /* 本物の sndTap が走る */
  tap('morningCards', 0, 'papa');          /* とりけし＝本物の sndUndo が走る */
  ok('T11-2 音を出そうとはしている（試験が素通りでない）',
     window.__audioAsked > before, 'asked=' + window.__audioAsked + ' before=' + before);
  eq('T11-3 音の入口は1回も作られていない', window.__audioMade, 0);
  ok('T11-4 AudioContext は使うと失敗する形になっている',
     typeof window.AudioContext === 'function' && window.AudioContext.name === 'blocked',
     'name=' + (window.AudioContext && window.AudioContext.name));
  ok('T11-5 動画の枠は作らない', mountPlayer.toString().indexOf('{}') > 0 ||
     mountPlayer.toString().replace(/\s/g, '').indexOf('function(){}') >= 0,
     mountPlayer.toString().slice(0, 40));
});

/* ============================================================
   T12〜T17 v33（2026-10-14 しげ指示）
   ①ごほうび動画までの実行期限をすべてなくす
   ②すべてのクエストで「パパと競争する？」を聞き、はい／いいえ で パパの れつを出し分ける
   ③おかえり画面の「ふつうの日」「まちこ先生の日」＝後者は ワークと ごはんを 入れない
   ④「しじまちゲーム」を「ぷちゲーム」へ
   ============================================================ */
function isOn(id){ var e = $(id); return !!e && e.className.indexOf('on') >= 0; }
function headCount(id){
  var box = $(id), n = 0, i;
  if (!box) return -1;
  for (i = 0; i < box.childNodes.length; i++) { if (box.childNodes[i].className === 'vsHead') n++; }
  return n;
}

/* T12 「パパと競争する？」の確認画面 */
step('T12a', function(){
  setDay(false, 'morning', 'ask');
  ok('T12-1 おはようクエストの前に 確認画面が出る', isOn('scrVsAsk'), $('scrVsAsk').className);
  ok('T12-2 札の画面は まだ出ない', !isOn('scrMorning'));
  eq('T12-3 確認画面の題は おはよう クエスト', txt('vsAskTitle'), 'おはよう クエスト');
  ok('T12-4 ことばは「パパと競争する？」', txt('scrVsAsk').indexOf('パパと競争する？') >= 0, txt('scrVsAsk'));
  eq('T12-5 はい の ボタン', txt('btnVsYes'), 'はい');
  eq('T12-6 いいえ の ボタン', txt('btnVsNo'), 'いいえ');
  click($('btnVsYes'));
  ok('T12-7 はい が記録される', state.today.vs.morning === true);
  ok('T12-8 札の画面が出る', isOn('scrMorning'));
  eq('T12-9 はい＝2れつ', rowLen('morningCards', 0), 2);
  eq('T12-10 れつの見出しが出る', headCount('morningCards'), 1);
});
step('T12b', function(){
  setDay(false, 'main', 'ask');
  eq('T12-11 クエスト①の前にも聞く', txt('vsAskTitle'), 'クエスト①');
  click($('btnVsYes'));
  ANSWER = true;
  tapAllSora('main', 'mainCards');
  eq('T12-12 クエスト①のあと クエスト②へ', state.today.phase, 'main2');
  ok('T12-13 クエスト②の前にも聞く', isOn('scrVsAsk'));
  eq('T12-14 題は クエスト②', txt('vsAskTitle'), 'クエスト②');
  ok('T12-15 クエスト①クリアの お祝いが 上に出ている', $('ovCeleb').className.indexOf('on') >= 0);
  click($('btnVsNo'));
  ok('T12-16 クエスト②は いいえ が記録される', state.today.vs.main2 === false);
  ok('T12-17 クエスト①の こたえは そのまま', state.today.vs.main === true);
  eq('T12-18 クエスト②は1れつ', rowLen('main2Cards', 0), 1);
});
step('T12c', function(){
  setDay(false, 'after', 'ask');
  eq('T12-19 おやすみクエストの前にも聞く', txt('vsAskTitle'), 'おやすみクエスト');
  setDay(true, 'main', 'ask');
  eq('T12-20 休日のクエストの前にも聞く', txt('vsAskTitle'), 'きょうの クエスト');
  setDay(true, 'morning', 'ask');
  eq('T12-21 休日の朝の前にも聞く', txt('vsAskTitle'), 'おはよう クエスト');
  ok('T12-22 休日のクエスト②（札0枚）は聞かない', needVsAsk('main2') === false);
});

/* T13 いいえ＝パパの れつを 出さない */
step('T13a', function(){
  setDay(false, 'morning', 'ask');
  click($('btnVsNo'));
  ok('T13-1 いいえ が記録される', state.today.vs.morning === false);
  eq('T13-2 れつの見出しは出ない', headCount('morningCards'), 0);
  eq('T13-3 行の数は8のまま', rowsOf('morningCards').length, 8);
  eq('T13-4 どの行も そらの札1枚', rowLen('morningCards', 0), 1);
  ok('T13-5 札は 左右いっぱい（solo）', cardCls('morningCards', 0, 'sora').indexOf('solo') >= 0, cardCls('morningCards', 0, 'sora'));
  ok('T13-6 れんらくちょうも solo（またがりではない）',
     cardCls('morningCards', 4, 'sora').indexOf('solo') >= 0 && cardCls('morningCards', 4, 'sora').indexOf('both') < 0,
     cardCls('morningCards', 4, 'sora'));
  var c0 = cardAt('morningCards', 0, 'sora');
  eq('T13-7 札に名前を出さない（1つめは絵文字）', c0 && c0.childNodes[0].className, 'c-emoji');
  eq('T13-8 とくてん表は そらだけ', nlen('hdProgM'), 1);
  ok('T13-9 とくてん表の文字', nth('hdProgM', 0).indexOf('そら 0／8') === 0, nth('hdProgM', 0));
  tap('morningCards', 0, 'sora');
  ok('T13-10 押したあとも solo のまま', cardCls('morningCards', 0, 'sora').indexOf('solo') >= 0 &&
     cardCls('morningCards', 0, 'sora').indexOf('done') >= 0, cardCls('morningCards', 0, 'sora'));
  tapAllSora('morning', 'morningCards');
  eq('T13-11 そらが おえると 画面が進む', state.today.phase, 'morningEnd');
  ok('T13-12 かちは つくらない', winnerOf('morning') === null, 'win=' + winnerOf('morning'));
  eq('T13-13 いってらっしゃいに かちの行は出ない', txt('mEndWin'), '');
});
step('T13b', function(){
  setDay(false, 'main', 'solo');
  ANSWER = true;
  tapAllSora('main', 'mainCards');
  eq('T13-14 クエスト②へ進む', state.today.phase, 'main2');
  eq('T13-15 クエスト①クリアの お祝いは出る', txt('celebTitle'), 'クエスト① クリア！');
  ok('T13-16 お祝いに かちの行は無い', txt('celebLines').indexOf('🏆') < 0, txt('celebLines'));
  tapAllSora('main2', 'main2Cards');
  eq('T13-17 はなまるへ', state.today.phase, 'celeb1');
  ok('T13-18 はなまるに かちの行は無い', txt('celebLines').indexOf('🏆') < 0, txt('celebLines'));
  state.today.phase = 'night';
  nightDrawn = '';
  render();
  eq('T13-19 きょうそうしなかった日は おやすみ画面に けっかを出さない', txt('nightScore'), '');
});
step('T13c', function(){
  setDay(false, 'night', 'solo');
  state.today.vs.morning = true;
  state.today.win = { morning: 'sora' };
  nightDrawn = '';
  render();
  eq('T13-20 1つでも きょうそうした日は けっかを出す', txt('nightScore'), 'きょうの きょうそう　そら 1かい　パパ 0かい');
});

/* T14 おかえり画面の「ふつうの日」「まちこ先生の日」 */
step('T14a', function(){
  setDay(false, 'welcome', 'ask');
  ok('T14-1 おかえり画面が出る', isOn('scrWelcome'));
  eq('T14-2 ふつうの日 の ボタン', txt('btnDayNormal'), 'ふつうの日');
  eq('T14-3 まちこ先生の日 の ボタン', txt('btnDayMachiko'), 'まちこ先生の日');
  ok('T14-4 10ぷんの ことばは出ない', txt('scrWelcome').indexOf('ぷん') < 0, txt('scrWelcome'));
  ok('T14-5 チャレンジの ボタンは無い', !$('btnChallenge'));
  click($('btnDayMachiko'));
  ok('T14-6 まちこ先生の日が記録される', state.today.machiko === true);
  eq('T14-7 クエスト①へ進む', state.today.phase, 'main');
  ok('T14-8 クエスト①の前に きょうそうの確認', isOn('scrVsAsk'));
  click($('btnVsYes'));
  eq('T14-9 クエスト①は5枚のまま', mainTaskList().length, 5);
  eq('T14-10 クエスト②は2枚', main2TaskList().length, 2);
  eq('T14-11 1枚目は おふろ', main2TaskList()[0] && main2TaskList()[0].t, 'おふろに はいる');
  eq('T14-12 2枚目は ぷちゲーム', main2TaskList()[1] && main2TaskList()[1].t, 'ぷちゲーム');
  ANSWER = true;
  tapAllSora('main', 'mainCards');
  click($('btnVsYes'));
  eq('T14-13 クエスト②の行は2', rowsOf('main2Cards').length, 2);
  CONFIRMLOG = [];
  ANSWER = false;   /* おふろ（せんとうではない） */
  tapAllSora('main2', 'main2Cards');
  eq('T14-14 はなまるへ', state.today.phase, 'celeb1');
  ok('T14-15 ごはんの2択は出ない（出た確認は おふろの1つだけ）',
     CONFIRMLOG.length === 1 && CONFIRMLOG[0].indexOf('ごはん') < 0, CONFIRMLOG.join('|'));
  eq('T14-16 どうがタイムは30ふん', rewardMinToday(), 30);
});
step('T14b', function(){
  setDay(false, 'welcome');
  click($('btnDayNormal'));
  ok('T14-17 ふつうの日が記録される', state.today.machiko === false);
  eq('T14-18 クエスト②は4枚', main2TaskList().length, 4);
  eq('T14-19 3枚目は ぷちゲーム', main2TaskList()[2] && main2TaskList()[2].t, 'ぷちゲーム');
  eq('T14-20 4枚目は ワーク', main2TaskList()[3] && main2TaskList()[3].t, 'ワークを する');
  state.today.machiko = true;
  openSettings();
  ok('T14-21 設定画面に まちこ先生の日と出る', txt('dayInfo').indexOf('まちこ先生の日') >= 0, txt('dayInfo'));
  $('ovSettings').className = 'ov';
});
step('T14c', function(){
  FAKE_MIN = 9 * 60;
  setDay(false, 'main');
  state.today.machiko = true;
  ok('T14-22 日を えらんだあとは 朝へ戻さない', backToMorningIfIdle() === false);
  state.today.machiko = null;
  ok('T14-23 えらぶ前で 何も押していない朝は 朝へ戻す（v32と同じ）', backToMorningIfIdle() === true);
  FAKE_MIN = 17 * 60;
});

/* T15 ごほうび動画までの 実行期限は 無い */
step('T15', function(){
  ok('T15-1 しめきりバーの部品は無い', !$('limit1') && !$('limit2') && !$('limit3'));
  ok('T15-2 設定に しめきりの値は無い',
     state.settings.videoEndBy === undefined && state.settings.bedCutoff === undefined &&
     state.settings.quest2By === undefined && state.settings.challengeMin === undefined);
  FAKE_MIN = 22 * 60;
  setDay(false, 'main2');
  ANSWER = true;
  tapAllSora('main2', 'main2Cards');
  eq('T15-3 22:00に おえても はなまる', state.today.phase, 'celeb1');
  click($('btnCeleb'));
  eq('T15-4 どうがタイムへ進む', state.today.phase, 'video1');
  eq('T15-5 見られる時間は35ふん（せんとう）＝時刻で へらない', videoConf().minutes, 35);
  ok('T15-6 どうがの画面が出る', isOn('scrVideo'));
  FAKE_MIN = 17 * 60;
});

/* T16 なまえの変更 */
step('T16', function(){
  var lists = ['morningTasks', 'morningTasksRest', 'mainTasks', 'mainTasks2', 'holidayTasks', 'afterTasks'], i, j, hit = 0;
  for (i = 0; i < lists.length; i++) {
    for (j = 0; j < state.settings[lists[i]].length; j++) {
      if (state.settings[lists[i]][j].t.indexOf('しじまち') >= 0) hit++;
    }
  }
  eq('T16-1 しじまちゲーム は どこにも無い', hit, 0);
  eq('T16-2 クエスト②の3枚目は ぷちゲーム', state.settings.mainTasks2[2].t, 'ぷちゲーム');
});

/* T17 版が上がった当日（v32の「きょう」）の引き継ぎ */
step('T17', function(){
  setDay(false, 'main2');
  delete state.today.vs;
  delete state.today.machiko;
  state.today.chStart = 12345;
  state.today.doneMain = [true, true, true, true, true];
  state.today.doneMain2 = [true];
  ensureToday();
  ok('T17-1 押し始めた クエスト②は きょうそう あり', state.today.vs.main2 === true);
  ok('T17-2 おわった クエスト①も きょうそう あり', state.today.vs.main === true);
  ok('T17-3 まだの おやすみクエストは あとで聞く', state.today.vs.after === undefined);
  ok('T17-4 チャレンジを始めていた日は ふつうの日', state.today.machiko === false);
  render();
  ok('T17-5 確認画面を出さず 札の画面のまま', isOn('scrMain2'));
  eq('T17-6 クエスト②は4枚のまま', main2TaskList().length, 4);
  setDay(false, 'main');
  var _confirm = window.confirm;
  window.confirm = function(){ return true; };
  click($('btnToggleRest'));
  window.confirm = _confirm;
  ok('T17-7 休日⇄平日の切替で やり直すクエストは 聞き直す', state.today.vs.main === undefined);
});

/* T18 押しまちがいから戻る道（v33査読の指摘1） */
step('T18a', function(){
  setDay(false, 'main2', 'ask');
  state.today.vs.main = true;
  click($('btnVsNo'));
  ok('T18-1 クエスト②で いいえ を押した', state.today.vs.main2 === false);
  tapFull('main2', 'main2Cards', 2);           /* ぷちゲームを1枚押してから気づいた */
  click($('btnReaskVs'));
  ok('T18-2 聞き直すと 確認画面が出る', isOn('scrVsAsk'));
  ok('T18-3 クエスト①の こたえは 消えない', state.today.vs.main === true);
  ok('T18-4 押した札は 消えない', state.today.doneMain2[2] === true);
  click($('btnVsYes'));
  eq('T18-5 こんどは 2れつ', rowLen('main2Cards', 0), 2);
});
step('T18b', function(){
  setDay(false, 'main');
  state.today.machiko = true;
  state.today.doneMorning = [1, 1, 1, 1, 1, 1, 1, 1];
  state.today.win = { morning: 'sora' };
  var _confirm = window.confirm, _alert = window.alert, alerted = 0;
  window.confirm = function(){ return true; };
  window.alert = function(){ alerted++; };
  click($('btnToggleMachiko'));
  ok('T18-6 まちこ先生の日 → ふつうの日 へ戻せる', state.today.machiko === false);
  eq('T18-7 クエスト②は4枚に戻る', main2TaskList().length, 4);
  ok('T18-8 朝の記録と かちは 消えない', state.today.doneMorning[0] === 1 && winnerOf('morning') === 'sora');
  state.today.doneMain2 = [true];
  click($('btnToggleMachiko'));
  eq('T18-9 クエスト②を押しはじめたら 切り替えない（注意文）', alerted, 1);
  ok('T18-10 ふつうの日のまま', state.today.machiko === false);
  window.confirm = _confirm; window.alert = _alert;
});

/* T19 シンカリオンの追加と、再生中のチャンネル選び直し（v34・2026-10-14 しげ指示） */
step('T19a', function(){
  var names = [], i;
  for (i = 0; i < VIDEO_SOURCES.main.length; i++) names.push(VIDEO_SOURCES.main[i].name);
  eq('T19-1 どうがタイムのチャンネルの並び', names.join('|'), 'むしおかだいき|もりこんにゃく|シンカリオン');
  eq('T19-2 シンカリオンは再生リストのID', VIDEO_SOURCES.main[2].id, 'PLhWipIfRhqz287Ri53YFJWWiGn5f1xfwb');
  /* 本数は毎朝の便で増減する（見られない動画を外す）ので「1本以上」で見る */
  ok('T19-3 シンカリオンの動画が一覧に入っている', bakedItemsOf(1, VIDEO_SOURCES.main[2].id).length >= 1,
     bakedItemsOf(1, VIDEO_SOURCES.main[2].id).length);
  setDay(false, 'video1');
  state.today.endAt = null;
  setChosenSrc(1, -1);
  render();
  var withItems = 0;
  for (i = 0; i < VIDEO_SOURCES.main.length; i++) { if (bakedItemsOf(1, VIDEO_SOURCES.main[i].id).length) withItems++; }
  eq('T19-4 えらぶ画面のボタン＝動画のあるチャンネルの数（いまは3つ）', nlen('vidPickBtns') + '/' + withItems, '3/3');
  eq('T19-5 3つめは シンカリオン', nth('vidPickBtns', 2), 'シンカリオン');
});
step('T19b', function(){
  var reloads = 0, _rp = reloadPage;
  reloadPage = function(){ reloads++; };
  setDay(false, 'video1');
  state.today.endAt = null;
  setChosenSrc(1, -1);
  render();
  click($('vidPickBtns').childNodes[2]);
  eq('T19-6 スタート前に選ぶと シンカリオンが選ばれる', chosenSrc(1), 2);
  eq('T19-7 スタート前は 読み直さない', reloads, 0);
  var endAt = Date.now() + 10 * 60000;
  state.today.endAt = endAt;
  state.vidSkips = 3;
  save();
  render();
  setBigVid(true);   /* 試験では枠を作らない（無音化）ので、再生中の大画面を手で立てておく */
  click($('btnVidChan'));
  eq('T19-8 再生中の「チャンネル」で読み直す', reloads, 1);
  eq('T19-9 選んでいたチャンネルは いったん消える', chosenSrc(1), -1);
  render();
  ok('T19-10 読み直したあとは えらぶ画面', $('vidPickWrap').style.display === 'block', $('vidPickWrap').style.display);
  ok('T19-11 大画面ではない', document.body.className.indexOf('bigvid') < 0, document.body.className);
  eq('T19-12 時間は そのまま すすむ', txt('vidPickNote'), 'じかんは そのまま すすむよ。');
  eq('T19-13 終わり時刻は変わらない', state.today.endAt, endAt);
  click($('vidPickBtns').childNodes[0]);
  eq('T19-14 別のチャンネルを選び直せる', chosenSrc(1), 0);
  eq('T19-15 選び直したら読み直して再生へ', reloads, 2);
  eq('T19-16 飛ばした数は0に戻る', state.vidSkips, 0);
  eq('T19-17 その日の開始位置から', state.today.vidCur,
     startIndexForToday(bakedForKind(1).items.length, 1));
  eq('T19-18 終わり時刻は変わらない（選び直しても のびない）', state.today.endAt, endAt);
  setDay(false, 'video2');
  state.today.endAt = null;
  setChosenSrc(2, -1);
  render();
  eq('T19-19 ねるまえタイムのチャンネルは2つのまま', nlen('vidPickBtns'), 2);
  reloadPage = _rp;
});

/* ---- 結果 ---- */
window.setTimeout = _setTimeout;
(function(){
  var pre = document.createElement('pre'), fails = [], i;
  for (i = 0; i < T.log.length; i++) { if (T.log[i].indexOf('PASS') !== 0) fails.push(T.log[i]); }
  pre.id = 'tresult';
  pre.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:99999;background:#fff;color:#000;font-size:13px;overflow:auto;padding:12px;margin:0;white-space:pre-wrap';
  pre.textContent = 'RESULT total=' + (T.pass + T.fail) + ' PASS=' + T.pass + ' FAIL=' + T.fail +
    '\n\n' + (fails.length ? fails.join('\n') : '(FAILなし)') + '\n\n---- 全件 ----\n' + T.log.join('\n');
  document.body.appendChild(pre);
  document.title = 'total=' + (T.pass + T.fail) + ' PASS=' + T.pass + ' FAIL=' + T.fail;
  window.__T = T;
})();

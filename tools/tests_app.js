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

var ANSWER = true, LASTCONFIRM = '';
askConfirm = function(msg, y, n, cb){ LASTCONFIRM = msg; cb(ANSWER); };

/* ---- 道具（無いものは null／-1／(なし) を返す＝例外にしない） ---- */
function setDay(rest, phase){
  calcRestDay = function(){ return rest; };
  state.today = null;
  state.stamps = 0; state.lastStampDate = ''; state.lastBugDate = '';
  ensureToday();
  state.today.rest = rest;
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
  ok('T6-11 見られる分数が0より多い', rewardMinNow() > 0, 'mins=' + rewardMinNow());
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
step('T9c', function(){
  FAKE_MIN = 20 * 60 + 45;
  setDay(false, 'after');
  ANSWER = true;
  tapAllSora('after', 'afterCards');
  eq('T9-13 ねる時間を過ぎたら まっすぐ おやすみへ', state.today.phase, 'night');
  ok('T9-14 bedOk は false', state.today.bedOk === false);
  FAKE_MIN = 17 * 60;
});
step('T9d', function(){
  FAKE_MIN = 20 * 60 + 30;
  setDay(false, 'main2');
  ANSWER = true;
  tapAllSora('main2', 'main2Cards');
  eq('T9-15 どうがタイムは0ふん', rewardMinNow(), 0);
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

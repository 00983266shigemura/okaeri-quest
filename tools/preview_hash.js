/* 目視用の複製に差し込む小さな道具（tools/mkpage.py が入れる）。
   アドレスの末尾で見たい画面を指定して開く。
     #morning / #restmorning / #welcome / #main / #main2 / #after / #rest
     #stamp / #zukan / #night
   うしろに -ask を付けると「パパと競争する？」の確認画面、-solo を付けると
   パパの れつ なし（いいえ）で開く（v33）。付けなければ はい（2れつ）。
     例 #morning-ask / #main2-solo
   #main2-machiko＝まちこ先生の日の クエスト②。
   #after-later＝ワークを「あとで」にした日の おやすみクエスト（札が1枚ふえる）。
   index.html 本体はさわらない。音は mkpage.py の無音化で出ない。 */
(function(){
  var raw = (location.hash || '').replace('#', '');
  if (!raw) return;
  var parts = raw.split('-'), h = parts[0], opt = parts[1] || '';
  var rest = (h === 'rest' || h === 'restmorning');
  calcRestDay = function(){ return rest; };
  /* tick() の syncMorningPhase に朝の画面を閉じられないようにする（目視用） */
  if (h === 'morning' || h === 'restmorning') isMorningTime = function(){ return true; };
  else isMorningTime = function(){ return false; };
  state.today = null;
  ensureToday();
  state.today.rest = rest;
  if (opt === 'ask') state.today.vs = {};
  else if (opt === 'solo') state.today.vs = { morning: false, main: false, main2: false, after: false };
  else state.today.vs = { morning: true, main: true, main2: true, after: true };
  if (opt === 'machiko') state.today.machiko = true;
  /* #after-later＝ワークを「あとで」にした日の おやすみクエスト（v37） */
  if (opt === 'later') state.today.workLater = true;
  if (h === 'morning' || h === 'restmorning') state.today.phase = 'morning';
  else if (h === 'welcome') state.today.phase = 'welcome';
  else if (h === 'main' || h === 'rest') state.today.phase = 'main';
  else if (h === 'main2') state.today.phase = 'main2';
  else if (h === 'after') state.today.phase = 'after';
  else if (h === 'stamp') state.today.phase = 'stamp';
  else if (h === 'zukan') state.today.phase = 'zukan';
  else if (h === 'night') state.today.phase = 'night';
  else if (h === 'video1') {
    /* #video1＝どうがタイムの「どの チャンネルに する？」。
       #video1-playpick＝再生中に「チャンネル」で選び直している画面（v34） */
    state.today.phase = 'video1';
    state.today.srcMain = -1;
    state.today.endAt = (opt === 'playpick') ? (Date.now() + 12 * 60000) : null;
  }
  save();
  render();
})();

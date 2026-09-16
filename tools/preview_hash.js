/* 目視用の複製に差し込む小さな道具（tools/mkpage.py が入れる）。
   アドレスの末尾で見たい画面を指定して開く。
     #morning / #restmorning / #main / #main2 / #after / #rest
     #stamp / #zukan / #night
   index.html 本体はさわらない。音は mkpage.py の無音化で出ない。 */
(function(){
  var h = (location.hash || '').replace('#', '');
  if (!h) return;
  var rest = (h === 'rest' || h === 'restmorning');
  calcRestDay = function(){ return rest; };
  /* tick() の syncMorningPhase に朝の画面を閉じられないようにする（目視用） */
  if (h === 'morning' || h === 'restmorning') isMorningTime = function(){ return true; };
  else isMorningTime = function(){ return false; };
  state.today = null;
  ensureToday();
  state.today.rest = rest;
  if (h === 'morning' || h === 'restmorning') state.today.phase = 'morning';
  else if (h === 'main' || h === 'rest') state.today.phase = 'main';
  else if (h === 'main2') state.today.phase = 'main2';
  else if (h === 'after') state.today.phase = 'after';
  else if (h === 'stamp') state.today.phase = 'stamp';
  else if (h === 'zukan') state.today.phase = 'zukan';
  else if (h === 'night') state.today.phase = 'night';
  save();
  render();
})();

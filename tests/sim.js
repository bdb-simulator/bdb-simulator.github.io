// 무작위 자동 대전으로 엔진 검증 (브라이트 규칙)
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const ctx = {};
new Function('ctx', code + '\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.RED=DECK_RED;ctx.BLUE=DECK_BLUE;ctx.DECKS=DECKS;ctx.RULES=RULES;')(ctx);
const { Engine, DEFS, RED, BLUE, RULES, DECKS } = ctx;
const pick = a => a[Math.floor(Math.random() * a.length)];
const SAMPLES = Object.keys(DECKS).filter(k => DECKS[k].sample);
// 전체 카드 DB에서 텍스트 능력(ab)이 있는 카드로 무작위 덱을 만들어 섞어 넣음
const DB = JSON.parse(fs.readFileSync(require('path').join(require('path').dirname(process.argv[2]), 'cards_db.json'), 'utf8'));
for (const [k, d] of Object.entries(DB.defs)) if (!DEFS[k]) DEFS[k] = Object.assign({ id: k, icon: null, attr: [], icons: [], titles: [] }, d);
const ABU = DB.base.map(String).filter(k => DEFS[k].ab && DEFS[k].type !== 'territory');
const ABT = DB.base.map(String).filter(k => DEFS[k].ab && DEFS[k].type === 'territory');
for (let i = 0; i < 40; i++) {
  const main = []; for (let j = 0; j < 12; j++) main.push([pick(ABU), 4]);
  DECKS['fz' + i] = { label: 'fuzz' + i, territory: pick(ABT), main, fuzz: 1 };
}
const CB = (process.argv[3] || '').startsWith('cb:') ? DB.collabs.findIndex(n => n.includes(process.argv[3].slice(3))) : -1;
if (CB >= 0) {
  const U = DB.base.map(String).filter(k => DEFS[k].cb === CB && DEFS[k].type !== 'territory');
  const T = DB.base.map(String).filter(k => DEFS[k].cb === CB && DEFS[k].type === 'territory');
  for (let i = 0; i < 40; i++) { const main = []; for (let j = 0; j < 12; j++) main.push([pick(U), 4]); DECKS['fz' + i] = { label: 'cb' + i, territory: pick(T), main, fuzz: 1 }; }
  console.log('작품:', DB.collabs[CB], U.length, T.length);
}
const FUZZ = Object.keys(DECKS).filter(k => DECKS[k].fuzz);
const PAIRS = (process.argv[3] === 'fuzz' || (process.argv[3] || '').startsWith('cb:')) ? [0] : [['bocchi','bocchi'],['bocchi','red'],['blue','bocchi'],['red','blue'], null, null, null, null];

const UNH = {};
process.on('exit', () => { if (Object.keys(UNH).length) console.log('UNHANDLED', JSON.stringify(UNH)); });
function check(s) {
  for (const l of (s.log || []).slice(-8)) { const t = typeof l === 'string' ? l : l.m || ''; const m = /처리하지 못한 효과: (\w+)/.exec(t); if (m) UNH[m[1]] = (UNH[m[1]] || 0) + 1; }
  for (let p = 0; p < 2; p++) {
    const P = s.players[p];
    const real = z => (z || []).filter(c => c.id !== 'CLASS').length;
    const n = real(P.set) + real(P.deck) + real(P.hand) + real(P.life) + real(P.energy) + real(P.drop) + real(P.remove)
      + s.field.filter(u => u.owner === p).reduce((t, u) => t + 1 + real(u.att), 0) + real(P.territory.att)
      + (s.pending?.type === 'shot' && s.pending.player === p ? 1 : 0);
    if (n !== s.size[p]) throw new Error(`카드 수 불일치 P${p + 1}: ${n} / ${s.size[p]}`);
  }
  { const seen = new Set(); const all = []; for (let q = 0; q < 2; q++) { const P = s.players[q]; for (const z of ['set','deck','hand','life','energy','drop','remove']) for (const c of P[z] || []) all.push(c.uid); for (const c of P.territory.att || []) all.push(c.uid); }
    for (const u of s.field) { all.push(u.uid); for (const c of u.att || []) all.push(c.uid); }
    for (const x of all) { if (seen.has(x)) throw new Error('같은 카드(uid 중복)가 두 곳에 있음: ' + x); seen.add(x); } }
  for (const u of s.field) { if (Engine.hasKw(s, u, 'indestructible')) continue; const pw = Engine.power(s, u); if (pw <= 0 || u.damage >= pw) throw new Error('파괴되지 않은 유닛'); }
  if (s.winner == null && !s.pending && (s.queue.length || s.conts.length)) throw new Error('처리 대기열이 남은 채 멈춤');
}

const st = { games: 0, turns: 0, wins: [0, 0], events: {} };
const ev = k => st.events[k] = (st.events[k] || 0) + 1;
if (PAIRS[0] !== 0) console.log('덱 검사:', Object.fromEntries(Object.entries(DECKS).map(([k,d])=>[k,Engine.validateDeck(d)])));
for (let g = 0; g < 1200; g++) {
  const pr = PAIRS[0] === 0 ? [pick(FUZZ), pick(FUZZ)] : PAIRS[g % PAIRS.length] || [pick(SAMPLES), pick(SAMPLES)];
  let s = Engine.newGame(DECKS[pr[0]], DECKS[pr[1]]);
  const size = pr.map(k => DECKS[k].main.reduce((t, [, n]) => t + n, 0));
  s.size = size;
  let steps = 0;
  const act = a => { s = Engine.apply(s, a); s.size = size; check(s); };
  const ALL = s2 => { const r = []; for (let q = 0; q < 2; q++) for (const z of ['hand','drop','energy','life','deck']) for (const c of s2.players[q][z]) r.push(c.uid); s2.field.forEach(u => r.push(u.uid)); return r; };
  const OPS = [['move','hand'],['move','drop'],['move','energy'],['move','life'],['move','deckTop'],['move','deckBottom'],['move','field'],['rest'],['pow'],['hitmod'],['dmg'],['draw'],['shuffle'],['lifeFromDeck'],['lifeToHand'],['move','remove']];
  while (s.winner == null) {
    if (++steps > 8000) throw new Error('게임이 끝나지 않음');
    const pd = s.pending;
    if (pd) {
      ev(pd.type);
      const P = s.players[pd.player];
      if (pd.type === 'order') { ev('order'); act({ type: 'ORDER', i: Math.floor(Math.random() * pd.items.length) }); }
      else if (pd.type === 'mulligan') act({ type: 'MULLIGAN', redraw: Math.random() < .3 });
      else if (pd.type === 'block') {
        const bl = s.field.filter(u => u.owner === pd.player && !u.rested && u.uid !== pd.target && !Engine.hasKw(s, u, 'noBlock'));
        { const must = Engine.blockRequired(s, s.pending); act({ type: 'BLOCK', blocker: (must || Math.random() < .5) && bl.length ? pick(bl).uid : null }); }
      } else if (pd.type === 'shot') {
        const d = DEFS[pd.card.id], ts = Engine.targetsFor(s, pd.player, d);
        act({ type: 'SHOT', play: Math.random() < .85, target: ts.length ? pick(ts) : undefined });
      } else if (pd.type === 'discard') act({ type: 'DISCARD', uid: pick(P.hand).uid });
      else if (pd.type === 'territory') {
        const can = P.energy.filter(e => !e.rested).length >= pd.cost;
        act({ type: 'TERRITORY', open: can && Math.random() < .9 });
      } else if (pd.type === 'bright') {
        const b = DEFS[Engine.findUnit(s, pd.uid).id].bright;
        const ok = P.hand.filter(c => { try { Engine.apply(s, { type: 'BRIGHT', discard: c.uid }); return true; } catch { return false; } });
        // 일부러 틀린 카드도 시도
        const bad = P.hand.find(c => !ok.includes(c) && DEFS[c.id].type !== 'command');
        if (bad) { try { Engine.apply(s, { type: 'BRIGHT', discard: bad.uid }); throw new Error('잘못된 브라이트가 통과됨'); } catch (e) { if (e.message.includes('통과')) throw e; } }
        act({ type: 'BRIGHT', discard: Math.random() < .8 ? pick(ok).uid : null });
      } else if (pd.type === 'scout') {
        const ids = P.deck.slice(0, pd.n).map(c => c.uid), top = [], bottom = [];
        for (const u of ids) (Math.random() < .5 ? top : bottom).push(u);
        act({ type: 'SCOUT', top, bottom });
      } else if (pd.type === 'seika') {
        if (pd.step === 'discard') act({ type: 'SEIKA', uid: Math.random() < .8 ? pick(P.hand).uid : null });
        else act({ type: 'SEIKA', uid: pick(Engine.seikaTargets(s, pd.player)) });
      } else if (pd.type === 'flashback') {
        act({ type: 'FLASHBACK', uid: Math.random() < .85 ? pick(Engine.flashTargets(s, pd.player)) : null });
      } else if (pd.type === 'dress') { ev('dress'); act({ type: 'DRESS', unit: Math.random() < .8 ? pick(pd.cands) : null });
      } else if (pd.type === 'setPlay') { ev('setPlay'); act({ type: 'PLAY_SET', uid: Math.random() < .8 ? pick(pd.cands) : null });
      } else if (pd.type === 'cosplay') {
        ev('cosplay');
        act({ type: 'COSPLAY', pick: Math.random() < .75 ? pick(pd.cands) : null });
      } else if (pd.type === 'manual') {
        ev('manualPrompt');
        if (Math.random() < .5) { try { act({ type: 'MANUAL', op: 'draw', p: pd.player }); } catch (e) {} }
        if (s.winner == null) act({ type: 'MANUAL', op: 'done' });
      } else if (pd.type === 'fx') {
        ev('fx_' + pd.kind + '_' + (pd.q.steps[pd.q.i]?.op || ''));
        if (pd.kind === 'confirm') act({ type: 'FX', yes: Math.random() < .8 });
        else if (pd.kind === 'choose') { const ok = [...Array(pd.n).keys()].filter(k => !pd.dis?.includes(k)); act({ type: 'FX', choice: ok[Math.floor(Math.random() * ok.length)] }); }
        else {
          // 일부러 틀린 선택도 시도
          if (pd.min > 0) { try { Engine.apply(s, { type: 'FX', uids: [] }); throw new Error('잘못된 선택이 통과됨'); } catch (e) { if (e.message.includes('통과')) throw e; } }
          let done = false;
          for (let tr = 0; tr < 200 && !done; tr++) {
            const c = [...pd.cands].sort(() => Math.random() - .5);
            let k = pd.min + Math.floor(Math.random() * (pd.max - pd.min + 1));
            if (pd.each) k = Math.min(k, Math.max(pd.min, 1));
            if (tr > 100) k = pd.min;
            if (pd.same && tr > 20) {   // 이름이 같은 묶음에서 고르기
              const idOf = uid => { for (const P of s.players) for (const z of ['hand', 'drop', 'energy', 'life', 'deck']) { const x = (P[z] || []).find(c => c.uid === uid); if (x) return x.id; } return null; };
              const g = {}; for (const u of pd.cands) (g[DB.defs[idOf(u)]?.name] ||= []).push(u);
              const grp = Object.values(g).find(x => x.length >= pd.min); if (grp) { c.splice(0, c.length, ...grp); k = pd.min; }
            }
            try { act({ type: 'FX', uids: c.slice(0, k) }); done = true; }
            catch (e) { if (!(pd.each || pd.distinct || pd.same || pd.sumPowLE != null) || !/골라 주세요|고를 수/.test(e.message)) throw e; }
          }
          if (!done) throw new Error('유효한 선택을 찾지 못함: ' + JSON.stringify({ min: pd.min, max: pd.max, distinct: pd.distinct, same: pd.same }));
        }
      } else throw new Error('알 수 없는 선택: ' + pd.type);
      continue;
    }
    if (Math.random() < .04) {   // 수동 조작 무작위 시도
      const [op, to] = pick(OPS), a = { type: 'MANUAL', op, to, uid: pick(ALL(s)), p: Math.random() < .5 ? 0 : 1, v: pick([1000, -1000, 1, -1]) };
      try { act(a); ev('manual_' + op); } catch (e) { if (!/찾을 수|아닙니다|유닛만|비었|없습니다/.test(e.message)) throw e; }
      continue;
    }
    const p = s.active;
    if (s.phase === 'main') {
      { const Q = s.players[p]; if (!Q.energySet && Q.hand.length && Math.random() < .85) act({ type: 'SET_ENERGY', uid: pick(Q.hand).uid }); }
      for (let k = 0; k < 6 && !s.pending && s.winner == null && s.active === p && s.phase === 'main'; k++) {
        const Q = s.players[p];
        const altOf = c => Engine.altsOf(s, p, DEFS[c.id]).findIndex(a => Engine.altOk(s, p, DEFS[c.id], a));
        const playable = Q.hand.filter(c => Engine.playAllowed(s, p, DEFS[c.id]) && (Engine.canPay(Q, DEFS[c.id]) || altOf(c) >= 0));
        if (!playable.length) break;
        const c = pick(playable), d = DEFS[c.id], need = Engine.needsTarget(d), ts = Engine.targetsFor(s, p, d);
        if (need && !ts.length) continue;
        const ai = altOf(c), useAlt = ai >= 0 && (!Engine.canPay(Q, d) || Math.random() < .5);
        if (useAlt) ev('altPlay');
        act({ type: 'PLAY', uid: c.uid, target: ts.length ? pick(ts) : undefined, ...(useAlt ? { alt: ai } : {}) });
      }
      { const sp = s.active === p ? Engine.setPlayable(s, p, 'myMain') : []; if (sp.length && !s.pending && s.winner == null && s.phase === 'main' && Math.random() < .7) { act({ type: 'PLAY_SET', uid: pick(sp) }); ev('setMain'); } }
      if (!s.pending && s.winner == null && s.phase === 'main' && s.active === p) act({ type: 'NEXT_PHASE' });
    } else if (s.phase === 'attack') {
      const ready = Engine.unitsOf(s, p).filter(u => Engine.canAttack(s, u));
      const must = Engine.mustAttack(s);
      if (must.length) {
        // 버서크 상태로 턴 종료 시도는 막혀야 함
        try { Engine.apply(s, { type: 'NEXT_PHASE' }); throw new Error('버서크 무시가 통과됨'); } catch (e) { if (e.message.includes('통과')) throw e; ev('berserkBlocked'); }
        const u = must[0]; act({ type: 'ATTACK', attacker: u.uid, target: pick(Engine.attackTargets(s, p, u.uid)) });
      } else if (ready.length && Math.random() < .85) {
        const u = pick(ready); act({ type: 'ATTACK', attacker: u.uid, target: pick(Engine.attackTargets(s, p, u.uid)) });
      } else act({ type: 'NEXT_PHASE' });
    } else throw new Error('멈춘 상태: ' + s.phase);
  }
  for (const l of s.log) {
    if (l.m.includes('개방!')) ev('terrOpened');
    if (l.m.startsWith('브라이트!')) ev('brightDone');
    if (l.m.startsWith('버스트')) ev('burst');
    if (l.m.includes('블리츠')) ev('blitz');
    if (l.m.includes('레드 존')) ev('redzoneLog');
    if (l.m.startsWith('[드롭 시]')) ev('dropTrigger');
    if (l.m.startsWith('[배틀 시]')) ev('battleTrigger');
    if (l.m.includes('남은 데미지가 사라짐')) ev('damageCancelled');
    if (l.m.startsWith('[결속]')) ev('kesso');
    if (l.m.includes('드롭 존에서 패로')) ev('seikaRecovered');
    if (l.m.includes('라이프 맨 앞을 에너지로')) ev('flashbackDone');
    if (l.m.includes('효과로 드롭')) ev('destroyLE');
    if (l.m.includes('상대 턴이라')) ev('standOnOppTurn');
    if (/파워 -5000, 히트 -2/.test(l.m)) ev('debuff');
    if (l.m.startsWith('(처리하지 못한')) ev(l.m);
  }
  st.games++; st.turns += s.turnCount; st.wins[s.winner]++;
}
st.avgTurns = (st.turns / st.games).toFixed(1);
console.log(JSON.stringify(st, null, 1));

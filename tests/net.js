// 두 기기 온라인 대전 시뮬레이션: 가짜 room 허브로 두 페이지를 연결해 끝까지 플레이하고 상태가 같은지 확인
const { JSDOM } = require('jsdom'); const fs = require('fs');
const html = fs.readFileSync((process.argv[2] || require('path').join(__dirname, '../simulator/index.html')), 'utf8');
const DROP = +(process.argv[3] || 0);   // 메시지 유실률 (재전송 복구 시험)

// ── 가짜 room 허브 (플랫폼 API 모양: join → emit/on/presence/onPeers/connected/onConnection/leave) ──
const rooms = {}; let peerSeq = 0;
function makeClaude(tag) {
  const peer = 'p' + (++peerSeq);
  const lobby = {
    async join(name) {
      const R = rooms[name] ||= { members: [] };
      const me = { peer, presence: {}, handlers: {}, peerFns: [], updatedAt: Date.now() };
      R.members.push(me);
      const snapshot = viewer => R.members.map(m => Object.freeze({ peer: m.peer, by: null, isMe: m === viewer, sameTab: m === viewer, kind: 'viewer', guest: false, presence: m.presence, updatedAt: m.updatedAt }));
      const notify = (joined) => R.members.forEach(m => m.peerFns.forEach(fn => setTimeout(() => fn({ peers: snapshot(m), joined: joined ? snapshot(m).filter(p => p.peer === joined) : [], left: [], updated: [] }), 1)));
      const api = {
        name,
        async emit(topic, data) {
          if (JSON.stringify(data).length > 4096) throw Object.assign(new Error('too big'), { code: 'invalid_argument' });
          R.members.forEach(m => {
            if (m !== me && Math.random() < DROP) return;   // 유실
            (m.handlers[topic] || []).forEach(fn => setTimeout(() => fn({ topic, data: JSON.parse(JSON.stringify(data)), peer, by: null, isMe: m === me, sameTab: m === me, kind: 'viewer', guest: false }), 1 + Math.random() * 5));
          });
        },
        on(topic, fn) { (me.handlers[topic] ||= []).push(fn); return () => {}; },
        async presence(patch) { me.presence = Object.freeze({ ...me.presence, ...patch }); me.updatedAt = Date.now(); notify(null); },
        peers() { return snapshot(me); },
        onPeers(fn) { me.peerFns.push(fn); setTimeout(() => fn({ peers: snapshot(me), joined: snapshot(me), left: [], updated: [] }), 1); return () => {}; },
        connected: () => true,
        onConnection(fn) { setTimeout(() => fn(true), 1); return () => {}; },
        async leave() { R.members = R.members.filter(m => m !== me); notify(null); },
      };
      notify(peer);
      return api;
    },
  };
  return { use: async n => n === 'room' ? lobby : null };
}

function page(tag) {
  const errs = [];
  const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'https://example.test/' + tag, beforeParse(w) { w.structuredClone = structuredClone; w.claude = makeClaude(tag); w.addEventListener('error', e => errs.push(e.message)); } });
  dom.window.eval("deckChoice=['bocchi','bocchi']");
  return { w: dom.window, d: dom.window.document, errs };
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const clk = (pg, sel) => { const el = pg.d.querySelector(sel); if (el) el.dispatchEvent(new pg.w.MouseEvent('click', { bubbles: true })); return !!el; };

(async () => {
  const A = page('host'), B = page('guest');
  await sleep(50);
  clk(A, '[data-b=goPlay]'); clk(B, '[data-b=goPlay]'); clk(A, '[data-b=mode][data-m=online]'); clk(B, '[data-b=mode][data-m=online]');
  clk(A, '[data-b=createRoom]'); await sleep(50);
  const code = A.w.eval('Net.code'); console.log('방 코드:', code);
  B.d.getElementById('roomcode').value = code; clk(B, '[data-b=joinRoom]'); await sleep(80);
  console.log('방장 화면 참가자:', A.d.querySelectorAll('.people li').length, '| 게스트 자리:', B.w.eval('Net.seat'));
  console.log('시작 버튼(준비 전) 비활성:', A.d.querySelector('[data-b=hostStart]').disabled);
  clk(B, '[data-b=ready]'); await sleep(60);
  console.log('시작 버튼(준비 후) 활성:', !A.d.querySelector('[data-b=hostStart]').disabled);
  clk(A, '[data-b=hostStart]'); await sleep(80);
  console.log('양쪽 게임 화면:', A.w.eval('screen'), B.w.eval('screen'), '| gid 같음:', A.w.eval('Net.gid') === B.w.eval('Net.gid'));

  // 각 페이지가 자기 차례일 때만 자기 화면 버튼으로 진행 (엔진 API 대신 실제 dispatch 경로 사용)
  const pick = a => a[Math.floor(Math.random() * a.length)];
  let steps = 0, blocked = 0;
  while (steps++ < 8000) {
    if (!A.w.eval('S') || !B.w.eval('S')) { await sleep(100); continue; }
    if (A.w.eval('S.winner') != null && B.w.eval('S.winner') != null) break;
    let moved = false;
    for (const P of [A, B]) {
      const w = P.w;
      if (!w.eval('S')) continue;
      if (!w.eval('myControl()') || w.eval('S.winner') != null) {
        // 차례가 아닐 때 조작하면 막혀야 함
        if (w.eval('S.winner') == null && w.eval('S.phase') === 'main' && Math.random() < .02) { w.eval("dispatch({type:'NEXT_PHASE'})"); if (w.eval('toast').includes('상대')) blocked++; }
        continue;
      }
      moved = true;
      const a = w.eval(`(() => {
        const s=S, pd=s.pending, pick=a=>a[Math.floor(Math.random()*a.length)];
        if (pd) { const P=s.players[pd.player];
          if (pd.type==='order') return {type:'ORDER',i:Math.floor(Math.random()*pd.items.length)};
          if (pd.type==='mulligan') return {type:'MULLIGAN',redraw:Math.random()<.3};
          if (pd.type==='block') { const bl=s.field.filter(u=>u.owner===pd.player&&!u.rested&&u.uid!==pd.target); return {type:'BLOCK',blocker:Math.random()<.5&&bl.length?pick(bl).uid:null}; }
          if (pd.type==='shot') { const ts=Engine.targetsFor(s,pd.player,DEFS[pd.card.id]); return {type:'SHOT',play:true,target:ts.length?pick(ts):undefined}; }
          if (pd.type==='discard') return {type:'DISCARD',uid:pick(P.hand).uid};
          if (pd.type==='territory') return {type:'TERRITORY',open:P.energy.filter(e=>!e.rested).length>=pd.cost};
          if (pd.type==='bright') { const b=DEFS[Engine.findUnit(s,pd.uid).id].bright; const ok=P.hand.filter(c=>DEFS[c.id].attr.some(a=>b.attrs.includes(a))); return {type:'BRIGHT',discard:ok.length?pick(ok).uid:null}; }
          if (pd.type==='scout') { const ids=P.deck.slice(0,pd.n).map(c=>c.uid); return {type:'SCOUT',top:ids,bottom:[]}; }
          if (pd.type==='seika') return pd.step==='discard'?{type:'SEIKA',uid:null}:{type:'SEIKA',uid:Engine.seikaTargets(s,pd.player)[0]};
          if (pd.type==='flashback') return {type:'FLASHBACK',uid:pick(Engine.flashTargets(s,pd.player))};
        }
        const p=s.active, P=s.players[p];
        if (s.phase==='main') {
          if (!P.energySet && P.hand.length && Math.random()<.8) return {type:'SET_ENERGY',uid:pick(P.hand).uid};
          const pl=P.hand.filter(c=>Engine.canPay(P,DEFS[c.id])&&Engine.playAllowed(s,p,DEFS[c.id]));
          const c=pl.length&&Math.random()<.7?pick(pl):null;
          if (c) { const d=DEFS[c.id], ts=Engine.targetsFor(s,p,d); if (!Engine.needsTarget(d)) return {type:'PLAY',uid:c.uid}; if (ts.length) return {type:'PLAY',uid:c.uid,target:pick(ts)}; }
          return {type:'NEXT_PHASE'};
        }
        if (s.phase==='attack') { const r=Engine.unitsOf(s,p).filter(u=>Engine.canAttack(s,u)); const m=Engine.mustAttack(s);
          const u=m[0]||(r.length&&Math.random()<.85?pick(r):null);
          if (u) return {type:'ATTACK',attacker:u.uid,target:pick(Engine.attackTargets(s,p,u.uid))};
          return {type:'NEXT_PHASE'}; }
        return null; })()`);
      if (a) w.eval(`dispatch(${JSON.stringify(a)})`);
      break;
    }
    await sleep(moved ? 12 : 30);
  }
  await sleep(DROP ? 12000 : 200);
  const sa = JSON.stringify(A.w.eval('S')), sb = JSON.stringify(B.w.eval('S'));
  console.log('끝:', A.w.eval('S.winner') != null ? `P${A.w.eval('S.winner') + 1} 승리, ${A.w.eval('S.turnCount')}턴` : '미종료',
    '| 행동 수', A.w.eval('Net.acts.length'), B.w.eval('Net.acts.length'),
    '| 두 기기 상태 일치:', sa === sb, '| 차례 아닌 조작 차단:', blocked);
  console.log('게스트 화면 아래쪽 매트 = 내 자리(P2):', (B.d.querySelector('.hand.me') ? true : false));
  console.log('오류:', A.errs, B.errs, '| 상태 메시지:', A.w.eval('Net.status') || '-', '/', B.w.eval('Net.status') || '-');
  process.exit(0);
})();

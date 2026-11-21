const {JSDOM}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync(process.argv[2],'utf8');const errs=[];
const dom=new JSDOM(html,{runScripts:'dangerously',beforeParse(w){w.structuredClone=structuredClone;w.addEventListener('error',e=>errs.push(e.message));}});
const w=dom.window,d=w.document;
const clk=el=>el&&el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
const q=s=>d.querySelector(s), txt=()=>q('.prompt')?.textContent.replace(/\s+/g,' ').trim();
console.log('로비:', q('.lobby h1')?.textContent, '| 덱 목록', d.querySelectorAll('.decklist li').length, '줄');
dom.window.eval("deckChoice=[deckChoice[0]||'bocchi',deckChoice[1]||'bocchi'];render()");clk(q('[data-b=startLocal]'));
clk(q('[data-b=keep]'));clk(q('[data-b=keep]'));
console.log('1:',q('.top').textContent.replace(/\s+/g,' ').slice(0,60),'|',q('.ps.me .terr').textContent);
// 몇 턴 진행: 에너지 놓고, 플레이할 수 있는 것 플레이, 공격, 턴 종료
console.log('덱:', [...d.querySelectorAll('select')].map(x=>x.value).join(' vs '));
for(let t=0;t<14;t++){
  let guard=0;
  while(w.eval('S.pending') && guard++<20){ // 선택 처리
    const ty=w.eval('S.pending.type');
    if(ty==='territory') clk(q('[data-b=terrYes]:not([disabled])')||q('[data-b=terrNo]'));
    else if(ty==='bright') clk(q('.ps.me [data-z=hand].tg')||q('[data-b=brightNo]'));
    else if(ty==='scout') clk(q('[data-b=scOk]'));
    else if(ty==='block') clk(q('[data-b=noBlock]'));
    else if(ty==='shot') { clk(q('[data-b=shotYes]')); const tg=q('.card.tg'); if(tg) clk(tg); }
    else if(ty==='discard') clk(q('.ps.me [data-z=hand]'));
    else if(ty==='seika') clk(q('.card.tg[data-z=pick]')||q('.ps.me [data-z=hand]'));
    else if(ty==='flashback') clk(q('.card.tg[data-z=pick]')||q('[data-b=flashNo]'));
    console.log('  선택:',ty,'→',w.eval('S.log.slice(-1)[0].m'));
  }
  if(w.eval('S.winner')!=null) break;
  if(w.eval('S.phase')==='main'){
    clk(q('.ps.me [data-z=hand]')); clk(q('[data-b=energy]'));
    for(const c of [...d.querySelectorAll('.ps.me [data-z=hand]')]){ const el=q(`.ps.me [data-u="${c.dataset.u}"]`); if(!el) continue; clk(el); const b=q('[data-b=play]'); if(b&&!b.disabled){clk(b); const tg=q('.card.tg'); if(tg) clk(tg); else if(q('[data-b=cancel]')&&txt().includes('대상')) clk(q('[data-b=cancel]'));} else clk(q('[data-b=cancel]')); if(w.eval('S.pending')) break; }
    if(w.eval('S.pending')) continue;
    clk(q('[data-b=next]'));
  }
  if(w.eval('S.phase')==='attack'){
    const u=q('.ps.me .card.can[data-z=field]');
    if(u){ clk(u); if(q('[data-b=atkPlayer]')) clk(q('[data-b=atkPlayer]')); else clk(q('.card.tg')); }
    if(!w.eval('S.pending')) clk(q('[data-b=next]'));
  }
  console.log(`턴${t}:`, q('.top').textContent.replace(/\s+/g,' ').slice(0,60), '| 토스트:', q('.toast')?.textContent||'-');
}
console.log('로그 끝:', w.eval('S.log.slice(-6).map(l=>l.m).join(" / ")'));
console.log('errors:',errs);
// 목록 창 테스트
clk(q('.ps.me [data-zone=drop]')); console.log('드롭 존 창:', q('.sheet h2')?.textContent, '|', q('.sheet .sub')?.textContent, '| 카드', d.querySelectorAll('.sheet .card').length);
clk(q('[data-b=viewMode][data-m=group]')); console.log('묶기:', [...d.querySelectorAll('.sheet .grp .x')].map(x=>x.textContent).join(' '));
clk(q('.sheet header h2')); console.log('창 안 클릭 후 열림?', !!q('.sheet'));
clk(q('.modal')); console.log('배경 클릭 후 열림?', !!q('.sheet'));
clk(q('.ps.them [data-zone=energy]')); console.log('상대 에너지 창:', q('.sheet h2')?.textContent, '|', q('.sheet .sub')?.textContent);
d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true})); console.log('Esc 후 열림?', !!q('.sheet'));
console.log('errors:',errs);

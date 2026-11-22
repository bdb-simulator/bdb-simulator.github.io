// 공격 중 연출 순서가 룰 처리 순서와 같은지 확인 (공격 → 공격 시 능력 → 블록 → 배틀 시 능력 → 배틀 → 데미지 / 라이프 공개 → 라이프 데미지 후 능력)
const {Engine,DEFS,U,C,base,auto}=require('./h.js');
const ev=s=>(s.fx||[]).map(e=>e.k+(e.k==='trig'?'('+(DEFS[e.id]?.name||'').slice(0,6)+')':e.k==='life'?'('+e.kind+')':''));
const find=pred=>Object.keys(DEFS).find(k=>DEFS[k].type==='unit'&&(DEFS[k].ab||[]).some(pred));
const atkU=find(a=>a.k==='auto'&&a.on==='attack'&&a.src==='self'&&!(a.if||[]).length&&a.do.some(x=>x.op==='draw'));
const batU=find(a=>a.k==='auto'&&a.on==='battle'&&a.src==='self'&&!(a.if||[]).length);
const lifeU=find(a=>a.k==='auto'&&a.on==='lifeDmgDrop');
const buster=Object.keys(DEFS).find(k=>DEFS[k].icon==='buster'&&DEFS[k].type==='unit'), plain=Object.keys(DEFS).find(k=>!DEFS[k].icon&&DEFS[k].type==='unit');
let ok=true; const check=(name,seq,order)=>{ let i=-1; const good=order.every(t=>{ const j=seq.findIndex((x,k)=>k>i&&x.startsWith(t)); if(j<0) return false; i=j; return true; }); ok&&=good; console.log(good?'OK ':'NG ',name,seq.join(' > ')); };
{ // 1) 플레이어 공격: 공격 시 능력 → 라이프 공개(버스터 포함) 순서
  let s=base(); const p=s.active, o=1-p; s.phase='attack'; s.fx=[];
  s.field.push(U(atkU,p,{uid:'A'})); s.players[o].life=[C(buster),C(plain),C(plain),C(plain),C(plain)];
  s=Engine.apply(s,{type:'ATTACK',attacker:'A',target:'player'}); s=auto(s);
  const q=ev(s); check('플레이어 공격 '+DEFS[atkU].name,q,['atk','trig','life(buster)','life']);
  ok&&=!q.includes('battle'); }
{ // 2) 유닛 공격 + 블록: 배틀 시 능력이 끝난 뒤 배틀 연출
  let s=base(); const p=s.active, o=1-p; s.phase='attack'; s.fx=[];
  s.field.push(U(batU,p,{uid:'A'}),U(plain,o,{uid:'T',rested:true}),U(plain,o,{uid:'B'}));
  s=Engine.apply(s,{type:'ATTACK',attacker:'A',target:'T'}); s=auto(s,[{type:'BLOCK',blocker:'B'}]);
  const q=ev(s); check('배틀 '+DEFS[batU].name,q,['atk','blk','trig','battle','dmg']);
  const bi=q.indexOf('battle'); ok&&=!q.slice(0,bi).filter(x=>x==='battle').length; }
{ // 3) 라이프 데미지 후 능력은 해당 라이프 공개 뒤
  let s=base(); const p=s.active, o=1-p; s.phase='attack'; s.fx=[];
  s.field.push(U(plain,p,{uid:'A'})); s.players[o].life=[C(lifeU),C(plain)];
  s=Engine.apply(s,{type:'ATTACK',attacker:'A',target:'player'}); s=auto(s);
  check('라이프 데미지 후 능력 '+DEFS[lifeU].name,ev(s),['atk','life','trig']); }
console.log(ok?'ALL OK':'FAIL'); process.exit(ok?0:1);

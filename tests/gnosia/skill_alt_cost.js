const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
const tc=(name,f)=>{ try{ console.log(name, JSON.stringify(f()).slice(0,500)); }catch(e){ console.log(name,'ERR',e.message); } };
function setup(id){ let s=base('7246'); const p=s.active; const P=s.players[p]; P.hand=[{uid:'CMD',id:'7312'},{uid:'H1',id:'7297'}]; P.energy=Array.from({length:6},(_,i)=>({uid:'ze'+i,id:'7297',rested:false})); s.field.push(U(id,p,{uid:'A'}),U('7150',1-p,{uid:'E1'})); s.phase='attack'; return s; }
// 3779 予言の子: 12번 반복, 원래 코스트는 다이아 에너지 레스트
tc('3779 반복 스킬', ()=>{ let s=setup('3779'); const p=s.active; s=run(s,p,'3779',0,{src:'A'}); const seq=[];
  for(let i=0;i<6&&s.pending;i++){ const pd=s.pending; seq.push(pd.kind+(pd.labels?':'+pd.labels.join('/'):'')+(pd.dis?' dis'+JSON.stringify(pd.dis):''));
    if(pd.kind==='pick'&&pd.text?.includes('대상')) s=Engine.apply(s,{type:'FX',uids:['E1']}); else if(pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice: seq.length===2?1:2}); else s=auto(s); }
  return {seq, cmdInHand:s.players[p].hand.some(c=>c.uid==='CMD'), log:L(s).slice(-5)}; });
// 7297 일반 a.cost
tc('7297 일반 스킬', ()=>{ let s=setup('7297'); const p=s.active; s=run(s,p,'7297',0,{src:'A'}); const pd=s.pending; return {kind:pd?.kind, labels:pd?.labels}; });
// 스킬이 아닌 비용에는 안 묻기: 6192 クルミ (덱 아래에 놓는 비용)
tc('비스킬 비용', ()=>{ let s=setup('6192'); const p=s.active; s.field.find(u=>u.uid==='A').rested=true; s=run(s,p,'6192',0,{src:'A'}); return {kind:s.pending?.kind, text:s.pending?.text}; });

const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
const tc=(name,f)=>{ try{ console.log(name, JSON.stringify(f()).slice(0,420)); }catch(e){ console.log(name,'ERR',e.message); } };
const pend=s=>s.pending&&(s.pending.type+'/'+(s.pending.kind||''));
tc('7147', ()=>{ let s=base('7051'); const p=s.active,o=1-p; const P=s.players[p]; P.drop=[C('7174'),C('7174'),{uid:'DC',id:'7202'}]; s.field.push(U('7147',p,{uid:'S'}),U('7150',o,{uid:'E1'}));
  s=run(s,p,'7147',0,{src:'S'}); const c0=s.pending?.cands; s=Engine.apply(s,{type:'FX',uids:['DC']}); s=auto(s,[{type:'FX',uids:['E1']}]); return {cands:c0, remove:(s.players[p].remove||[]).map(c=>c.id), drop:s.players[p].drop.map(c=>c.id), hand:s.players[p].hand.length, oppHand:s.players[o].hand.map(c=>c.id).slice(-1), log:L(s).slice(-5)}; });
tc('7156 대상 후보', ()=>{ let s=base('7059'); const p=s.active,o=1-p; s.players[o].territory.open=true; s.field.push(U('7156',o,{uid:'ST',rested:true}),U('7153',o,{uid:'SE'}),U('7150',o,{uid:'X'}));
  s.active=p; s=run(s,p,'7170',0); return {cands:s.pending?.cands}; });
tc('7156 상대 턴이 아니면(내 턴 기준 상대가 스텔라 주인)…', ()=>{ return 'turn owner p uses cmd → it is opp turn for ST owner'; });
tc('7171', ()=>{ let s=base(); const p=s.active,o=1-p; const t0=s.players[o].life[0].id; s=run(s,p,'7171',0); const seq=[];
  for(let i=0;i<6&&s.pending;i++){ const pd=s.pending; seq.push(pd.type+'/'+(pd.kind||'')); if(pd.type==='scout') s=Engine.apply(s,{type:'SCOUT',top:s.players[p].deck.slice(0,pd.n).map(c=>c.uid),bottom:[]}); else if(pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice:1}); else s=auto(s); }
  return {seq, oppTopBefore:t0, oppTop:s.players[o].life[0].id, oppDropTop:s.players[o].drop.slice(-1)[0]?.id, log:L(s).slice(-4)}; });
tc('7205 레스트 등장/스탠드 안 함', ()=>{ let s=base(); const p=s.active; s.pending={type:'order',player:p,items:[{t:'ab',p,src:'x',id:'7150',ai:-1,ctx:{p,T:[]},steps:[{op:'pick',from:'hand',to:'field',f:{type:'unit'},n:1,upto:0}],i:0}]};
  s.players[p].hand=[{uid:'K',id:'7205'}]; s=Engine.apply(s,{type:'ORDER',i:0}); s=auto(s); return {rested:s.field.find(u=>u.uid==='K')?.rested}; });
tc('7227 라이프로', ()=>{ let s=base(); const p=s.active; const P=s.players[p]; const l0=P.life.length; s=run(s,p,'7227',0,{src:'zzMC'}); s=auto(s); return {dLife:s.players[p].life.length-l0, log:L(s).slice(-3)}; });

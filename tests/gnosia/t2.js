const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
function dropOwn(s,p,uids){ s.pending={type:'order',player:p,items:[{t:'ab',p,src:uids[0],id:'7150',ai:-1,ctx:{p,src:uids[0],T:[]},steps:[{op:'drop',to:{all:{side:'own',type:'unit'}}}],i:0}]}; return Engine.apply(s,{type:'ORDER',i:0}); }
function step(s,choice){ const seq=[]; for(let i=0;i<10&&s.pending;i++){ const pd=s.pending; seq.push(pd.type+'/'+(pd.kind||'')+(pd.text?':'+pd.text.slice(0,20):''));
  if(pd.type==='order'){ s=Engine.apply(s,{type:'ORDER',i:0}); continue; }
  if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes:true}); else if(pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice}); else s=Engine.apply(s,{type:'FX',uids:pd.cands.slice(0,1)}); } return [s,seq]; }
for (const ch of [0,1]) { let s=base('7057'); const p=s.active; s.field.push(U('7150',p,{uid:'X'})); s.players[p].hand=[];
  s=dropOwn(s,p,['X']); let seq; [s,seq]=step(s,ch);
  console.log('A choice',ch, seq, 'field',s.field.map(x=>x.id+(x.rested?'(R)':'')),'hand',s.players[p].hand.map(c=>c.id),'terr',s.players[p].territory.open, L(s).slice(-3)); }
{ let s=base('7057'); const p=s.active; s.field.push(U('7150',p,{uid:'X'}),U('7186',p,{uid:'Y'})); s.players[p].hand=[];
  s=dropOwn(s,p,['X']); let seq; [s,seq]=step(s,1);
  console.log('A double', seq, 'field',s.field.map(x=>x.id),'terr',s.players[p].territory.open, L(s).slice(-4)); }
{ let s=base(); const p=s.active; const P=s.players[p]; const rb=Object.keys(DEFS).find(k=>DEFS[k].color==='red'&&DEFS[k].icon==='buster'&&DEFS[k].type==='unit'&&DEFS[k].cb!=null);
  const sp=Object.keys(DEFS).filter(k=>(DEFS[k].attr||[]).includes('スペード')&&DEFS[k].cb!=null).slice(0,5);
  P.drop=sp.map(k=>C(k)); P.energy=[{uid:'RB',id:rb,rested:false}]; s.field.push(U('7216',p,{uid:'M'}));
  s=dropOwn(s,p,['M']); let seq; [s,seq]=step(s,0); console.log('F manan',seq,s.field.map(x=>x.id+(x.rested?'(R)':'')),L(s).slice(-3)); }
// 7055 vs 테리토리 닫힘: 닫혀 있으면 발동 안 해야
{ let s=base('7057'); const p=s.active; s.players[p].territory.open=false; s.field.push(U('7150',p,{uid:'X'}));
  s=dropOwn(s,p,['X']); let seq; [s,seq]=step(s,0); console.log('A closed', seq, L(s).slice(-2)); }

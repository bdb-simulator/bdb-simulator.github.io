const {Engine,DEFS,U,C,base,run,auto,L}=require('/tmp/gn/h.js');
const tc=(name,f)=>{ try{ console.log(name, JSON.stringify(f()).slice(0,600)); }catch(e){ console.log(name,'ERR',e.message); } };
function setup(terr,id){ let s=base(terr); const p=s.active; const P=s.players[p]; const dia=Object.keys(DEFS).find(k=>(DEFS[k].attr||[]).includes('ダイヤ')&&DEFS[k].type==='unit');
  P.hand=[{uid:'H1',id:dia}]; P.energy=Array.from({length:4},(_,i)=>({uid:'ze'+i,id:dia,rested:false})); s.field.push(U(id,p,{uid:'A'}),U('7150',1-p,{uid:'E1'}),U('7150',1-p,{uid:'E2'})); s.phase='attack'; return s; }
tc('3723 브리튼: 반복 스킬도 스킬 발동 시 트리거', ()=>{ let s=setup('3723','3779'); const p=s.active; s=run(s,p,'3779',0,{src:'A'}); const seq=[];
  for(let i=0;i<10&&s.pending;i++){ const pd=s.pending; seq.push(pd.type+'/'+(pd.kind||'')+':'+(pd.text||'').slice(0,18));
    if(pd.type==='order') s=Engine.apply(s,{type:'ORDER',i:0}); else if(pd.kind==='pick') s=Engine.apply(s,{type:'FX',uids:pd.cands.slice(0,1)}); else if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes: seq.filter(x=>x.includes('confirm')).length<2}); else s=auto(s); }
  return {seq, log:L(s).filter(m=>m.includes('브리튼')||m.includes('理想')||m.includes('8000')||m.includes('3000'))}; });
tc('千子村正 무료 스킬: 반복 스킬 첫 회 무료', ()=>{ let s=setup('7246','3779'); const p=s.active; s.turn.flags={freeSkill:p+1}; s.players[p].hand=[]; const r0=s.players[p].energy.filter(e=>e.rested).length;
  s=run(s,p,'3779',0,{src:'A'}); for(let i=0;i<6&&s.pending;i++){ const pd=s.pending; if(pd.kind==='pick') s=Engine.apply(s,{type:'FX',uids:['E1']}); else if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes:i<2}); else s=auto(s); }
  return {rested:s.players[p].energy.filter(e=>e.rested).length-r0, log:L(s).slice(-5)}; });
tc('비스킬 비용 드롭은 skillDrop 아님 (6156 미즈키)', ()=>{ let s=base(); const p=s.active; s.players[p].hand=[{uid:'KP',id:'5444'}]; s.field.push(U('6156',p,{uid:'M'}));
  s.pending={type:'order',player:p,items:[{t:'ab',p,src:'M',id:'7150',ai:-1,ctx:{p,T:[]},steps:[{op:'drop',to:{all:{side:'own',type:'unit'}}}],i:0}]};
  s=Engine.apply(s,{type:'ORDER',i:0}); const h0=s.players[p].hand.length; s=auto(s); return {log:L(s).slice(-4)}; });

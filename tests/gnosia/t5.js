const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
const tc=(name,f)=>{ try{ console.log(name, JSON.stringify(f()).slice(0,420)); }catch(e){ console.log(name,'ERR',e.message); } };
console.log('7174 color', DEFS['7174'].color, '7227', DEFS['7227'].color, DEFS['7227'].cost);
tc('7156', ()=>{ let s=base('7059'); const p=s.active,o=1-p; s.players[o].territory.open=true; s.field.push(U('7156',o,{uid:'ST',rested:true}),U('7153',o,{uid:'SE'}),U('7150',o,{uid:'X'}));
  s=run(s,p,'7170',0); return {pend:s.pending?.cands, log:L(s).slice(-3)}; });
tc('7227 실제 플레이', ()=>{ let s=base(); const p=s.active; s.phase='main'; const P=s.players[p]; const col=Object.keys(DEFS).find(k=>DEFS[k].color===DEFS['7227'].color&&DEFS[k].type==='unit');
  P.hand=[{uid:'MC',id:'7227'}]; P.energy=Array.from({length:5},(_,i)=>({uid:'ze'+i,id:col,rested:false})); const l0=P.life.length;
  s=Engine.apply(s,{type:'PLAY',uid:'MC'}); s=auto(s); return {terr:s.players[p].territory.open, dLife:s.players[p].life.length-l0, lifeTop:s.players[p].life[0].id, delayed:(s.delayed||[]).length, log:L(s).slice(-3)}; });

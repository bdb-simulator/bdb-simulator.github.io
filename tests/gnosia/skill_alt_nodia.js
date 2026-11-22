const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
let s=base('7246'); const p=s.active, P=s.players[p];
P.hand=[{uid:'CMD',id:'7312'},{uid:'CMD2',id:'7312'}];
const red=Object.keys(DEFS).find(k=>DEFS[k].type==='unit'&&!(DEFS[k].attr||[]).includes('ダイヤ')&&DEFS[k].icons);
P.energy=Array.from({length:4},(_,i)=>({uid:'ze'+i,id:red,rested:false}));
s.field.push(U('3779',p,{uid:'A'}),U(red,1-p,{uid:'E1',rested:true}),U(red,1-p,{uid:'E2',rested:true}));
s.phase='attack'; s.fx=[];
s=Engine.apply(s,{type:'ATTACK',attacker:'A',target:'player'});
const seq=[]; for(let i=0;i<10&&s.pending;i++){ const pd=s.pending; seq.push(pd.type+'/'+(pd.kind||'')+':'+(pd.text||'').slice(0,30)+(pd.labels?' ['+pd.labels.join('/')+']':'')+(pd.dis?' dis'+JSON.stringify(pd.dis):''));
 if(pd.type==='fx'&&pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice:1}); else if(pd.type==='fx'&&pd.kind==='pick') s=Engine.apply(s,{type:'FX',uids:pd.cands.includes('E1')?['E1']:pd.cands.slice(0,pd.n||1)}); else if(pd.type==='block') s=Engine.apply(s,{type:'BLOCK',blocker:null}); else if(pd.type==='order') s=Engine.apply(s,{type:'ORDER',i:0}); else if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes:true}); else break; }
console.log(seq.join('\n')); console.log(s.log.slice(-12).map(l=>l.m).join('\n'));

const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const html=fs.readFileSync(H,'utf8');const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
const {Engine,DEFS,DECKS}=ctx;const DB=JSON.parse(fs.readFileSync(H.replace('index.html','cards_db.json'),'utf8'));
for (const [k,d] of Object.entries(DB.defs)) if(!DEFS[k]) DEFS[k]=Object.assign({id:k,icon:null,attr:[],icons:[],titles:[]},d);
const ci=DB.collabs.indexOf('Fate/Grand Order');
const names=new Set(); let list=[];
for (const [k,d] of Object.entries(DB.defs)) { if(d.cb!==ci||names.has(d.name)) continue; if((d.ab||[]).some(a=>a.k==='auto'&&a.on==='attack')) {names.add(d.name);list.push(k);} }
list=(process.argv[2]||'').split(',').filter(Boolean).length?process.argv[2].split(','):list;
const terrs=Object.keys(DB.defs).filter(k=>DB.defs[k].type==='territory'&&DB.defs[k].cb===ci);
const ok=[],bad=[];
for (const k of list) {
  const d=DEFS[k], a=d.ab.find(a=>a.k==='auto'&&a.on==='attack'); a.cost=a.cost||[];
  // 조건에 맞는 테리토리
  const need=(a.if||[]).map(c=>c.terrTitle||(c.terrTitleAny||[])[0]).find(Boolean);
  const T=terrs.find(t=>need?(DEFS[t].titles||[]).includes(need):(DEFS[t].titles||[]).some(x=>(d.titles||[]).includes(x)))||terrs[0];
  const deck={label:'t',territory:T,main:DECKS.wGZEVOA7X.main};
  let s=Engine.newGame(deck,deck,1); s=Engine.apply(s,{type:'MULLIGAN',redraw:false}); s=Engine.apply(s,{type:'MULLIGAN',redraw:false}); 
  s.pending=null; s.phase='attack'; s.turnCount=3; const p=s.active,o=1-p,P=s.players[p];
  P.territory.open=true;
  s.field=[{uid:'A',id:k,owner:p,rested:false,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]},{uid:'B',id:P.deck[0].id,owner:o,rested:true,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]}];
  // 패: 모든 속성·커맨드 섞어서
  const pool=Object.keys(DB.defs).filter(x=>DB.defs[x].cb===ci&&DB.defs[x].type!=='territory');
  const pickF=(f)=>pool.find(x=>{const dd=DEFS[x]; if(f?.attr&&!(dd.attr||[]).some(t=>f.attr.includes(t)))return false; if(f?.type&&dd.type!==f.type)return false; if(f?.color&&!(Array.isArray(f.color)?f.color.includes(dd.color):f.color===dd.color))return false; return true;});
  const costF=a.cost.map(c=>c.f||{});
  P.hand=[];for(const f of costF){for(let i=0;i<3;i++)P.hand.push({uid:'h'+P.hand.length,id:pickF(f)||pool[0]});}
  for(let i=0;i<3;i++)P.hand.push({uid:'h'+P.hand.length,id:pool[i]});
  const cols=['red','blue','white','black']; P.energy=Array.from({length:12},(_,i)=>({uid:'e'+i,id:pool.find(x=>DEFS[x].color===cols[i%4]&&DEFS[x].type==='unit')||pool[0],rested:false}));
  s.field[0].att=[{uid:'cl1',id:'CLASS'},{uid:'cl2',id:'CLASS'}]; P.drop.push(...Array.from({length:7},(_,i)=>({uid:'dc'+i,id:'CLASS'}))); P.drop.push(...pool.filter(x=>(DEFS[x].text||[]).some(t=>t.includes('【スキル】'))).slice(0,6).map((x,i)=>({uid:'ds'+i,id:x}))); s.conts=[];s.queue=[];
  const h0=P.hand.length; let steps=[],err=null;
  try{ s=Engine.apply(s,{type:'ATTACK',attacker:'A',target:'B'});
    for(let i=0;i<20&&s.pending&&s.winner==null;i++){const pd=s.pending; steps.push(pd.type+':'+(pd.kind||''));
      if(pd.type==='block') s=Engine.apply(s,{type:'BLOCK',blocker:null});
      else if(pd.type==='order') s=Engine.apply(s,{type:'ORDER',i:0});
      else if(pd.type==='fx'){ if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes:true}); else if(pd.cands) s=Engine.apply(s,{type:'FX',uids:pd.cands.slice(0,Math.max(pd.min??0,pd.n||1))}); else if(pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice:0}); else break; }
      else if(pd.type==='shot') s=Engine.apply(s,{type:'SHOT',play:false});
      else break; }
  }catch(e){err=e.message}
  const lg=s.log.map(l=>l.m); const fired=lg.some(m=>m.includes('[자동] '+d.name)); const nofire=lg.find(m=>m.includes('발동하지 않음')||m.includes('비용을 낼 수 없'));
  const paid=s.players[p].hand.length<h0||s.players[p].energy.some(e=>e.rested||e.down);
  (fired&&paid&&!err?ok:bad).push({k,name:d.name,need,T:DEFS[T].name,fired,paid,nofire,err,steps:steps.join(','),cost:JSON.stringify(a.cost),tail:lg.slice(-4)});
}
console.log('ok',ok.length,'bad',bad.length);
for(const b of bad) console.log(JSON.stringify(b).slice(0,600));

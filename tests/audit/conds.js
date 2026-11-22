// 모든 카드 능력을 풍부한 상태에서 직접 실행해 보고 이상한 것을 찾는 점검 도구
const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const html=fs.readFileSync(H,'utf8');const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code.replace('function condOk(','ctx.condOk=condOk;function condOk(')+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
const {Engine,DEFS,DECKS}=ctx;const DB=JSON.parse(fs.readFileSync(H.replace('index.html','cards_db.json'),'utf8'));
for (const [k,d] of Object.entries(DB.defs)) if(!DEFS[k]) DEFS[k]=Object.assign({id:k,icon:null,attr:[],icons:[],titles:[]},d);
const CB=+process.argv[2]; const ONLY=process.argv[3]?process.argv[3].split(','):null;
let seed=12345; const rnd=()=>{seed=(seed*1103515245+12345)&0x7fffffff;return seed/0x7fffffff;}; const pick=a=>a[Math.floor(rnd()*a.length)];
const base=Object.keys(DB.defs).filter(k=>DB.defs[k].cb===CB);
const units=base.filter(k=>DEFS[k].type==='unit'), cmds=base.filter(k=>DEFS[k].type==='command'), terrs=base.filter(k=>DEFS[k].type==='territory');
const allUnits=Object.keys(DB.defs).filter(k=>DEFS[k].type==='unit');
let n=0; const uid=()=>'q'+(++n);
const deck={label:'cb',territory:terrs[0]||'BQT',main:[...new Set(base.filter(k=>DEFS[k].type!=='territory'))].slice(0,40).map(k=>[k,1])}; while(deck.main.reduce((t,[,n])=>t+n,0)<40) deck.main.push([pick(units.length?units:allUnits),1]);
function state(src, a, v){
  let s=Engine.newGame(deck,deck,7); s.size=[999,999]; s=Engine.apply(s,{type:'MULLIGAN',redraw:false}); s=Engine.apply(s,{type:'MULLIGAN',redraw:false});
  const p=s.active,o=1-p,P=s.players[p],O=s.players[o];
  s.turnCount=4; s.phase=a.on==='attack'||a.on==='battle'||a.on==='win'||a.on==='attackStart'||a.on==='attackEnd'?'attack':'main';
  const d=DEFS[src];
  const needT=(a.if||[]).map(c=>c.terrTitle||(c.terrTitleAny||[])[0]).find(Boolean);
  const T=terrs.find(t=>needT?(DEFS[t].titles||[]).includes(needT):(DEFS[t].titles||[]).some(x=>(d.titles||[]).includes(x)))||terrs[0]||P.territory.id;
  P.territory={id:T,open:true}; O.territory.open=true;
  const mk=(id,owner,o2={})=>({uid:o2.uid||uid(),id,owner,rested:!!o2.rested,damage:0,tmp:{power:0,hit:0,kw:[]},att:o2.att||[]});
  s.field=[];
  const srcUid='SRC';
  if (d.type==='unit') s.field.push(mk(src,p,{uid:srcUid,att:[{uid:'cl1',id:'CLASS'},{uid:'cl2',id:'CLASS'}]}));
  for(let i=0;i<3;i++) s.field.push(mk(pick(units.length?units:allUnits),p));
  for(let i=0;i<3;i++) s.field.push(mk(pick(units.length?units:allUnits),o,{uid:'OP'+i,rested:i===1}));
  s.field.push(mk(pick(allUnits.filter(k=>DEFS[k].cost<=3)),o,{uid:'OPc'}));
  const C=id=>({uid:uid(),id});
  P.hand=[...Array(4)].map(()=>C(pick(units)))
    .concat([...Array(3)].map(()=>C(pick(cmds.length?cmds:units))));
  P.drop=[...Array(4)].map(()=>C(pick(units))).concat([...Array(7)].map(()=>C(pick(cmds.length?cmds:units)))).concat([{uid:'dcl',id:'CLASS'},{uid:'dcl2',id:'CLASS'},{uid:'dcl3',id:'CLASS'}]);
  O.drop=[...Array(4)].map(()=>C(pick(allUnits)));
  O.hand=[...Array(4)].map(()=>C(pick(allUnits)));
  const cols=['red','blue','white','black'];
  P.energy=[...Array(8)].map((_,i)=>({uid:uid(),id:pick(base.filter(k=>DEFS[k].color===cols[i%4]&&DEFS[k].type!=='territory'))||pick(allUnits),rested:false}));
  O.energy=[...Array(6)].map(()=>({uid:uid(),id:pick(allUnits),rested:false}));
  if (d.type==='command') P.drop.push({uid:srcUid,id:src});
  if (a.fromHand) P.hand.push({uid:srcUid,id:src});
  if (a.fromEnergy) P.energy.push({uid:srcUid,id:src,rested:false});
  if (s.phase==='attack' && d.type==='unit') { s.attacking=srcUid; }
  if (v) { const aces=base.filter(k=>DEFS[k].sub==='ace'); P.life=P.life.slice(0,4); const su=s.field.find(u=>u.uid==='SRC'); if(su) su.rested=true;
    for(let i=0;i<4;i++){ P.hand.push(C(pick(aces.length?aces:units))); P.drop.push(C(pick(aces.length?aces:units))); P.energy.push({uid:uid(),id:pick(aces.length?aces:units),rested:false}); }
    P.hand.push(C(pick(units.filter(k=>DEFS[k].cost<=3).concat(units)))); s.field.filter(u=>u.owner===p).forEach(u=>u.rested=true); }
  s.queue=[]; s.conts=[]; s.pending=null;
  return s;
}

// 카드마다 풍부한 상태 여러 개에서 조건을 평가: 한 번도 참이 안 되는 조건(값)을 찾음
const CTX_FREE=new Set(['terr','terrTitle','terrTitleAny','zc','zcAll','countGE','zoneHas','energyGE','lifeLE','lifeGE','handGE','handLE','dropGE','oppLifeLE','oppHandGE','myTurn','oppTurn','turnGE','redZone','energyColorsGE','energyEach','fieldGE','oppFieldGE','dropAttrsEach']);
const res=[]; const seen=new Set();
for (const k of base) { const d=DEFS[k];
  (d.ab||[]).forEach((a,ai)=>{ for (const c of a.if||[]) { const [key]=Object.keys(c); if(!CTX_FREE.has(key)) continue;
    const sig=JSON.stringify(c); if(seen.has(sig+k)) continue; seen.add(sig+k);
    let any=false, err=null;
    for (let t=0;t<12&&!any;t++){ let s; try{ s=state(k,a,t%2===1); }catch(e){ continue; }
      const p=s.active; try{ if(ctx.condOk(s,{p,src:'SRC',id:k,T:[]},c)) any=true; }catch(e){ err=e.message; break; } }
    if(!any) res.push({k,name:d.name,cond:sig,err});
  } });
}
const byCond={}; for(const r of res){ (byCond[r.cond] ||= []).push(r.k+' '+r.name+(r.err?' ERR '+r.err:'')); }
for(const [c,l] of Object.entries(byCond)) console.log(c.slice(0,160),'|',l.length,l.slice(0,3).join(' / '));

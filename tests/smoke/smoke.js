// 모든 카드 능력을 풍부한 상태에서 직접 실행해 보고 이상한 것을 찾는 점검 도구
const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const html=fs.readFileSync(H,'utf8');const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
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
const strip=s=>{ const c=structuredClone(s); for (const k of ['log','fx','fxSeq','hist','reveals','seq','queue','conts','pending','_fxP','_moved','rngState','rng']) delete c[k];
  if(c.turn){ const t=c.turn; c.turn={flags:t.flags,ttrig:t.ttrig,watch:t.watch,restrict:t.restrict}; }
  for (const P of c.players) { delete P.classTri; }
  return JSON.stringify(c); };
function answer(s){
  const pd=s.pending, P=s.players[pd.player];
  switch(pd.type){
    case 'order': return {type:'ORDER',i:0};
    case 'block': return {type:'BLOCK',blocker:null};
    case 'shot': return {type:'SHOT',play:false};
    case 'discard': return {type:'DISCARD',uid:P.hand[0].uid};
    case 'scout': return {type:'SCOUT',top:P.deck.slice(0,pd.n).map(c=>c.uid),bottom:[]};
    case 'territory': return {type:'TERRITORY',open:false};
    case 'bright': return {type:'BRIGHT',discard:null};
    case 'dress': return {type:'DRESS',unit:null};
    case 'setPlay': return {type:'PLAY_SET',uid:null};
    case 'cosplay': return {type:'COSPLAY',pick:null};
    case 'seika': return pd.step==='discard'?{type:'SEIKA',uid:null}:{type:'SEIKA',uid:Engine.seikaTargets(s,pd.player)[0]};
    case 'flashback': return {type:'FLASHBACK',uid:Engine.flashTargets(s,pd.player)[0]};
    case 'fx':
      if(pd.kind==='confirm') return {type:'FX',yes:true};
      if(pd.kind==='choose'){ let k=0; while(pd.dis?.includes(k)) k++; return {type:'FX',choice:k}; }
      return {type:'FX',uids:pd.cands.slice(0,Math.max(pd.min||0,Math.min(pd.max??1,1)))};
  }
  return null;
}
const DIFF=process.argv[4]==='diff';
const res={err:[],nochange:[],cost:[],unh:[],stuck:[],ok:0};
const seen=new Set();
for (const k of base) { const d=DEFS[k]; if(ONLY&&!ONLY.includes(k)) continue;
  (d.ab||[]).forEach((a,ai)=>{
    const key=d.name+'|'+JSON.stringify(a); if(seen.has(key)) return; seen.add(key);
    if(a.k==='perm') return;
    const txt=d.type==='territory'?((d.tfx?.text||'').split(' / ')[(a.li||[0])[0]]||''):(a.li||[]).map(i=>d.text?.[i]||'').join(' ');
    const attempt=(v)=>{ const out={};
    let s; try{ s=state(k,a,v); }catch(e){ return {kind:'err',rec:{k,name:d.name,ai,phase:'setup',e:e.message}}; }
    const p=s.active, srcUid=d.type==='territory'?null:'SRC';
    const ctxx={p,src:srcUid,id:k,T:[],evt:a.src==='self'?srcUid:a.src==='opp'?'OP0':a.src==='own'?s.field.find(u=>u.owner===p&&u.uid!=='SRC')?.uid:null,vs:'OP0'};
    s.pending={type:'order',player:p,items:[{t:'ab',p,src:srcUid,id:k,ai,ctx:ctxx}]};
    const b0=strip({...s,pending:null});
    let steps=0, err=null;
    try{ s=Engine.apply(s,{type:'ORDER',i:0});
      while(s.pending&&s.winner==null&&steps<40){ const an=answer(s); if(!an) break; s=Engine.apply(s,an); steps++; }
    }catch(e){ err=e.message; }
    const lg=s.log.slice(-12).map(l=>l.m);
    const rec={k,name:d.name,ai,on:a.on||a.k,txt:txt.slice(0,160),log:lg.slice(-5)};
    if(err){ return {kind:'err',rec:{...rec,e:err}}; }
    if(s.pending&&s.winner==null){ return {kind:'stuck',rec:{...rec,pd:s.pending.type+'/'+(s.pending.kind||'')}}; }
    if(lg.some(m=>m.includes('처리하지 못한'))){ return {kind:'unh',rec}; }
    if(lg.some(m=>m.includes('비용을 낼 수 없'))){ return {kind:'cost',rec}; }
    if(strip(s)===b0){ return {kind:'nochange',rec}; }
    // 기대 효과 점검: 문장에 있는 효과가 상태에 나타났는지
    const B=JSON.parse(b0), A=JSON.parse(strip(s));
    const fld=(X,w)=>X.field.filter(u=>w==null||u.owner===w);
    const pw=(X,w)=>{ return 0; };
    const miss=[];
    const T2=txt.replace(/（[^）]*）/g,'');
    const has=re=>re.test(T2);
    const me=p, op=1-p;
    if (has(/(\d+|１|２|３)枚引|引く|引き/) && !has(/なるように引/) && !(A.players[me].hand.length>B.players[me].hand.length || A.players[me].deck.length<B.players[me].deck.length || A.players[op].deck.length<B.players[op].deck.length)) miss.push('드로우');
    if (has(/\d+ダメージ/) && !has(/ダメージで敗北|ダメージを受けない|ダメージでも受けると/) && !(fld(A).some(u=>{const b=B.field.find(x=>x.uid===u.uid);return b&&u.damage>b.damage;}) || fld(A).length<fld(B).length || A.players.some((P,i)=>P.life.length<B.players[i].life.length))) miss.push('데미지');
    if (has(/手札に戻/) && !(A.players.some((P,i)=>P.hand.length>B.players[i].hand.length))) miss.push('패로');
    if (has(/登場させ/) && !has(/登場させない|登場させられない/) && !(fld(A).length>fld(B).length || fld(A).some(u=>!B.field.find(x=>x.uid===u.uid)))) miss.push('등장');
    if (has(/パワーを[＋+]/) && !fld(A).some(u=>{const b=B.field.find(x=>x.uid===u.uid);return !b||JSON.stringify(u.tmp)!==JSON.stringify(b.tmp)||JSON.stringify(u.lt||[])!==JSON.stringify(b.lt||[]);})) miss.push('파워');
    if (has(/をドロップさせ/) && !(fld(A,op).length<fld(B,op).length || fld(A,me).length<fld(B,me).length)) miss.push('드롭');
    if (has(/レストする|レストし、/) && !has(/レストすることで|レストしているなら|レストで登場/) && !fld(A).some(u=>{const b=B.field.find(x=>x.uid===u.uid);return b&&u.rested&&!b.rested;}) && !A.players.some((P,i)=>P.energy.filter(e=>e.rested).length>B.players[i].energy.filter(e=>e.rested).length)) miss.push('레스트');
    if (miss.length) { return {kind:'miss',rec:{...rec,miss}}; }
    return {kind:'ok'};
    };
    let r=attempt(false); if(r.kind!=='ok'&&r.kind!=='err'){ const r2=attempt(true); if(r2.kind==='ok') r=r2; }
    if(r.kind==='ok'){ res.ok++; return; }
    (res[r.kind]||(res[r.kind]=[])).push(r.rec); return;
    res.ok++;
  });
}
console.log(JSON.stringify({cb:DB.collabs[CB],ok:res.ok,miss:(res.miss||[]).length,err:res.err.length,stuck:res.stuck.length,unh:res.unh.length,cost:res.cost.length,nochange:res.nochange.length}));
fs.writeFileSync('/tmp/sm/r'+CB+'.json',JSON.stringify(res,null,1));

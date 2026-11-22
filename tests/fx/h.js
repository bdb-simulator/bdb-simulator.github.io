const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const html=fs.readFileSync(H,'utf8');const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
const {Engine,DEFS,DECKS}=ctx;const DB=JSON.parse(fs.readFileSync(H.replace('index.html','cards_db.json'),'utf8'));
for (const [k,d] of Object.entries(DB.defs)) if(!DEFS[k]) DEFS[k]=Object.assign({id:k,icon:null,attr:[],icons:[],titles:[]},d);
const deck=DECKS.wGZNWKQ4Z; // 그노시아 입상 덱
let n=0; const U=(id,owner,o={})=>({uid:o.uid||('zu'+(++n)),id,owner,rested:!!o.rested,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]});
const C=(id)=>({uid:'zc'+(++n),id});
function base(terrId){ let s=Engine.newGame(deck,deck,7); s=Engine.apply(s,{type:'MULLIGAN',redraw:false}); s=Engine.apply(s,{type:'MULLIGAN',redraw:false});
  if(terrId) s.players[s.active].territory={id:terrId,open:true};
  s.players[s.active].territory.open=true; s.field=[]; return s; }
// 능력 하나를 즉시 실행
function run(s,p,id,ai,ctxx={}){ s=structuredClone(s); s.pending={type:'order',player:p,items:[{t:'ab',p,src:ctxx.src||null,id,ai,ctx:{p,src:ctxx.src||null,id,T:[],...ctxx}}]}; return Engine.apply(s,{type:'ORDER',i:0}); }
function auto(s,ans=[]){ let k=0; for(let i=0;i<30&&s.pending&&s.winner==null;i++){ const pd=s.pending; const a=ans[k++];
  if(a!==undefined && a!==null){ s=Engine.apply(s,a); continue; }
  if(pd.type==='fx'){ if(pd.kind==='confirm') s=Engine.apply(s,{type:'FX',yes:true}); else if(pd.kind==='choose') s=Engine.apply(s,{type:'FX',choice:0}); else s=Engine.apply(s,{type:'FX',uids:pd.cands.slice(0,Math.max(pd.min||0, Math.min(1,pd.max)))}); }
  else if(pd.type==='order') s=Engine.apply(s,{type:'ORDER',i:0});
  else if(pd.type==='block') s=Engine.apply(s,{type:'BLOCK',blocker:null});
  else break; } return s; }
const L=s=>s.log.slice(-8).map(l=>l.m);
module.exports={Engine,DEFS,DB,U,C,base,run,auto,L};

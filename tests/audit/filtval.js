// 카드 데이터에 쓰인 필터 (키, 값) 하나하나를 defMatches로 전 카드에 돌려 봄: 아무것도 거르지 않거나 아무것도 안 맞으면 의심
const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const code=fs.readFileSync(H,'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code.replace(/function defMatches\(/,'ctx.defMatches=defMatches;function defMatches(')+'\nctx.DEFS=DEFS;')(ctx);
const DB=JSON.parse(fs.readFileSync(H.replace('index.html','cards_db.json'),'utf8')).defs;
for (const [k,d] of Object.entries(DB)) if(!ctx.DEFS[k]) ctx.DEFS[k]=Object.assign({id:k,icon:null,attr:[],icons:[],titles:[]},d);
const all=Object.values(ctx.DEFS).filter(d=>d.type&&d.type!=='territory');
const pairs=new Map();
const SKIP=new Set(['side','n','upto','zone','or','not','cls','field','self','rested','attacking','stand','other','ctx']);
function walkF(f,cid){ if(!f||typeof f!=='object') return; if(Array.isArray(f)) return f.forEach(g=>walkF(g,cid));
  for(const [k,v] of Object.entries(f)){ if(k==='or'){walkF(v,cid);continue;} const key=k+'='+JSON.stringify(v); if(!pairs.has(key)) pairs.set(key,{k,v,cards:new Set()}); pairs.get(key).cards.add(cid); } }
function walk(x,cid){ if(Array.isArray(x)) return x.forEach(y=>walk(y,cid)); if(x&&typeof x==='object'){ for(const [k,v] of Object.entries(x)){ if(k==='f') walkF(v,cid); else walk(v,cid);} } }
for(const [cid,d] of Object.entries(DB)) walk(d.ab||[],cid);
const out=[];
for(const {k,v,cards} of pairs.values()){
  let n; try{ n=all.filter(d=>ctx.defMatches(d,{[k]:v})).length; }catch(e){ out.push(['ERR',k,v,e.message,[...cards].slice(0,4)]); continue; }
  if(n===all.length) out.push(['거르지 않음',k,JSON.stringify(v),cards.size,[...cards].slice(0,5).join(',')]);
  else if(n===0) out.push(['아무것도 안 맞음',k,JSON.stringify(v),cards.size,[...cards].slice(0,5).join(',')]);
}
out.sort((a,b)=>a[1]<b[1]?-1:1); for(const o of out) console.log(o.join(' | '));
console.log('pairs',pairs.size,'suspect',out.length);

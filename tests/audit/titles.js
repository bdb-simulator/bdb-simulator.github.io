// 칭호 표기·테리토리 칭호 보충 확인: 조건이 실제 테리토리로 참이 되는지
const fs=require('fs');const H='/home/claude/bdb-simulator/simulator/index.html';
const code=fs.readFileSync(H,'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];const ctx={};
new Function('ctx',code.replace('function condOk(','ctx.condOk=condOk;function condOk(').replace(/function defMatches\(/,'ctx.defMatches=defMatches;function defMatches(')+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
const {Engine,DEFS,DECKS}=ctx; const DB=JSON.parse(fs.readFileSync(H.replace('index.html','cards_db.json'),'utf8'));
for (const [k,d] of Object.entries(DB.defs)) if(!DEFS[k]) DEFS[k]=Object.assign({id:k,icon:null,attr:[],icons:[],titles:[]},d);
let s=Engine.newGame(DECKS.wGZEVOA7X,DECKS.wGZEVOA7X,1); const p=s.active;
const cases=[['5002',{terrTitle:'恋愛は戦!!'}],['5029',{terrTitle:'告白'}],['5049',{terrTitle:'秀知院学園'}],['2735',{terrTitle:'blessing software'}],['2717',{terrTitle:'冴えカノ'}],['5040',{terrTitle:'秀知院学園'}],['4815',{terrTitle:'怪異譚'}],['4940',{terrTitle:'生命戦維'}]];
let ok=0; for(const [t,c] of cases){ s.players[p].territory={id:t,open:true}; const r=ctx.condOk(s,{p,T:[]},c); ok+=r; console.log(r?'OK ':'NG ',t,DEFS[t].name,JSON.stringify(c)); }
const ab=DB.defs['5258'].ab.find(a=>a.on==='win'); console.log('5258 조건', JSON.stringify(ab.if), '칭호 필터', JSON.stringify(ab.do[0].f));
console.log('「いざ調合！」 이름 필터 일치', Object.values(DEFS).filter(d=>ctx.defMatches(d,{name:DB.defs['2546'].ab[0].do.at(-1).per.f.name})).length);

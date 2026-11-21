const {JSDOM}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync(process.argv[2],'utf8');
const db=JSON.parse(fs.readFileSync(process.argv[2].replace('index.html','cards_db.json'),'utf8'));
const dom=new JSDOM(html,{runScripts:'dangerously',beforeParse(w){w.structuredClone=structuredClone;}});
const w=dom.window,d=w.document;const clk=el=>el&&el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
clk(d.querySelector('[data-b=goPlay]'));w.eval("deckChoice=[deckChoice[0]||'bocchi',deckChoice[1]||'bocchi'];render()");clk(d.querySelector('[data-b=startLocal]'));clk(d.querySelector('[data-b=keep]'));clk(d.querySelector('[data-b=keep]'));
w.__db=db.defs;
console.log(JSON.stringify(w.eval(`(() => {
  const T=Object.keys(__db).find(k=>__db[k].type==='territory'&&(__db[k].titles||[]).includes('コスキュン'));
  const ace=Object.keys(__db).find(k=>__db[k].type==='unit'&&__db[k].sub==='ace'&&(__db[k].attr||[]).includes('ハート')&&!__db[k].text&&!__db[k].cos);
  for (const k of ['6298',ace,T]) if(!DEFS[k]) def(k,Object.assign({},__db[k],{id:k}));
  const s=structuredClone(S),p=s.active,P=s.players[p]; s.phase='main'; s.pending=null;
  P.territory={id:T,open:true}; P.hand=[{uid:'h1',id:ace}];
  s.field=s.field.filter(u=>u.owner!==p);
  s.field.push({uid:'g1',id:'6298',owner:p,rested:false,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]});
  S=s; dispatch({type:'NEXT_PHASE'});
  const steps=[];
  for(let i=0;i<8&&S.pending;i++){ const pd=S.pending; steps.push(pd.kind||pd.type);
    if(pd.kind==='confirm'||pd.type==='confirm') dispatch({type:'FX',yes:true});
    else if(pd.kind==='pick') dispatch({type:'FX',uids:pd.cands.slice(0,1)});
    else break; }
  const u=S.field.find(x=>x.uid==='h1');
  return {terr:T,ace,steps,phase:S.phase,등장:!!u,코스프레:u&&Engine.cosValue(S,u),파워:u&&Engine.power(S,u),원래파워:DEFS[ace].power,log:S.log.slice(-6).map(l=>l.m)};
})()`)));

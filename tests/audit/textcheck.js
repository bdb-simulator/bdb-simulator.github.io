// 카드 원문(일본어)에서 '고르는 대상'의 조건을 뽑아, 엔진이 실제로 내민 후보·장수와 대조
const Z2='０１２３４５６７８９';
const num=t=>+String(t).replace(/[０-９]/g,c=>Z2.indexOf(c));
const COL={'赤':'red','青':'blue','白':'white','黒':'black','緑':'green','黄':'yellow'};
module.exports=(Engine,DEFS)=>{
  const issues=new Map();
  function phrases(txt){
    const T=txt.replace(/（[^）]*）/g,'').replace(/『[^』]*』/g,'');   // 괄호 설명·부여 능력 문장 제외
    const out=[];
    const re=/([^、。：]*?)を([０-９\d]+)枚(まで)?/g; let m;
    while((m=re.exec(T))){ let P=m[1]; const after=T.slice(re.lastIndex,re.lastIndex+12);
      const c={n:num(m[2]),upto:!!m[3],raw:P+'を'+m[2]+'枚'+(m[3]||'')+after.slice(0,6)};
      if(/相手の/.test(P)&&!/あなたの/.test(P)) c.side='opp'; else if(/あなたの/.test(P)||/^(手札|ドロップゾーン|エナジー)/.test(P)) c.side='own';
      if(/コマンド/.test(P)) c.type='command'; else if(/ユニット/.test(P)) c.type='unit';
      if(/エース/.test(P)&&!/エース以外|エースでない/.test(P)) c.ace=1;
      if(/エース以外|エースでない/.test(P)) c.ace=0;
      let k; if((k=/コスト([０-９\d]+)以下/.exec(P))) c.costLE=num(k[1]); if((k=/コスト([０-９\d]+)以上/.exec(P))) c.costGE=num(k[1]);
      if((k=/パワー([０-９\d]+)以下/.exec(P))) c.powLE=num(k[1]); if((k=/パワー([０-９\d]+)以上/.exec(P))) c.powGE=num(k[1]);
      const neg=[...P.matchAll(/(赤|青|白|黒|緑|黄)(?:でない|以外)/g)].map(x=>COL[x[1]]); if(neg.length) c.notColors=neg;
      const cols=[...P.replace(/(赤|青|白|黒|緑|黄)(?:でない|以外)/g,'').matchAll(/(赤|青|白|黒|緑|黄)(?=の|か|で|・|と|、)/g)].map(x=>COL[x[1]]); if(cols.length) c.colors=cols;
      const attrs=[...P.matchAll(/⁅(ダイヤ|ハート|スペード|クラブ)⁆/g)].map(x=>x[1]); if(attrs.length&&!/でない|以外/.test(P)) c.attrs=attrs;
      if(/その中|見て|公開/.test(P)) c.skip=1; if(/生成/.test(P+after)) c.skip=1; if(/バスター|ショット|⁅B⁆|⁅S⁆/.test(P)) c.loose=1;
      if(/レスト状態の|レストしている/.test(P)) c.rested=1; if(/スタンド状態の|スタンドしている/.test(P)) c.rested=0;
      if(/ドロップゾーン/.test(P)) c.zone='drop'; else if(/手札/.test(P)) c.zone='hand'; else if(/エナジー/.test(P)) c.zone='energy'; else if(/ライフ/.test(P)) c.zone='life'; else if(/山札/.test(P)) c.zone='deck'; else if(/ユニット/.test(P)&&!/カード/.test(P)) c.zone='field';
      if(/他の/.test(P)) c.notSelf=1;
      if(/このユニット以外|このカード以外/.test(P)) c.notSelf=1;
      out.push(c);
    }
    return out;
  }
  function where(s,uid){
    const u=Engine.findUnit(s,uid); if(u) return {c:u,zone:'field',owner:u.owner,pow:Engine.power(s,u),rested:u.rested};
    for(let p=0;p<2;p++){ const P=s.players[p]; for(const z of ['hand','drop','energy','life','deck','remove','set']) { const c=(P[z]||[]).find(c=>c.uid===uid); if(c) return {c,zone:z,owner:p,pow:DEFS[c.id].power,rested:c.rested}; } }
    return null;
  }
  function ok(c,w,me,src){
    const d=DEFS[w.c.id]; if(!d) return true; const why=[];
    if(c.side==='opp'&&w.owner===me) why.push('내 카드'); if(c.side==='own'&&w.owner!==me) why.push('상대 카드');
    if(c.type&&d.type!==c.type) why.push(d.type);
    if(c.ace===1&&d.sub!=='ace') why.push('에이스 아님'); if(c.ace===0&&d.sub==='ace') why.push('에이스');
    if(c.costLE!=null&&!(d.cost<=c.costLE)) why.push('코스트'+d.cost); if(c.costGE!=null&&!(d.cost>=c.costGE)) why.push('코스트'+d.cost);
    if(c.powLE!=null&&!(w.pow<=c.powLE)) why.push('파워'+w.pow); if(c.powGE!=null&&!(w.pow>=c.powGE)) why.push('파워'+w.pow);
    if(c.notColors&&c.notColors.includes(d.color)) why.push(d.color);
    if(c.attrs&&!c.attrs.some(x=>(d.attr||[]).includes(x))) why.push('속성 '+(d.attr||[]).join('/'));
    if(c.loose) return why.filter(x=>!/에이스|코스트|파워/.test(x));
    if(c.colors&&!c.colors.includes(d.color)&&!(d.colors||[]).some(x=>c.colors.includes(x))) why.push(d.color);
    if(c.rested===1&&w.zone==='field'&&!w.rested) why.push('스탠드'); if(c.rested===0&&w.zone==='field'&&w.rested) why.push('레스트');
    if(c.zone&&c.zone!==w.zone&&!(c.zone==='field'&&w.zone==='field')) why.push('영역 '+w.zone);
    if(c.notSelf&&w.c.uid===src) why.push('자기 자신');
    return why;
  }
  function add(kind,id,ai,msg,ex){ const k=kind+'|'+id+'|'+ai+'|'+msg; if(!issues.has(k)) issues.set(k,{kind,id,ai,msg,ex}); }
  return {
    check(s,cur){
      const pd=s.pending; if(!pd||pd.type!=='fx'||pd.kind!=='pick'||!pd.q) return;
      if(!['tgt','pick','discard'].includes(pd.q.steps?.[pd.q.i]?.op)) return;
      const st=pd.q.steps[pd.q.i]; const q=pd.q, d=DEFS[q.id], a=(d?.ab||[])[q.ai]; if(!a) return;
      const inCost=st.inCost||(a.cost||[]).includes(st);
      const skillLines=(d.text||[]).filter(t=>/^【スキル】/.test(t)||/^【[^】]+】（/.test(t));
      const txt=inCost&&skillLines.length?skillLines.join(' '):d.type==='territory'?(d.tfx?.text||''):(a.li||[]).map(i=>d.text?.[i]||'').join(' ');
      const W=pd.cands.map(u=>where(s,u)).filter(Boolean); if(!W.length) return;
      const zoneOf=W[0].zone;
      const ph=phrases(txt).filter(c=>!c.skip&&(!c.zone||c.zone===zoneOf||(c.zone==='field'&&zoneOf==='field'))&&(st.op!=='discard'||c.zone==='hand'||/手札/.test(c.raw))&&(zoneOf==='field'?!c.zone||c.zone==='field':!!c.zone)); if(!ph.length) return;
      // 후보가 모두 들어맞는 문구가 하나라도 있으면 통과
      const scored=ph.map(c=>({c,bad:W.map(w=>({w,why:ok(c,w,q.p,q.src)})).filter(x=>x.why.length)}));
      const best=scored.sort((x,y)=>x.bad.length-y.bad.length)[0];
      if(best.bad.length){ const b=best.bad[0]; add('후보에 조건 밖 카드',q.id,q.ai,`「${best.c.raw}」 ← ${DEFS[b.w.c.id].name}(${b.why.join(',')})`, st.op+' '+JSON.stringify(st.f||{})); }
      else {
        const c=best.c;
        // 장수: 「まで」가 없으면 반드시 그만큼 (고를 수 있는 만큼), 있으면 0장도 가능
        const min=pd.min??0, max=pd.max??1;
        if(c.upto&&min>0&&st.op!=='discard') add('「まで」인데 반드시 골라야 함',q.id,q.ai,`「${c.raw}」 min=${min}`,st.op);
        if(!c.upto&&min===0&&W.length>=1&&!/てもよい|てよい|ことができ/.test(txt)) add('반드시 고르는데 0장 허용',q.id,q.ai,`「${c.raw}」 min=0`,st.op);
        if(max!==c.n&&max<Math.min(c.n,W.length)) add('고르는 장수 다름',q.id,q.ai,`「${c.raw}」 max=${max}`,st.op);
        // 빠진 후보: 같은 영역에서 조건을 만족하는데 후보에 없는 카드
        if(['field','drop','hand'].includes(zoneOf)){
          const pool=zoneOf==='field'?s.field.map(u=>where(s,u.uid)):[0,1].flatMap(p=>(s.players[p][zoneOf]||[]).map(cc=>({c:cc,zone:zoneOf,owner:p,pow:DEFS[cc.id]?.power})));
          const miss=pool.filter(w=>w&&w.c.id!=='CLASS'&&!pd.cands.includes(w.c.uid)&&!ok(c,w,q.p,q.src).length&&(c.side||w.owner===W[0].owner));
          if(miss.length) add('조건에 맞는데 후보에서 빠짐',q.id,q.ai,`「${c.raw}」 ← ${DEFS[miss[0].c.id].name}`,st.op+' '+JSON.stringify(st.f||{}));
        }
      }
    },
    dump(cb,name){ const arr=[...issues.values()]; require('fs').writeFileSync('/tmp/aud/'+cb+'.json',JSON.stringify(arr,null,1)); const cnt={}; for(const x of arr) cnt[x.kind]=(cnt[x.kind]||0)+1; console.log(cb,name,JSON.stringify(cnt)); }
  };
};

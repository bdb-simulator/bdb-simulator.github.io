# 브라우저에서 공격 연출 순서를 시간대별로 기록 (공격 → 공격 시 능력 → 라이프 공개)
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        pg = await b.new_page(viewport={'width':1400,'height':860}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(800)
        await pg.evaluate("""() => { deckChoice=['wGZEVOA7X','wGZEVOA7X']; }""")
        await pg.click('[data-b=goPlay]'); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { deckChoice=['wGZEVOA7X','wGZEVOA7X']; }""")
        await pg.click('[data-b=startLocal]'); await pg.wait_for_timeout(300)
        for _ in range(2):
            if await pg.locator('[data-b=keep]').count(): await pg.click('[data-b=keep]'); await pg.wait_for_timeout(200)
        await pg.evaluate("""() => {
          const s = structuredClone(S), p = s.active, o = 1-p;
          const ids=[...new Set([...s.players[p].deck,...s.players[p].hand,...s.players[o].deck].map(c=>c.id))].filter(k=>DEFS[k]?.icons);
          const atkU = ids.find(k=>DEFS[k].type==='unit'&&(DEFS[k].ab||[]).some(a=>a.k==='auto'&&a.on==='attack'&&a.src==='self'&&!(a.if||[]).length)) || ids.find(k=>DEFS[k].type==='unit');
          const bu = ids.find(k=>DEFS[k].icon==='buster'), pl = ids.find(k=>!DEFS[k].icon&&DEFS[k].type==='unit');
          s.field.push({uid:'zA',id:atkU,owner:p,rested:false,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]});
          s.players[o].life=[{uid:'zl1',id:bu},{uid:'zl2',id:pl},{uid:'zl3',id:pl},{uid:'zl4',id:pl}];
          s.phase='attack'; S=s; render(); window.__t=[atkU&&DEFS[atkU].name];
          const t0=performance.now(); window.__iv=setInterval(()=>{ const bn=document.querySelector('#fxlayer .banner'), rv=document.querySelector('#reveal .rv .kind');
            const v=(rv?'LIFE:'+rv.textContent:'')||(bn?bn.textContent.slice(0,14):''); const a=window.__t; if(v && a[a.length-1]!==v) a.push(v); },50);
          dispatch({type:'ATTACK',attacker:'zA',target:'player'});
        }""")
        for i in range(40):
            await pg.wait_for_timeout(300)
            if await pg.evaluate("!Fx.busy && !(S.pending)"): break
            if await pg.evaluate("S.pending?.type==='fx' && !Fx.busy"): await pg.evaluate("dispatch(S.pending.kind==='confirm'?{type:'FX',yes:true}:{type:'FX',uids:S.pending.cands.slice(0,1)})")
        print(json.dumps(await pg.evaluate("window.__t"), ensure_ascii=False)); print('errors', errs); await b.close()
asyncio.run(main())

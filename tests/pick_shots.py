import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        for W,H,mob in [(1400,860,False),(390,844,True)]:
            ctx = await b.new_context(viewport={'width':W,'height':H}, is_mobile=mob, has_touch=mob, device_scale_factor=1 if not mob else 2)
            pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(800)
            await pg.evaluate("localStorage.setItem('bdb-fx','off')")
            await pg.evaluate("document.querySelector('[data-b=goPlay]').click()"); await pg.evaluate("deckChoice=['bocchi','bocchi'];render()")
            await pg.evaluate("document.querySelector('[data-b=startLocal]').click()"); await pg.wait_for_timeout(1500)
            for _ in range(2): await pg.evaluate("document.querySelector('[data-b=keep]').click()"); await pg.wait_for_timeout(200)
            await pg.evaluate("""() => { const s=structuredClone(S),p=s.active,o=1-p;
              const id=s.players[o].deck.find(c=>DEFS[c.id].type==='unit').id;
              for (const q of [o,o,o,p]) { const c=s.players[q].deck.find(c=>c.id===id)||s.players[q].deck.find(c=>DEFS[c.id].type==='unit'); s.players[q].deck.splice(s.players[q].deck.indexOf(c),1); s.field.push({uid:c.uid,id:c.id,owner:q,rested:false,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]}); }
              const cmd=Object.keys(DEFS).find(k=>DEFS[k].ab?.[0]?.k==='play'&&DEFS[k].ab[0].do[0]?.op==='tgt'); s.queue.push({t:'ab',p,src:'zz',id:cmd,ai:0,ctx:{p,src:'zz',id:cmd,T:[]},steps:[{op:'tgt',f:{type:'unit'},n:1,upto:0},{op:'dmg',n:1000,to:'T'}],i:0});
              S=s; S=Engine.apply(S,{type:'NEXT_PHASE'}); render(); return S.pending&&S.pending.kind; }""")
            await pg.wait_for_timeout(1200)
            await pg.screenshot(path=f'/tmp/mob/pick_{W}.png')
            print(W, errs, await pg.evaluate("[...document.querySelectorAll('.ptag')].map(e=>e.textContent)"))
        await b.close()
asyncio.run(main())

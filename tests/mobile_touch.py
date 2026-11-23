import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(800)
        await pg.tap('[data-b=goPlay]'); await pg.wait_for_timeout(300)
        await pg.evaluate("deckChoice=['wGZEVOA7X','wGZEVOA7X']; render()")
        await pg.tap('[data-b=startLocal]'); await pg.wait_for_timeout(400)
        for _ in range(2):
            await pg.tap('[data-b=keep]'); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { const s=structuredClone(S),p=s.active; const P=s.players[p];
          const u=Object.keys(DEFS).find(k=>DEFS[k].type==='unit'&&DEFS[k].cost<=2&&!DEFS[k].ab?.length&&DEFS[k].color!=='none');
          for (let i=0;i<4;i++) P.energy.push({uid:'ze'+i,id:u,rested:false}); P.hand.unshift({uid:'zz1',id:u}); S=s; render(); Fx.reset(); }""")
        await pg.wait_for_timeout(500)
        cdp = await ctx.new_cdp_session(pg)
        async def touch(t, x, y):
            pts = [] if t=='touchEnd' else [{'x':x,'y':y}]
            await cdp.send('Input.dispatchTouchEvent', {'type':t, 'touchPoints':pts})
        el = await pg.query_selector('.hand.me [data-cu=zz1], .hand.me [data-u=zz1]')
        await el.scroll_into_view_if_needed()
        bb = await el.bounding_box(); fb = await (await pg.query_selector('.ps.me .field')).bounding_box()
        x0,y0 = bb['x']+bb['width']/2, bb['y']+bb['height']/2; x1,y1 = fb['x']+fb['width']/2, fb['y']+fb['height']/2
        await touch('touchStart', x0, y0)
        for i in range(1,13): await touch('touchMove', x0+(x1-x0)*i/12, y0+(y1-y0)*i/12); await pg.wait_for_timeout(16)
        await touch('touchEnd', x1, y1); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({onField: S.field.some(u=>u.uid==='zz1'), toast, pend: S.pending&&S.pending.type})")
        # 가로로 밀기: 패 스크롤
        hr = await pg.query_selector('.hand.me .handrow'); hb = await hr.bounding_box()
        await pg.evaluate("for(let i=0;i<6;i++) S.players[S.active].hand.push(S.players[S.active].deck.shift()); render()")
        hr = await pg.query_selector('.hand.me .handrow'); hb = await hr.bounding_box()
        y = hb['y']+hb['height']/2
        await touch('touchStart', hb['x']+300, y)
        for i in range(1,11): await touch('touchMove', hb['x']+300-i*25, y); await pg.wait_for_timeout(16)
        await touch('touchEnd', 0, 0); await pg.wait_for_timeout(500)
        sl = await pg.evaluate("document.querySelector('.hand.me .handrow').scrollLeft")
        print(r, 'scrollLeft', sl, errs); await b.close()
asyncio.run(main())

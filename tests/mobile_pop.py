# 모바일 카드 설명 팝업: 탭(동작 없는 카드), 길게 누르기, '카드 설명' 탭, 닫기, 드래그로 내기 유지
import asyncio, json
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
        await pg.evaluate("""() => { const s=structuredClone(S),p=s.active,o=1-p; const P=s.players[p];
          const u=[...P.deck].map(c=>c.id).find(k=>DEFS[k]?.type==='unit');
          s.field.push({uid:'zo',id:u,owner:o,rested:false,damage:1000,tmp:{power:0,hit:0,kw:[]},att:[]});
          for (let i=0;i<4;i++) P.energy.push({uid:'ze'+i,id:u,rested:false}); P.hand.unshift({uid:'zz1',id:u}); S=s; render(); Fx.reset(); }""")
        await pg.wait_for_timeout(400)
        out={}
        await pg.wait_for_function('!Fx.busy')
        # 1) 상대 유닛 탭 → 팝업
        await pg.tap('.card[data-u=zo]'); await pg.wait_for_timeout(300)
        out['상대유닛탭']=await pg.evaluate("!document.getElementById('cardpop').hidden")
        await pg.screenshot(path='/tmp/pop1.png')
        # 2) 바깥 탭 → 닫힘
        await pg.mouse.click(10,10); await pg.wait_for_timeout(200)
        out['바깥닫힘']=await pg.evaluate("document.getElementById('cardpop').hidden")
        # 3) 내 패 카드 탭 → 선택(팝업 없음)
        await pg.wait_for_function('!Fx.busy')
        el = await pg.query_selector('.hand.me [data-cu=zz1], .hand.me [data-u=zz1]'); await el.scroll_into_view_if_needed()
        await el.tap(timeout=5000); await pg.wait_for_timeout(300)
        out['패탭_팝업없음']=await pg.evaluate("document.getElementById('cardpop').hidden")
        # 4) 길게 누르기 → 팝업
        el = await pg.query_selector('.hand.me [data-cu=zz1], .hand.me [data-u=zz1]'); bb=await el.bounding_box(); cdp=await ctx.new_cdp_session(pg)
        x,y=bb['x']+bb['width']/2, bb['y']+12
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]}); await pg.wait_for_timeout(650)
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]}); await pg.wait_for_timeout(300)
        out['길게누르기']=await pg.evaluate("!document.getElementById('cardpop').hidden && CardPop.det.uid==='zz1'")
        out['길게누른뒤_선택안바뀜']=await pg.evaluate("ui.sel")
        await pg.screenshot(path='/tmp/pop2.png')
        await pg.tap('#cardpop .cpx'); await pg.wait_for_timeout(200)
        # 5) '카드 설명' 탭 → 팝업
        await pg.tap('[data-b=side][data-s=card]'); await pg.wait_for_timeout(300)
        out['설명탭']=await pg.evaluate("!document.getElementById('cardpop').hidden && !document.querySelector('.log.open')")
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
        out['Esc닫힘']=await pg.evaluate("document.getElementById('cardpop').hidden")
        # 6) 데스크톱 크기에선 팝업 안 뜸
        await pg.set_viewport_size({'width':1400,'height':860}); await pg.wait_for_timeout(300)
        await pg.click('.card[data-u=zo]'); await pg.wait_for_timeout(300)
        out['데스크톱_팝업없음']=await pg.evaluate("document.getElementById('cardpop').hidden")
        print(json.dumps(out,ensure_ascii=False)); print('errors',errs); await b.close()
asyncio.run(main())

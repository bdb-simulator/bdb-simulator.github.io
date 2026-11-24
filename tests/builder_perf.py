# 덱 편성 화면: 작품 목록이 바로 나오는지, 작품을 바꿨을 때 그림이 얼마나 빨리 채워지는지, 받은 용량, 스크롤 유지
import asyncio, json, sys
from playwright.async_api import async_playwright
PORT = sys.argv[1] if len(sys.argv) > 1 else '8791'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        pg = await b.new_page(viewport={'width':1400,'height':860}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        got = {'bytes':0,'req':0}
        async def onresp(r):
            if '/packs/' in r.url and r.url.endswith('.webp'):
                got['req'] += 1
                try: got['bytes'] += len(await r.body())
                except Exception: pass
        pg.on('response', lambda r: asyncio.ensure_future(onresp(r)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(500)
        await pg.evaluate("openBuilder()"); await pg.wait_for_timeout(50)
        n0 = await pg.evaluate("document.querySelectorAll('[data-bf=collab] option').length")
        await pg.wait_for_function("CardDB.data", timeout=20000)
        await pg.select_option('[data-bf=collab]', '10'); t0 = await pg.evaluate("performance.now()")
        # 처음 화면에 보이는 카드(위쪽 24장)의 그림이 채워질 때까지
        await pg.wait_for_function("[...document.querySelectorAll('.bgrid .card')].slice(0,24).every(c=>c.querySelector('img.art'))", timeout=60000)
        t1 = await pg.evaluate("performance.now()")
        # 스크롤해 둔 위치가 그림이 들어와도 유지되는지
        await pg.evaluate("document.querySelector('.bgrid').scrollTop=900"); await pg.wait_for_timeout(1500)
        keep = await pg.evaluate("document.querySelector('.bgrid').scrollTop")
        await pg.fill('.bq', 'アルトリア'); await pg.wait_for_timeout(400)
        focus = await pg.evaluate("document.activeElement?.dataset?.bf")
        print(json.dumps({'작품목록_즉시': n0, '위24장그림_ms': round(t1-t0), '받은_MB': round(got['bytes']/1e6,1), '요청수': got['req'], '스크롤유지': keep, '검색칸포커스': focus}, ensure_ascii=False))
        print('errors', errs); await b.close()
asyncio.run(main())

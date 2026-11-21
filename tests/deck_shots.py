import asyncio, sys
from playwright.async_api import async_playwright
async def run(p, W, H, mob):
    b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = await b.new_context(viewport={'width':W,'height':H}, device_scale_factor=1 if not mob else 2, is_mobile=mob, has_touch=mob)
    pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(1500)
    await pg.click('[data-b=goPlay]'); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'/tmp/mob/d{W}_empty.png')
    await pg.click('[data-b=openDecks][data-i="0"]'); await pg.wait_for_timeout(1500)
    await pg.screenshot(path=f'/tmp/mob/d{W}_modal.png')
    await pg.click('.dgrid .dtile >> nth=2'); await pg.wait_for_timeout(500)
    await pg.click('[data-b=openDecks][data-i="1"]'); await pg.wait_for_timeout(500)
    await pg.click('[data-b=deckTab][data-t=basic]'); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'/tmp/mob/d{W}_basic.png')
    await pg.click('.dgrid .dtile >> nth=0'); await pg.wait_for_timeout(800)
    await pg.screenshot(path=f'/tmp/mob/d{W}_chosen.png')
    dis = await pg.evaluate("document.querySelector('[data-b=startLocal]').disabled")
    print(W, 'start disabled:', dis, errs)
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 1400, 900, False); await run(p, 390, 844, True)
asyncio.run(main())

import asyncio
from playwright.async_api import async_playwright


async def test():
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        print("Playwright launched successfully")
        await browser.close()
        await pw.stop()
    except Exception as e:
        print(f"Playwright failed: {e}")


asyncio.run(test())
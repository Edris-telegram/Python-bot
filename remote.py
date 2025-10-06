import asyncio
from playwright.async_api import async_playwright

BROWSERLESS_WS = "wss://production-sfo.browserless.io?token=2TBcCoG2vzP3UFs93f92e1471c723563c170e676ec2e2d255"
async def run():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(BROWSERLESS_WS)
        page = await browser.new_page()
        await page.goto("https://www.google.com")
        print("✅ Page title:", await page.title())
        await browser.close()

asyncio.run(run())

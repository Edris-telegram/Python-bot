import asyncio
from playwright.async_api import async_playwright

EMAIL = "imadedison@gmail.com"
PASSWORD = "EDRIS1234"
MESSAGE = "Gm peeps😎"

# Use your Browserless token
BROWSERLESS_WS = "wss://production-sfo.browserless.io?token=2TBcCoG2vzP3UFs93f92e1471c723563c170e676ec2e2d255"

async def main():
    async with async_playwright() as p:
        print("Connecting to Browserless headless browser...")
        browser = await p.chromium.connect_over_cdp(BROWSERLESS_WS)
        context = await browser.new_context()
        page = await context.new_page()

        print("Opening CoinMarketCap...")
        await page.goto("https://coinmarketcap.com/")

        print("Clicking Login button...")
        await page.click("text=Log In")

        await page.wait_for_selector('input[name="email"]', timeout=15000)
        print("Filling in credentials...")
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="password"]', PASSWORD)

        await page.click('button:has-text("Log In")')
        await page.wait_for_load_state("networkidle")

        print("Login successful, navigating to new post page...")
        await page.goto("https://coinmarketcap.com/community/new-post/")
        await page.wait_for_selector('textarea[placeholder*="What’s happening"]', timeout=15000)

        print("Filling in post content...")
        await page.fill('textarea[placeholder*="What’s happening"]', MESSAGE)

        print("Submitting post...")
        await page.click('button:has-text("Post")')
        await page.wait_for_timeout(5000)

        print("✅ Post created successfully!")

        await browser.close()

asyncio.run(main())        print("Submitting post...")
        await page.click('button:has-text("Post")')
        await page.wait_for_timeout(5000)

        print("✅ Post created successfully!")

        await browser.close()

asyncio.run(main())

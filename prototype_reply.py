import os
import json
import asyncio
import logging
import threading
from fastapi import FastAPI, Request
import uvicorn
from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------
COOKIES_FILE = "cookies.json"

# Setup logging
logging.basicConfig(level=logging.INFO)

# FastAPI app
app = FastAPI()


# ----------- MAIN BROWSER FUNCTION -----------
async def send_reply(tweet_url: str, reply_message: str):
    logging.info(f"Launching browser to reply: {tweet_url} -> {reply_message}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()

        # Load cookies if available
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                logging.info("✅ Cookies loaded into browser context")

        page = await context.new_page()

        # Go to tweet link
        await page.goto(tweet_url)
        await page.wait_for_timeout(3000)

        # Check if logged in
        if "login" in page.url:
            logging.error("❌ Cookies invalid or expired – Twitter redirected to login")
            await browser.close()
            return

        # Click reply
        reply_box = await page.query_selector('div[aria-label="Tweet your reply"]')
        if reply_box:
            await reply_box.fill(reply_message)
            await page.keyboard.press("Control+Enter")
            logging.info("✅ Reply posted successfully")
        else:
            logging.error("❌ Could not find reply box")

        # Optionally update cookies (to refresh expiry)
        cookies = await context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f)
            logging.info("💾 Cookies updated")

        await browser.close()


# ----------- API ENDPOINTS -----------
@app.get("/")
def health():
    return {"status": "ok", "message": "Twitter bot is running with cookies"}


@app.post("/do_tweet")
async def do_tweet(request: Request):
    data = await request.json()
    tweet_url = data.get("link")
    reply_message = data.get("message")

    if not tweet_url or not reply_message:
        return {"status": "error", "message": "link and message are required"}

    # Run the browser task
    asyncio.create_task(send_reply(tweet_url, reply_message))
    return {"status": "ok", "tweet": tweet_url, "reply": reply_message}


# ----------- BACKGROUND KEEP-ALIVE LOOP -----------
async def keep_alive():
    while True:
        logging.info("⏳ Bot is alive and waiting for tasks...")
        await asyncio.sleep(60)  # ping every 1 minute


def start_background_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(keep_alive())
    loop.run_forever()


# ----------- ENTRY POINT -----------
if __name__ == "__main__":
    # Start keep-alive loop in background thread
    threading.Thread(target=start_background_loop, daemon=True).start()

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

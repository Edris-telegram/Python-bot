# prototype_reply_async.py
import asyncio
import os
import json
from playwright.async_api import async_playwright
from fastapi import FastAPI
import uvicorn

# -------- CONFIG --------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")
TWEET_URL = "https://x.com/Maldris15559/status/1968948525204472309"
FIXED_MESSAGE = "Prototype reply — testing ✅"
# ------------------------

def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []

    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                cookies = json.load(f)
                print(f"[🍪] Loaded {len(cookies)} cookies from JSON file")
                return cookies
            except Exception as e:
                print(f"[❌] Failed reading cookies.json: {e}")
                return []

    if "=" not in cookie_input:
        return [{
            "name": "auth_token",
            "value": cookie_input.strip(),
            "domain": ".x.com",
            "path": "/"
        }]

    parts = [p.strip() for p in cookie_input.split(";") if p.strip()]
    cookies = []
    for p in parts:
        if "=" in p:
            name, val = p.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": val.strip(),
                "domain": ".x.com",
                "path": "/"
            })
    return cookies

async def try_selectors(page, selectors, timeout=5000, step=""):
    for sel in selectors:
        try:
            print(f"[🔎] Trying selector: {sel} ({step})")
            handle = await page.wait_for_selector(sel, timeout=timeout)
            if handle:
                print(f"[✅] Found selector: {sel} ({step})")
                return sel
        except Exception as e:
            print(f"[❌] Selector failed: {sel} ({step}) -> {e}")
            continue
    return None

async def run_once(headless=True):
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var.")
        return

    cookies = parse_cookie_input(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie input.")
        return

    print("🚀 Starting Playwright (async)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context()

        try:
            await context.add_cookies(cookies)
            print("[🍪] Cookies applied")

            page = await context.new_page()

            print("[→] Visiting home...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            print("[✅] Home loaded")
            await asyncio.sleep(2)

            print(f"[→] Opening tweet: {TWEET_URL}")
            await page.goto(TWEET_URL, wait_until="domcontentloaded", timeout=60000)
            print("[✅] Tweet loaded")
            await asyncio.sleep(2)

            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]

            sel = await try_selectors(page, textbox_selectors, timeout=7000, step="reply textbox")

            if not sel:
                reply_buttons = [
                    "div[data-testid='reply']",
                    "div[role='button'][data-testid='reply']",
                    "a[href$='/reply']",
                ]
                rb = await try_selectors(page, reply_buttons, timeout=5000, step="reply button")
                if rb:
                    try:
                        print(f"[→] Clicking reply button ({rb})...")
                        await page.click(rb)
                        print(f"[✅] Clicked reply button ({rb})")
                        await asyncio.sleep(1.5)
                        sel = await try_selectors(page, textbox_selectors, timeout=7000, step="reply textbox after click")
                    except Exception as e:
                        print(f"[⚠️] Failed clicking reply button: {e}")

            if not sel:
                print("⚠️ Reply textbox not found — likely cookie issue.")
                await page.screenshot(path="debug_tweet.png")
                print("💾 Saved debug_tweet.png")
                return

            print(f"[→] Using textbox selector: {sel}")
            await page.click(sel)
            await asyncio.sleep(0.3)
            await page.fill(sel, FIXED_MESSAGE)
            print(f"[✅] Filled textbox with: {FIXED_MESSAGE}")
            await asyncio.sleep(0.4)

            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']",
                "div[role='button'][data-testid='tweetButton']",
            ]
            sent = False
            for s in send_selectors:
                try:
                    print(f"[→] Trying send button: {s}")
                    btn = await page.wait_for_selector(s, timeout=5000)
                    if btn:
                        await btn.click()
                        print(f"[✅] Clicked send button ({s})")
                        sent = True
                        break
                except Exception as e:
                    print(f"[❌] Failed on send button {s}: {e}")
                    continue

            if not sent:
                try:
                    print("[→] Fallback: Ctrl+Enter submit")
                    await page.keyboard.down("Control")
                    await page.keyboard.press("Enter")
                    await page.keyboard.up("Control")
                    print("[✅] Sent reply via keyboard fallback")
                    sent = True
                except Exception as e:
                    print(f"[❌] Keyboard fallback failed: {e}")

            if sent:
                print("[✔] Reply submitted. Waiting a few seconds...")
                await asyncio.sleep(5)
                print("[✔] Done (check tweet).")
            else:
                print("❌ Could not send reply. Screenshotting...")
                await page.screenshot(path="error_debug.png")
                print("💾 Saved error_debug.png")

        except Exception as e:
            print("❌ Exception during run:", e)
            try:
                await page.screenshot(path="error_debug.png")
                print("💾 Saved error_debug.png")
            except Exception:
                pass
        finally:
            try:
                await context.close()
            except Exception:
                pass
            await browser.close()

# -------- Dummy FastAPI Server --------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive", "message": "Render service is up!"}

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# -------- Main --------
if __name__ == "__main__":
    import threading
    threading.Thread(target=start_dummy_server, daemon=True).start()

    headless_flag = os.environ.get("HEADLESS", "1") not in ("0", "false", "False")
    asyncio.run(run_once(headless=headless_flag))

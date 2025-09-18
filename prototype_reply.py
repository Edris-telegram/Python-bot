# prototype_reply_with_dummy_web.py
import time
import os
import json
from playwright.sync_api import sync_playwright
from fastapi import FastAPI
import threading
import uvicorn

# -------- CONFIG --------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # can be raw auth_token, cookie string, or path to cookies.json
TWEET_URL = "https://x.com/Maldris15559/status/1924175415939121331"
FIXED_MESSAGE = "Prototype reply — testing ✅"
# ------------------------

def parse_cookie_input(cookie_input):
    """
    Accept:
      - raw auth_token
      - full cookie string "name=val; name2=val2"
      - path to cookies.json
    Returns list of cookie dicts suitable for context.add_cookies([...]).
    """
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

def try_selectors(page, selectors, timeout=5000):
    """Wait for the first selector that appears."""
    for sel in selectors:
        try:
            handle = page.wait_for_selector(sel, timeout=timeout)
            if handle:
                return sel
        except Exception:
            continue
    return None

def run_once(headless=True):
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var (auth_token, cookie string, or cookies.json path).")
        return

    cookies = parse_cookie_input(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie input.")
        return

    print("Starting Playwright... (first run may download Chromium)")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context()
        try:
            context.add_cookies(cookies)
            print("[🍪] Cookies applied")

            page = context.new_page()

            # Visit home to apply cookies
            print("[→] Visiting home...")
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # Open the tweet page
            print(f"[→] Opening tweet: {TWEET_URL}")
            page.goto(TWEET_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # Try common textbox selectors
            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]

            sel = try_selectors(page, textbox_selectors, timeout=7000)

            # If no textbox, attempt to click reply button
            if not sel:
                reply_buttons = [
                    "div[data-testid='reply']",
                    "div[role='button'][data-testid='reply']",
                    "a[href$='/reply']",
                ]
                rb = try_selectors(page, reply_buttons, timeout=5000)
                if rb:
                    try:
                        print(f"[→] Clicking reply button ({rb})...")
                        page.click(rb)
                        time.sleep(1.5)
                        sel = try_selectors(page, textbox_selectors, timeout=7000)
                    except Exception as e:
                        print(f"[⚠️] Failed clicking reply button: {e}")

            if not sel:
                print("⚠️ Reply textbox not found — likely cookie issue.")
                page.screenshot(path="debug_tweet.png")
                print("Saved debug_tweet.png")
                return

            print(f"[→] Using textbox selector: {sel}")
            page.click(sel)
            time.sleep(0.3)
            page.fill(sel, FIXED_MESSAGE)
            time.sleep(0.4)

            # Try send button selectors
            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']",
                "div[role='button'][data-testid='tweetButton']",
            ]
            sent = False
            for s in send_selectors:
                try:
                    btn = page.wait_for_selector(s, timeout=5000)
                    if btn:
                        print(f"[→] Clicking send button ({s})")
                        btn.click()
                        sent = True
                        break
                except Exception:
                    continue

            if not sent:
                # fallback - keyboard submit
                try:
                    print("[→] Fallback: Ctrl+Enter submit")
                    page.keyboard.down("Control")
                    page.keyboard.press("Enter")
                    page.keyboard.up("Control")
                    sent = True
                except Exception as e:
                    print(f"[❌] Keyboard fallback failed: {e}")

            if sent:
                print("[✔] Reply submitted. Waiting a few seconds...")
                time.sleep(5)
                print("[✔] Done (check tweet).")
            else:
                print("❌ Could not send reply. Screenshotting...")
                page.screenshot(path="error_debug.png")
                print("Saved error_debug.png")

        except Exception as e:
            print("❌ Exception during run:", e)
            try:
                page.screenshot(path="error_debug.png")
                print("Saved error_debug.png")
            except Exception:
                pass
        finally:
            try:
                context.close()
            except Exception:
                pass
            browser.close()

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
    # Start dummy web server in a background thread
    threading.Thread(target=start_dummy_server, daemon=True).start()

    # Run Playwright code exactly as before
    headless_flag = os.environ.get("HEADLESS", "1") not in ("0", "false", "False")
    run_once(headless=headless_flag)

# prototype_reply.py
import time
import os
from playwright.sync_api import sync_playwright

# -------- CONFIG --------
# Put your cookie value here (auth_token string, or full cookie string "name=val; name2=val2")
# For safety put cookie into an env var and read it instead of hardcoding.
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # better: set this in env
TWEET_URL = "https://x.com/username/status/1234567890123456789"  # replace with the target tweet
FIXED_MESSAGE = "Prototype reply — testing ✅"  # message to post
# ------------------------

def parse_cookie_string(cookie_str):
    """
    Accept either a raw token (like 'abc...') for auth_token,
    or a full cookie string "name=val; name2=val2".
    Returns list of cookie dicts suitable for context.add_cookies([...]).
    """
    if not cookie_str:
        return []
    cookie_str = cookie_str.strip()
    if "=" not in cookie_str:
        # treat as auth_token only
        return [{"name": "auth_token", "value": cookie_str, "domain": ".twitter.com", "path": "/", "httpOnly": True, "secure": True}]
    parts = [p.strip() for p in cookie_str.split(";") if p.strip()]
    cookies = []
    for p in parts:
        if "=" in p:
            name, val = p.split("=", 1)
            cookies.append({"name": name.strip(), "value": val.strip(), "domain": ".twitter.com", "path": "/", "httpOnly": False, "secure": True})
    return cookies

def main():
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var to your cookie/auth_token.")
        return

    cookies = parse_cookie_string(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        try:
            # add cookies
            context.add_cookies(cookies)
            page = context.new_page()

            # go to twitter home to apply cookie
            page.goto("https://x.com/home", wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # open the tweet
            print(f"[→] Opening tweet: {TWEET_URL}")
            page.goto(TWEET_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Try to find reply box
            # Twitter/X uses different selectors; try a few common ones
            textbox_selectors = [
                "div[aria-label='Tweet text']",                     # older
                "div[role='textbox'][contenteditable='true']",      # generic
                "div[aria-label='Reply to Tweet'] div[role='textbox']"
            ]

            textbox = None
            for sel in textbox_selectors:
                try:
                    textbox = page.query_selector(sel)
                    if textbox:
                        break
                except:
                    textbox = None

            if not textbox:
                print("⚠️ Reply textbox not found — page layout may differ or cookie not logged in.")
                # Optionally, dump screenshot for debugging
                page.screenshot(path="debug_tweet.png")
                print("Saved debug_tweet.png")
                browser.close()
                return

            # Click and type
            textbox.click()
            time.sleep(0.5)
            textbox.fill(FIXED_MESSAGE)
            time.sleep(0.5)

            # Find tweet/send button
            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']"
            ]
            sent = False
            for s in send_selectors:
                try:
                    btn = page.query_selector(s)
                    if btn:
                        btn.click()
                        sent = True
                        break
                except Exception as e:
                    continue

            if not sent:
                # fallback: press Ctrl+Enter
                page.keyboard.down("Control")
                page.keyboard.press("Enter")
                page.keyboard.up("Control")
                sent = True

            if sent:
                print("[✔] Reply action attempted. Waiting a few seconds...")
                time.sleep(5)
                print("[✔] Done (check the tweet).")
            else:
                print("❌ Could not trigger send button.")

        except Exception as e:
            print("❌ Exception:", e)
            page.screenshot(path="error_debug.png")
            print("Saved error_debug.png")
        finally:
            browser.close()

if __name__ == "__main__":
    main()

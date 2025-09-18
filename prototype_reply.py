# prototype_reply.py
import time
import os
from playwright.sync_api import sync_playwright

# -------- CONFIG --------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # set this env var before running
TWEET_URL = "https://x.com/Maldris15559/status/1924175415939121331"  # fixed tweet link
FIXED_MESSAGE = "Prototype reply — testing ✅"
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
    # If it's just a bare token (no '=') treat as auth_token
    if "=" not in cookie_str:
        return [{
            "name": "auth_token",
            "value": cookie_str,
            "domain": ".twitter.com",
            "path": "/",
            "httpOnly": True,
            "secure": True
        }]
    parts = [p.strip() for p in cookie_str.split(";") if p.strip()]
    cookies = []
    for p in parts:
        if "=" in p:
            name, val = p.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": val.strip(),
                "domain": ".twitter.com",
                "path": "/",
                "httpOnly": False,
                "secure": True
            })
    return cookies

def try_selectors(page, selectors, timeout=3000):
    """Return the first selector string that matches (or None)."""
    for sel in selectors:
        try:
            handle = page.query_selector(sel)
            if handle:
                return sel
        except Exception:
            continue
    return None

def main():
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var to your cookie/auth_token.")
        return

    cookies = parse_cookie_string(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie.")
        return

    print("Starting Playwright... (first run will download browsers if needed)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        try:
            # Add cookies to context
            context.add_cookies(cookies)
            page = context.new_page()

            # Navigate to home so cookie is applied
            print("[→] Visiting home to apply cookie...")
            page.goto("https://x.com/home", wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Open the tweet URL
            print(f"[→] Opening tweet: {TWEET_URL}")
            page.goto(TWEET_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Common selectors for reply/textbox
            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply to Tweet'] div[role='textbox']",
                "div[aria-label='Tweet text area']",
            ]

            sel = try_selectors(page, textbox_selectors)
            if not sel:
                # Try to click a reply button to open box, then retry
                possible_reply_buttons = [
                    "div[data-testid='reply']", "div[role='button'][data-testid='reply']",
                    "a[href$='/reply']"
                ]
                rb = try_selectors(page, possible_reply_buttons)
                if rb:
                    try:
                        print("[→] Clicking reply button to open textbox...")
                        page.click(rb)
                        time.sleep(1.2)
                        sel = try_selectors(page, textbox_selectors)
                    except Exception as e:
                        print("Failed to click reply button:", e)

            if not sel:
                print("⚠️ Reply textbox not found — layout may differ or cookie not logged in.")
                page.screenshot(path="debug_tweet.png")
                print("Saved debug_tweet.png")
                return

            print(f"[→] Using textbox selector: {sel}")
            # Click into the textbox and type
            page.click(sel)
            time.sleep(0.3)
            page.fill(sel, FIXED_MESSAGE)
            time.sleep(0.4)

            # Try send buttons
            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']",
                "div[role='button'][data-testid='tweetButton']"
            ]
            sent = False
            for s in send_selectors:
                try:
                    btn = page.query_selector(s)
                    if btn:
                        print(f"[→] Clicking send button selector: {s}")
                        btn.click()
                        sent = True
                        break
                except Exception:
                    continue

            if not sent:
                # fallback: keyboard submit
                try:
                    print("[→] Falling back to Ctrl+Enter keyboard submit")
                    page.keyboard.down("Control")
                    page.keyboard.press("Enter")
                    page.keyboard.up("Control")
                    sent = True
                except Exception as e:
                    print("Fallback keyboard submit failed:", e)
                    sent = False

            if sent:
                print("[✔] Reply action attempted. Waiting a few seconds...")
                time.sleep(5)
                print("[✔] Done (check the tweet).")
            else:
                print("❌ Could not trigger send action. Saved debug screenshot.")
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

if __name__ == "__main__":
    main()            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
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
                except Exception:
                    continue

            if not sent:
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
    main()            # Twitter/X uses different selectors; try a few common ones
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

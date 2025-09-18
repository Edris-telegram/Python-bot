import time
import os
import json
import threading
import socket
from playwright.sync_api import sync_playwright

# -------- CONFIG --------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # auth_token, cookie string, or path to cookies.json
PORT = int(os.environ.get("PORT", 10000))        # Render-assigned port
# ------------------------

# Storage for the latest raid info
latest_raid = {"tweet_url": None, "message": None}


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
            cookies.append({"name": name.strip(), "value": val.strip(), "domain": ".x.com", "path": "/"})
    return cookies


def try_selectors(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            handle = page.wait_for_selector(sel, timeout=timeout)
            if handle:
                return sel
        except Exception:
            continue
    return None


def run_once(headless=True):
    tweet_url = latest_raid.get("tweet_url")
    message = latest_raid.get("message")

    if not tweet_url or not message:
        print("⚠️ No raid data received yet.")
        return

    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var.")
        return

    cookies = parse_cookie_input(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie input.")
        return

    print("Starting Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        try:
            context.add_cookies(cookies)
            print("[🍪] Cookies applied")
            page = context.new_page()

            print("[→] Visiting home...")
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            print(f"[→] Opening tweet: {tweet_url}")
            page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]
            sel = try_selectors(page, textbox_selectors, timeout=7000)

            if not sel:
                reply_buttons = [
                    "div[data-testid='reply']",
                    "div[role='button'][data-testid='reply']",
                    "a[href$='/reply']",
                ]
                rb = try_selectors(page, reply_buttons, timeout=5000)
                if rb:
                    print(f"[→] Clicking reply button ({rb})...")
                    page.click(rb)
                    time.sleep(1.5)
                    sel = try_selectors(page, textbox_selectors, timeout=7000)

            if not sel:
                print("⚠️ Reply textbox not found.")
                page.screenshot(path="debug_tweet.png")
                print("Saved debug_tweet.png")
                return

            print(f"[→] Using textbox selector: {sel}")
            page.click(sel)
            time.sleep(0.3)
            page.fill(sel, message)
            time.sleep(0.4)

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
                print("[→] Fallback: Ctrl+Enter submit")
                page.keyboard.down("Control")
                page.keyboard.press("Enter")
                page.keyboard.up("Control")
                sent = True

            if sent:
                print("[✔] Reply submitted. Done.")
                time.sleep(3)
        finally:
            context.close()
            browser.close()


def loop_runner():
    while True:
        try:
            run_once(headless=True)
        except Exception as e:
            print(f"❌ Exception in runner: {e}")
        time.sleep(30)  # check every 30s


def heartbeat():
    """Fake server so Render sees the service as alive"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", PORT))
    s.listen(1)
    print(f"[💓] Heartbeat socket running on port {PORT}")
    while True:
        conn, addr = s.accept()
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nService alive")
        conn.close()


if __name__ == "__main__":
    threading.Thread(target=loop_runner, daemon=True).start()
    heartbeat()

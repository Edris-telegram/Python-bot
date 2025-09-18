# dynamic_reply.py
import time
import os
import json
import threading
from fastapi import FastAPI, Request
import uvicorn
from playwright.sync_api import sync_playwright

# -------- CONFIG --------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # raw auth_token, cookie string, or path to cookies.json
TASK_FILE = "task.json"
# ------------------------

app = FastAPI()
lock = threading.Lock()

def save_task(url, message):
    with lock:
        with open(TASK_FILE, "w") as f:
            json.dump({"url": url, "message": message}, f)
    print(f"[🆕] Task saved: {url} | {message}")

def load_task():
    if not os.path.exists(TASK_FILE):
        return None
    with lock:
        with open(TASK_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return None

def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []

    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            return json.load(f)

    if "=" not in cookie_input:
        return [{
            "name": "auth_token",
            "value": cookie_input.strip(),
            "domain": ".x.com",
            "path": "/"
        }]

    parts = [p.strip() for p in cookie_input.split(";") if p.strip()]
    return [{"name": name.strip(), "value": val.strip(), "domain": ".x.com", "path": "/"}
            for name, val in (p.split("=", 1) for p in parts)]

def try_selectors(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            handle = page.wait_for_selector(sel, timeout=timeout)
            if handle:
                return sel
        except:
            continue
    return None

def run_once(tweet_url, message, headless=True):
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var.")
        return

    cookies = parse_cookie_input(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie input.")
        return

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
                    page.click(rb)
                    time.sleep(1.5)
                    sel = try_selectors(page, textbox_selectors, timeout=7000)

            if not sel:
                print("⚠️ Reply textbox not found. Saved debug screenshot.")
                page.screenshot(path="debug_tweet.png")
                return

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
            for s in send_selectors:
                try:
                    btn = page.wait_for_selector(s, timeout=5000)
                    if btn:
                        btn.click()
                        print("[✔] Reply submitted.")
                        time.sleep(5)
                        return
                except:
                    continue

            print("❌ Could not send reply, screenshotting...")
            page.screenshot(path="error_debug.png")

        finally:
            try:
                context.close()
            except:
                pass
            browser.close()

def worker_loop():
    while True:
        task = load_task()
        if task:
            url, msg = task.get("url"), task.get("message")
            if url and msg:
                print(f"[▶] Running task: {url} | {msg}")
                run_once(url, msg)
                os.remove(TASK_FILE)  # clear after run
        time.sleep(10)

@app.post("/new-task")
async def new_task(req: Request):
    data = await req.json()
    url = data.get("url")
    msg = data.get("message")
    if not url or not msg:
        return {"status": "error", "reason": "url and message required"}
    save_task(url, msg)
    return {"status": "ok", "url": url, "message": msg}

if __name__ == "__main__":
    # Start worker in background
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    # Run FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

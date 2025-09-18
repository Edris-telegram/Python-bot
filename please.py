# full_raid_bot_render.py
import re
import os
import json
import random
import time
from datetime import datetime, timezone
from telethon import TelegramClient, events, functions
from playwright.sync_api import sync_playwright
from fastapi import FastAPI
import threading
import uvicorn

# ------------------ CONFIG ------------------
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION = os.environ.get("SESSION_FILE", "session.session")
WATCH_GROUPS = [int(g) for g in os.environ.get("WATCH_GROUPS", "-1002786329549").split(",")]

COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")
HEADLESS = os.environ.get("HEADLESS", "1") not in ("0", "false", "False")

MESSAGES_FILE = os.environ.get("MESSAGES_FILE", "messages.txt")
TRIAL_REPLIES = [
    "Smash ✅🔥", "In! 🚀", "Let’s go fam 💯",
    "Replying as a test ⚡", "Trial reply — automated"
]

LOG_FILE = os.environ.get("LOG_FILE", "raid_training_data.json")

TWEET_RE = re.compile(r"(https?://(?:x\.com|twitter\.com)/[^\s]+)", re.IGNORECASE)
# --------------------------------------------

# ------------------ Utilities ------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
    with open(path, "r+", encoding="utf-8") as f:
        try:
            arr = json.load(f)
        except Exception:
            arr = []
        arr.append(entry)
        f.seek(0)
        json.dump(arr, f, indent=2)
        f.truncate()

def extract_tweet(text):
    m = TWEET_RE.search(text or "")
    return m.group(1) if m else None

def get_random_message(file_path=MESSAGES_FILE):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if lines:
                return random.choice(lines)
        except Exception:
            pass
    return random.choice(TRIAL_REPLIES)

def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []
    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    if "=" not in cookie_input:
        return [{"name": "auth_token", "value": cookie_input.strip(), "domain": ".x.com", "path": "/"}]
    cookies = []
    for p in [p.strip() for p in cookie_input.split(";") if p.strip()]:
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

# ------------------ Raid Browser ------------------
class RaidBrowser:
    def __init__(self, headless=True):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        cookies = parse_cookie_input(COOKIE_AUTH_TOKEN)
        if cookies:
            self.context.add_cookies(cookies)
        self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

    def send_reply(self, tweet_url, message):
        try:
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]
            sel = try_selectors(self.page, textbox_selectors, timeout=7000)
            if not sel:
                reply_buttons = ["div[data-testid='reply']", "div[role='button'][data-testid='reply']", "a[href$='/reply']"]
                rb = try_selectors(self.page, reply_buttons, timeout=5000)
                if rb:
                    self.page.click(rb)
                    time.sleep(1.5)
                    sel = try_selectors(self.page, textbox_selectors, timeout=7000)
            if not sel:
                self.page.screenshot(path="debug_tweet.png")
                return
            self.page.click(sel)
            time.sleep(0.3)
            self.page.fill(sel, message)
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
                    btn = self.page.wait_for_selector(s, timeout=5000)
                    if btn:
                        btn.click()
                        sent = True
                        break
                except Exception:
                    continue
            if not sent:
                self.page.keyboard.down("Control")
                self.page.keyboard.press("Enter")
                self.page.keyboard.up("Control")
                sent = True
            if sent:
                print("[✔] Reply submitted successfully.")
                time.sleep(3)
        except Exception as e:
            print("❌ Error sending reply:", e)
            self.page.screenshot(path="error_debug.png")

    def close(self):
        self.context.close()
        self.browser.close()
        self.p.stop()

# ------------------ Telegram ------------------
client = TelegramClient(SESSION, API_ID, API_HASH)
raid_browser = RaidBrowser(headless=HEADLESS)

async def click_inline_button(client, message, match_texts=("👊", "Smash", "smash")):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        return {"clicked": False, "reason": "no_buttons"}
    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    return {"clicked": True, "button_text": lbl}
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": str(e)}
    return {"clicked": False, "reason": "no_matching_label"}

@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        if not sender_id or sender_id not in [5994885234]:
            return
        tweet_url = extract_tweet(msg.text)
        click_result = await click_inline_button(client, msg)
        if tweet_url:
            message_to_send = get_random_message()
            raid_browser.send_reply(tweet_url, message_to_send)
        entry = {"time": now_iso(), "chat_id": event.chat_id, "message_id": msg.id, "tweet_url": tweet_url, "smash": click_result}
        save_json_append(LOG_FILE, entry)
    except Exception as e:
        print("❌ Error in handler:", repr(e))

# ------------------ Dummy FastAPI ------------------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive", "message": "Render service is up!"}

def run_api():
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# ------------------ Main ------------------
def main():
    threading.Thread(target=run_api, daemon=True).start()
    client.start()
    client.run_until_disconnected()
    raid_browser.close()

if __name__ == "__main__":
    main()

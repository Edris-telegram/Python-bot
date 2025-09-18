# raid_auto_with_reply.py
import re
import json
import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, functions
from fastapi import FastAPI
import uvicorn
from playwright.async_api import async_playwright

# ------------------ TELEGRAM CONFIG ------------------
API_ID = 27403368
API_HASH = "7cfc7759b82410f5d90641d6a6fc415f"
SESSION = "session"               # session.session
WATCH_GROUPS = [-1002786329549]   # group id(s)
KNOWN_RAID_BOTS = ["raidar"]      # raid bot usernames
LOG_FILE = "raid_training_data.json"

TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Replying as a test ⚡",
    "Trial reply — automated"
]

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

# ------------------ TWITTER CONFIG ------------------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # set as env var
# ----------------------------------------------------

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
    with open(path, "r+") as f:
        try:
            arr = json.load(f)
        except Exception:
            arr = []
        arr.append(entry)
        f.seek(0)
        json.dump(arr, f, indent=2)
        f.truncate()

def extract_tweet(text):
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)  # url, id
    return None, None

def get_random_message(file_path="messages.txt"):
    if not os.path.exists(file_path):
        print(f"[⚠️] {file_path} not found. Using default trial replies.", flush=True)
        return random.choice(TRIAL_REPLIES)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return random.choice(TRIAL_REPLIES)
        return random.choice(lines)
    except Exception as e:
        print(f"[⚠️] Error reading {file_path}: {e}", flush=True)
        return random.choice(TRIAL_REPLIES)

client = TelegramClient(SESSION, API_ID, API_HASH)

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        print("[🔘] No inline buttons found", flush=True)
        return {"clicked": False, "reason": "no_buttons"}

    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    print(f"[🔘] Clicking button: {lbl}", flush=True)
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

# ------------------ TWITTER REPLY FUNCTION (ASYNC) ------------------
def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []
    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                cookies = json.load(f)
                return cookies
            except Exception:
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

async def try_selectors(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            handle = await page.wait_for_selector(sel, timeout=timeout)
            if handle:
                return sel
        except Exception:
            continue
    return None

async def reply_to_tweet(tweet_url, message, headless=True):
    cookie_str = COOKIE_AUTH_TOKEN
    if not cookie_str:
        print("ERROR: No cookie found. Set TW_COOKIE env var.", flush=True)
        return
    cookies = parse_cookie_input(cookie_str)
    if not cookies:
        print("ERROR: Failed to parse cookie input.", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context()
        try:
            await context.add_cookies(cookies)
            page = await context.new_page()
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            await page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]
            sel = await try_selectors(page, textbox_selectors, timeout=7000)
            if not sel:
                print("❌ Could not find textbox selector.", flush=True)
                return
            await page.click(sel)
            await page.fill(sel, message)
            await asyncio.sleep(0.5)

            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']",
                "div[role='button'][data-testid='tweetButton']",
            ]
            btn_sel = await try_selectors(page, send_selectors, timeout=5000)
            if btn_sel:
                await page.click(btn_sel)
                await asyncio.sleep(3)
                print("✅ Tweet posted!", flush=True)
            else:
                print("❌ Could not find send button.", flush=True)

        except Exception as e:
            print("❌ Exception during reply:", e, flush=True)
        finally:
            try:
                await context.close()
            except Exception:
                pass
            await browser.close()

# ------------------ FASTAPI DUMMY SERVER ------------------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive", "message": "Service is running"}

# ------------------ TELEGRAM HANDLER ------------------
@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        if not sender_id or sender_id not in [5994885234]:
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        print(f"\n🚨 [RAID DETECTED] Tweet: {tweet_url}", flush=True)

        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        message_to_send = get_random_message()

        # Call Twitter reply using async
        print(f"[🐦] Replying to {tweet_url} with message: {message_to_send}", flush=True)
        await reply_to_tweet(tweet_url, message_to_send)

        entry = {
            "time": now_iso(),
            "chat_id": event.chat_id,
            "message_id": msg.id,
            "tweet_url": tweet_url,
            "smash": click_result,
            "message": message_to_send
        }
        save_json_append(LOG_FILE, entry)

    except Exception as e:
        print("❌ Error in handler:", repr(e), flush=True)

# ------------------ MAIN ------------------
async def main():
    print("🚀 Starting raid_auto_with_reply...", flush=True)
    # Start FastAPI server in background
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), log_level="info")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    # Start Telegram client
    await client.start()
    print("✅ Connected to Telegram. Waiting for raids...", flush=True)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())

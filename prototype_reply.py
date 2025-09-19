# raid_auto_with_reply_verbose.py
import re
import json
import os
import random
import time
import traceback
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, functions
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from fastapi import FastAPI
import threading
import uvicorn

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
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)  # url, id
    return None, None

def get_random_message(file_path="messages.txt"):
    if not os.path.exists(file_path):
        print(f"[⚠️] {file_path} not found. Using default trial replies.")
        return random.choice(TRIAL_REPLIES)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return random.choice(TRIAL_REPLIES)
        return random.choice(lines)
    except Exception as e:
        print(f"[⚠️] Error reading {file_path}: {e}")
        return random.choice(TRIAL_REPLIES)

client = TelegramClient(SESSION, API_ID, API_HASH)

async def click_inline_button(client, message, match_texts=("👊",)):
    print("[🔘] Searching for inline buttons...")
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        print("[🔘] No inline buttons found")
        return {"clicked": False, "reason": "no_buttons"}

    print("[🔘] Buttons found (printing labels):")
    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", None)
            url = getattr(btn, "url", None)
            print(f"    Label: {lbl} | URL: {url}")

    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    print(f"[🔘] Attempting to click button: {lbl}")
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    print(f"[🔘] Click result: {res}")
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    print(f"[🔘] Error clicking {lbl}: {e}")
                    traceback.print_exc()
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    print("[🔘] No matching label found among buttons")
    return {"clicked": False, "reason": "no_matching_label"}

# ------------------ TWITTER REPLY FUNCTION (VERY VERBOSE) ------------------
def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []
    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                cookies = json.load(f)
                print(f"[🍪] Loaded {len(cookies)} cookies from JSON file '{cookie_input}'")
                return cookies
            except Exception as e:
                print(f"[❌] Failed reading cookies.json: {e}")
                return []
    if "=" not in cookie_input:
        print("[🍪] Cookie input looks like a raw auth_token")
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
    print(f"[🍪] Parsed {len(cookies)} cookies from cookie string")
    return cookies

def try_selectors_with_debug(page, selectors, timeout=5000):
    """Try selectors with debug prints; returns the first that matches or None."""
    for sel in selectors:
        print(f"[🔎] Checking selector: {sel} (waiting up to {timeout}ms)")
        try:
            handle = page.wait_for_selector(sel, timeout=timeout)
            if handle:
                print(f"[🔎] Selector matched: {sel}")
                return sel
            else:
                print(f"[🔎] Selector did not match (no handle returned): {sel}")
        except PlaywrightTimeoutError:
            print(f"[🔎] Timeout waiting for selector: {sel}")
        except Exception as e:
            print(f"[🔎] Error while checking selector {sel}: {e}")
            traceback.print_exc()
    return None

def reply_to_tweet(tweet_url, message, headless=True):
    # (unchanged, still your verbose Playwright workflow)
    # ...
    pass  # keeping short here to focus on handler changes
    # but in your file, keep the full function body

# ------------------ FASTAPI DUMMY SERVER ------------------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive", "message": "Service is running"}

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"[🌐] Starting dummy server on port {port} (uvicorn)...")
    uvicorn.run(app, host="0.0.0.0", port=port)

# ------------------ TELEGRAM HANDLER (FIXED) ------------------
@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        print("\n==================== [NEW TELEGRAM MESSAGE] ====================")
        print(f"[📝] Raw message text: {msg.text!r}")
        print(f"[👤] Sender ID: {sender_id}")
        print("===============================================================")

        # Only process raid bot messages
        if not sender_id or sender_id not in [5994885234]:
            print(f"[DEBUG] Ignored message from sender ID: {sender_id}")
            return

        # Extract tweet
        tweet_url, tweet_id = extract_tweet(msg.text or "")
        print(f"\n🚨 [RAID DETECTED] Tweet URL: {tweet_url}, Tweet ID: {tweet_id}")

        # Smash button
        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        print(f"[🔘] Button click result: {click_result}")

        # Pick a reply
        message_to_send = get_random_message()
        print(f"[💬] Selected reply message: {message_to_send}")

        # Run Twitter reply in executor (avoids sync/async clash)
        loop = asyncio.get_event_loop()
        print(f"[🐦] Scheduling reply_to_tweet for {tweet_url} ...")
        success = await loop.run_in_executor(
            None,
            lambda: reply_to_tweet(
                tweet_url,
                message_to_send,
                headless=(os.environ.get("HEADLESS", "1") != "0")
            )
        )
        print(f"[🐦] Reply success: {success}")

        # Save log
        entry = {
            "time": now_iso(),
            "chat_id": event.chat_id,
            "message_id": msg.id,
            "tweet_url": tweet_url,
            "smash": click_result,
            "message": message_to_send,
            "reply_success": success
        }
        save_json_append(LOG_FILE, entry)
        print("[💾] Log entry saved.")

    except Exception as e:
        print("❌ Error in handler:", repr(e))
        traceback.print_exc()

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting raid_auto_with_reply_verbose...")
    threading.Thread(target=start_dummy_server, daemon=True).start()
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()

# raid_auto_full_verbose_fixed.py
import re
import json
import os
import random
from datetime import datetime
from telethon import TelegramClient, events, functions, Button

# ------------------ CONFIG ------------------
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
# --------------------------------------------

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

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

# ------------------ NEW: pick random message from messages.txt ------------------
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
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        print("[🔘] No inline buttons found")
        return {"clicked": False, "reason": "no_buttons"}

    print("[🔘] Buttons found:")
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
                    print(f"[🔘] Clicking button: {lbl}")
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    print(f"[🔘] ✅ {lbl} button clicked")
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    print(f"[🔘] ❌ Error clicking {lbl}: {e}")
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

# ------------------ DEBUG HANDLER ------------------
@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        # Debug prints for every message in the watched group
        print(f"\n[DEBUG] chat_id={event.chat_id} | sender_id={sender_id} | message_id={msg.id}")
        print(f"Message text preview: {msg.text[:100] if msg.text else 'No text'}")

        if not sender_id or sender_id not in [5994885234]:  # only allow your raid bot ID
            print("[DEBUG] Sender not the raid bot. Ignoring.")
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        print(f"\n🚨 [RAID DETECTED] msg_id={msg.id} | Tweet: {tweet_url}")

        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        print("🔘 Button click result:", click_result)

        message_to_send = get_random_message()  # still pick message for logging

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
        print("❌ Error in handler:", repr(e))
# --------------------------------------------

def main():
    print("🚀 Starting raid_auto_full_verbose_fixed...")
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()

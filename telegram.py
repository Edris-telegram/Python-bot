# raid_auto_twitter.py
import re
import json
import os
import random
from datetime import datetime
from telethon import TelegramClient, events, functions
import tweepy
from twilio.rest import Client as TwilioClient  # <-- Twilio import

# ------------------ TELEGRAM CONFIG ------------------
API_ID = "27403368"
API_HASH = "7cfc7759b82410f5d90641d6fc415f"
SESSION = "session"               # session.session
RAID_BOT_IDS = [5994885234]       # allowed raid bot ID(s)
LOG_FILE = "raid_training_data.json"

# ------------------ GROUP CONFIG ------------------
CONFIG_FILE = "groups_config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        GROUPS_CONFIG = json.load(f)
else:
    GROUPS_CONFIG = {}

WATCH_GROUPS = [int(gid) for gid in GROUPS_CONFIG.keys()]

# ------------------ TWITTER CONFIG ------------------
API_KEY = "OwRbI9wi8eglE4yAxeiJgdtBr"
API_SECRET = "HenKDXkitpno7Ciiql1FWuq1aDVuGamocqu2gswHfDMe7j6qjk"
ACCESS_TOKEN = "1917680783331930112-VFp1mvpIqq5xYfxBbG3IiWLPbCJrc9"
ACCESS_TOKEN_SECRET = "TjIVuZrh0Re7KdkCCsKwuUtTmFSU18UNvuq4tBxSHhh3h"
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAAALU24QEAAAAA%2BJgMXUnzs6YRb2w5iEw4E%2FXtgkM%3DVThVeUHqvPH4EAyEqXdTLYzlfOXD8bPBwoCx52xkflPJyf8Nop"

# ==== Authenticate Tweepy v2 client ====
twitter_client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# ------------------ TWILIO CONFIG ------------------
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
VERIFIED_NUMBER = os.getenv("VERIFIED_PHONE_NUMBER")

twilio_client = TwilioClient(TWILIO_SID, TWILIO_AUTH)

def call_alert():
    """Place a call via Twilio to warn about API limit."""
    if not all([TWILIO_SID, TWILIO_AUTH, TWILIO_NUMBER, VERIFIED_NUMBER]):
        print("❌ Missing Twilio environment variables, cannot place call.")
        return
    try:
        call = twilio_client.calls.create(
            to=VERIFIED_NUMBER,
            from_=TWILIO_NUMBER,
            twiml='<Response><Say>Warning. Twitter API limit almost reached.</Say></Response>'
        )
        print(f"[📞] Call triggered: {call.sid}")
    except Exception as e:
        print("❌ Twilio call error:", e)

# ------------------ HELPERS ------------------
TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Trial reply — automated"
]

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

sent_tweet_ids = set()  # avoid duplicate replies
tweet_count = 0
TWEET_LIMIT = 17  # adjust if you know your exact free API cap
ALERT_THRESHOLD = 3

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
        return m.group(1), m.group(2)
    return None, None

def get_random_message(chat_id=None):
    file_path = "messages.txt"  # default

    if chat_id and str(chat_id) in GROUPS_CONFIG:
        file_path = GROUPS_CONFIG[str(chat_id)]

    if not os.path.exists(file_path):
        print(f"[⚠️] {file_path} not found for chat {chat_id}. Using default trial replies.")
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

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        return {"clicked": False, "reason": "no_buttons"}

    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    print(f"[🔘] ✅ Clicked: {lbl}")
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

def reply_on_twitter(tweet_url, tweet_id, reply_text):
    global tweet_count
    try:
        response = twitter_client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet_id
        )
        tweet_count += 1
        print(f"✅ Replied to {tweet_url}: {reply_text} (Count: {tweet_count})")

        # Check threshold
        if TWEET_LIMIT - tweet_count <= ALERT_THRESHOLD:
            call_alert()

        return response.data
    except Exception as e:
        print("❌ Twitter error:", e)
        return None

# ------------------ TELEGRAM HANDLER ------------------
client = TelegramClient(SESSION, API_ID, API_HASH)

@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        if not sender_id or sender_id not in RAID_BOT_IDS:
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        if not tweet_id:
            return

        print(f"\n🚨 [RAID DETECTED] Tweet: {tweet_url}")

        # Click smash
        click_result = await click_inline_button(client, msg, match_texts=("👊",))

        # Prepare message
        message_to_send = get_random_message(event.chat_id)

        if tweet_id not in sent_tweet_ids:
            sent_tweet_ids.add(tweet_id)
            twitter_data = reply_on_twitter(tweet_url, tweet_id, message_to_send)
        else:
            print(f"[⚠️] Already replied: {tweet_url}")
            twitter_data = None

        entry = {
            "time": now_iso(),
            "chat_id": event.chat_id,
            "message_id": msg.id,
            "tweet_url": tweet_url,
            "tweet_id": tweet_id,
            "smash": click_result,
            "reply": message_to_send,
            "twitter_response": twitter_data
        }
        save_json_append(LOG_FILE, entry)

    except Exception as e:
        print("❌ Handler error:", repr(e))

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting raid_auto_twitter...")
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()

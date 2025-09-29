# raid_auto_twitter.py
import re
import json
import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, functions
from telethon.errors import FloodWaitError
import tweepy
from twilio.rest import Client as TwilioClient

# ------------------ TELEGRAM CONFIG ------------------
API_ID = 27403368                       # integer
API_HASH = "7cfc7759b82410f5d90641d6fc415f"
SESSION = "session"
RAID_BOT_IDS = [5994885234]
LOG_FILE = "raid_training_data.json"

# ------------------ GROUP CONFIG ------------------
CONFIG_FILE = "groups_config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        GROUPS_CONFIG = json.load(f)    # expected shape: { "<chat_id>": "<messages_file_path_or_empty>" }
else:
    GROUPS_CONFIG = {}

# WATCH_GROUPS are the configured keys (convert to int)
WATCH_GROUPS = [int(gid) for gid in GROUPS_CONFIG.keys()]

# ------------------ LOAD TWITTER ACCOUNTS ------------------
with open("twitter_accounts.json", "r", encoding="utf-8") as f:
    TWITTER_ACCOUNTS = json.load(f)

current_account_index = 0

def get_twitter_client():
    creds = TWITTER_ACCOUNTS[current_account_index]
    return tweepy.Client(
        bearer_token=creds["BEARER_TOKEN"],
        consumer_key=creds["API_KEY"],
        consumer_secret=creds["API_SECRET"],
        access_token=creds["ACCESS_TOKEN"],
        access_token_secret=creds["ACCESS_TOKEN_SECRET"]
    )

twitter_client = get_twitter_client()

# ------------------ TWILIO CONFIG ------------------
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
VERIFIED_NUMBER = os.getenv("VERIFIED_PHONE_NUMBER")

twilio_client = TwilioClient(TWILIO_SID, TWILIO_AUTH) if TWILIO_SID and TWILIO_AUTH else None

def call_alert():
    """Place a call via Twilio to warn about API limit and rotate account."""
    global current_account_index, twitter_client, tweet_count
    if not twilio_client:
        print("[⚠️] Twilio not configured; cannot call alert.")
        return

    try:
        call = twilio_client.calls.create(
            to=VERIFIED_NUMBER,
            from_=TWILIO_NUMBER,
            twiml='<Response><Say>Warning. Twitter API limit almost reached. Switching account now.</Say></Response>'
        )
        print(f"[📞] Call triggered: {call.sid}")

        # Rotate account after call
        current_account_index = (current_account_index + 1) % len(TWITTER_ACCOUNTS)
        twitter_client = get_twitter_client()
        tweet_count = 0  # reset after switching
        print(f"[🔄] Switched to Twitter account #{current_account_index + 1}")

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

sent_tweet_ids = set()
tweet_count = 0
TWEET_LIMIT = 17  # tweak per-account limit
ALERT_THRESHOLD = 1  # when remaining tweets <= this, trigger alert

# per-group cooldown (seconds)
LAST_REPLY = {}
GROUP_COOLDOWN_SECONDS = 10

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
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
    """
    Returns:
      - string message (if configured and file exists)
      - None if this group is in manual mode (empty/None path) OR file missing
    """
    if chat_id and str(chat_id) in GROUPS_CONFIG:
        file_path = GROUPS_CONFIG[str(chat_id)]
        # If config value is empty or falsy -> manual mode (no auto-tweet)
        if not file_path:
            # explicit manual mode
            return None
        # otherwise file_path supplied: attempt to read
        if not os.path.exists(file_path):
            print(f"[⚠️] Messages file for group {chat_id} not found at {file_path} — treating as manual mode.")
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            return random.choice(lines) if lines else None
        except Exception as e:
            print(f"[⚠️] Error reading messages file {file_path}: {e} — treating as manual mode.")
            return None

    # If group is not configured (shouldn't happen if WATCH_GROUPS built from config) return None
    return None

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
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except FloodWaitError as e:
                    # Respect Telegram flood wait
                    print(f"⏳ Flood wait from Telegram: sleeping {e.seconds}s...")
                    await asyncio.sleep(e.seconds)
                    # after sleeping, try once more (or continue to next button)
                    try:
                        res = await client(functions.messages.GetBotCallbackAnswerRequest(
                            peer=message.to_id,
                            msg_id=message.id,
                            data=btn.data or b""
                        ))
                        return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                    except Exception as e2:
                        return {"clicked": False, "button_text": lbl, "error": repr(e2)}
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

def reply_on_twitter(tweet_url, tweet_id, reply_text):
    """
    Synchronous wrapper that calls tweepy.Client.create_tweet and manages tweet_count & account rotation alert.
    This function is safe to run in a thread (we call it via asyncio.to_thread).
    """
    global tweet_count
    try:
        response = twitter_client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet_id
        )
        tweet_count += 1
        print(f"✅ Replied to {tweet_url}: {reply_text} (Count: {tweet_count})")

        # Only trigger Twilio when close to hitting limit
        if (TWEET_LIMIT - tweet_count) <= ALERT_THRESHOLD:
            print("[⚠️] Approaching tweet limit — triggering Twilio alert / account rotation.")
            call_alert()

        return response.data
    except Exception as e:
        print("❌ Twitter error:", e)
        return None

async def safe_reply(tweet_url, tweet_id, reply_text):
    """
    Sleep a random interval, then call reply_on_twitter in a thread to avoid blocking the event loop.
    """
    await asyncio.sleep(random.uniform(3, 7))
    return await asyncio.to_thread(reply_on_twitter, tweet_url, tweet_id, reply_text)

# ------------------ TELEGRAM HANDLER ------------------
client = TelegramClient(SESSION, API_ID, API_HASH)

@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    global LAST_REPLY, sent_tweet_ids

    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        if not sender_id or sender_id not in RAID_BOT_IDS:
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        if not tweet_id:
            return

        # per-group cooldown
        now_ts = datetime.utcnow().timestamp()
        if event.chat_id in LAST_REPLY and now_ts - LAST_REPLY[event.chat_id] < GROUP_COOLDOWN_SECONDS:
            print(f"⏳ Skipping (cooldown) for group {event.chat_id}")
            return
        LAST_REPLY[event.chat_id] = now_ts

        print(f"\n🚨 [RAID DETECTED] Tweet: {tweet_url}")

        # Click the smash button if present
        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        print(f"🔘 Smash/callback result: {click_result}")

        # Determine if this group has an associated messages file (auto-reply) or is manual mode
        message_to_send = get_random_message(event.chat_id)

        if message_to_send is None:
            # MANUAL MODE: configured group without messages file (or file missing) -> do NOT tweet
            print(f"[✋] Group {event.chat_id} is in MANUAL mode (no messages file). Not sending Twitter reply.")
            twitter_data = None
        else:
            # AUTOMATED mode: we have a message to post
            if tweet_id not in sent_tweet_ids:
                sent_tweet_ids.add(tweet_id)
                twitter_data = await safe_reply(tweet_url, tweet_id, message_to_send)
            else:
                print(f"[⚠️] Already replied (skipping): {tweet_url}")
                twitter_data = None

        # Log the event
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

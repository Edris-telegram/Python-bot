# raid_auto_twitter.py
# -> Updated to generate Twitter replies using a small Hugging Face model (Inference API).
# Requirements: tweepy, telethon, requests
# Install: pip install tweepy telethon requests python-dotenv

import re
import json
import os
import random
import requests
import time
from datetime import datetime
from telethon import TelegramClient, events, functions
import tweepy

# ------------------ TELEGRAM CONFIG ------------------
API_ID = "27403368"
API_HASH = "7cfc7759b82410f5d90641d6fc415f8"  # keep yours secure
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
# (Your existing keys are left as-is in the file you gave me,
#  but it's strongly recommended to move these to env vars for safety.)
API_KEY = os.getenv("API_KEY") or "OwRbI9wi8eglE4yAxeiJgdtBr"
API_SECRET = os.getenv("API_SECRET") or "HenKDXkitpno7Ciiql1FWuq1aDVuGamocqu2gswHfDMe7j6qjk"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "1917680783331930112-VFp1mvpIqq5xYfxBbG3IiWLPbCJrc9"
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET") or "TjIVuZrh0Re7KdkCCsKwuUtTmFSU18UNvuq4tBxSHhh3h"
BEARER_TOKEN = os.getenv("BEARER_TOKEN") or "AAAAAAAAAAAAAAAAAAAAAAALU24QEAAAAA%2BJgMXUnzs6YRb2w5iEw4E%2FXtgkM%3DVThVeUHqvPH4EAyEqXdTLYzlfOXD8bPBwoCx52xkflPJyf8Nop"

# ==== Authenticate Tweepy v2 client ====
twitter_client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
)

# ------------------ HUGGING FACE (open model) CONFIG ------------------
# Create a Hugging Face access token and put it in HUGGINGFACE_API_TOKEN env var.
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "pszemraj/flan-t5-small-instructiongen")
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# Safety / fallback replies in case API fails
TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Trial reply — automated"
]

# Tweet regex and duplicate tracking
TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)
sent_tweet_ids = set()  # avoid duplicate replies

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

# ------------------ Hugging Face reply generator ------------------
def generate_reply_via_hf(tweet_text: str, max_chars=240) -> str:
    """
    Send tweet_text to the HF Inference API (HF_MODEL) and return a short friendly reply.
    Fallback: one of TRIAL_REPLIES if API fails or no token provided.
    """
    if not tweet_text:
        return random.choice(TRIAL_REPLIES)

    if not HUGGINGFACE_API_TOKEN:
        print("[⚠️] HUGGINGFACE_API_TOKEN not set — falling back to trial replies.")
        return random.choice(TRIAL_REPLIES)

    prompt = (
        "You are a friendly, concise social media commenter. "
        "Given the tweet below, write ONE short reply (1 sentence, <= 240 characters) that is positive, "
        "does NOT include links or ask for DMs/personal info, and uses light emoji if appropriate.\n\n"
        f"Tweet: \"{tweet_text}\"\n\nReply:"
    )

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}",
        "Accept": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 64,
            "temperature": 0.7,
            "top_p": 0.9
        },
    }

    try:
        resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=20)
    except Exception as e:
        print("[⚠️] HF request failed:", e)
        return random.choice(TRIAL_REPLIES)

    if resp.status_code != 200:
        print(f"[⚠️] HF API returned {resp.status_code}: {resp.text}")
        return random.choice(TRIAL_REPLIES)

    try:
        data = resp.json()
        # HF responses vary: sometimes list of dicts with 'generated_text', or list of strings
        text = None
        if isinstance(data, list):
            first = data[0]
            if isinstance(first, dict) and "generated_text" in first:
                text = first["generated_text"]
            elif isinstance(first, str):
                text = first
            elif isinstance(first, dict) and "generated_texts" in first:
                text = first["generated_texts"][0]
        elif isinstance(data, dict) and "generated_text" in data:
            text = data["generated_text"]
        else:
            # fallback: convert full response to string
            text = str(data)

        if not text:
            return random.choice(TRIAL_REPLIES)

        # sanitize and shorten
        text = " ".join(text.strip().splitlines())
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        return text

    except Exception as e:
        print("[⚠️] Error parsing HF response:", e)
        return random.choice(TRIAL_REPLIES)

# ------------------ Twitter helper: fetch tweet text ------------------
def fetch_tweet_text(tweet_id: str) -> str:
    try:
        resp = twitter_client.get_tweet(id=int(tweet_id), tweet_fields=["text"])
        if resp and getattr(resp, "data", None):
            return resp.data.text or ""
    except Exception as e:
        print("❌ Error fetching tweet text:", e)
    return ""

# ------------------ posting helper ------------------
def reply_on_twitter(tweet_url, tweet_id, reply_text):
    try:
        response = twitter_client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=int(tweet_id)
        )
        print(f"✅ Replied to {tweet_url}: {reply_text}")
        return response.data
    except Exception as e:
        print("❌ Twitter error:", e)
        return None

# ------------------ TELEGRAM HANDLERS ------------------
client = TelegramClient(SESSION, API_ID, API_HASH)

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

        # Click smash button (if present)
        click_result = await click_inline_button(client, msg, match_texts=("👊",))

        # Get tweet text from Twitter and generate reply via HF model
        tweet_text = fetch_tweet_text(tweet_id)
        # small safety: if tweet_text is empty, fall back to the original telegram message text
        if not tweet_text:
            tweet_text = (msg.text or "")[:800]

        message_to_send = generate_reply_via_hf(tweet_text)

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

        # small pause after posting (avoid bursts)
        time.sleep(random.uniform(2.0, 5.0))

    except Exception as e:
        print("❌ Handler error:", repr(e))

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting raid_auto_twitter (HF reply mode)...")
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()

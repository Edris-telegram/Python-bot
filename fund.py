# bot.py
import os
import asyncio
import threading
import random
import aiohttp
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from flask import Flask

# ----------------------------
# Load environment variables
# ----------------------------
api_id = int(os.environ.get('API_ID', '0'))
api_hash = os.environ.get('API_HASH')
session_str = os.environ.get('SESSION')   # string session
group = int(os.environ.get('GROUP_ID', '-1003067016330'))
delay_seconds = int(os.environ.get('DELAY_SECONDS', '10'))  # default 10s

hf_token = os.environ.get('HF_TOKEN')  # HuggingFace token
hf_model = os.environ.get('HF_MODEL', 'gpt2')  # small default model

if not api_id or not api_hash or not session_str:
    raise RuntimeError("Missing one of API_ID, API_HASH or SESSION environment variables")

if not hf_token:
    raise RuntimeError("Missing HuggingFace token (HF_TOKEN)")

client = TelegramClient(StringSession(session_str), api_id, api_hash)

# ----------------------------
# HuggingFace text generation
# ----------------------------
async def generate_reply(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{hf_model}"
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {"inputs": prompt, "max_length": 50, "temperature": 0.7}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HF API error: {resp.status} - {text}")
                return "👍"
            data = await resp.json()
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            return "👌"

# ----------------------------
# Telegram bot logic
# ----------------------------
async def main():
    while True:
        try:
            # fetch last 5 messages
            msgs = await client.get_messages(group, limit=5)
            if msgs:
                msg = random.choice(msgs)
                if msg.text:
                    print(f"Picked: {msg.text}")
                    reply_text = await generate_reply(msg.text)
                    try:
                        await client.send_message(group, reply_text, reply_to=msg.id)
                        print(f"Replied with: {reply_text}")
                    except errors.FloodWaitError as e:
                        print(f"Flood wait: Sleeping for {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Failed to send reply: {e}")
            await asyncio.sleep(delay_seconds)
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(5)

async def run():
    async with client:
        await main()

# ----------------------------
# Flask web server (for Render)
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ----------------------------
# Run bot and Flask together
# ----------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

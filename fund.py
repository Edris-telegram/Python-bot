# bot.py
import os
import asyncio
import threading
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from flask import Flask

# ----------------------------
# Load environment variables
# ----------------------------
api_id = int(os.environ.get('API_ID', '0'))
api_hash = os.environ.get('API_HASH')
session_str = os.environ.get('SESSION')   # string session you will create
group = int(os.environ.get('GROUP_ID', '-1003067016330'))  # override via env if needed
messages_file = os.environ.get('MESSAGES_FILE', 'messages.txt')
delay_seconds = int(os.environ.get('DELAY_SECONDS', '30'))

if not api_id or not api_hash or not session_str:
    raise RuntimeError("Missing one of API_ID, API_HASH or SESSION environment variables")

client = TelegramClient(StringSession(session_str), api_id, api_hash)

# ----------------------------
# Telegram bot logic
# ----------------------------
async def main():
    with open(messages_file, 'r', encoding='utf-8') as f:
        messages = [line.strip() for line in f if line.strip()]

    for msg in messages:
        try:
            await client.send_message(group, msg)
            print(f"Sent: {msg}")
        except errors.FloodWaitError as e:
            print(f"Flood wait: Sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            await client.send_message(group, msg)
        except Exception as e:
            print(f"Failed to send message: {msg} | Error: {e}")

        await asyncio.sleep(delay_seconds)

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
    # Start Flask server in a thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start Telegram bot without asyncio.run()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

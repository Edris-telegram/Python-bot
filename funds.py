from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import random
import os
from flask import Flask

# ====== Dummy web server to keep Render happy ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# ====== Environment Variables ======
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
TARGET = int(os.getenv("TARGET"))   # Group/User ID
TEXT_FILE = os.getenv("TEXT_FILE", "text.txt")  # default = text.txt

# ====== Client ======
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ====== Load messages ======
try:
    with open(TEXT_FILE, "r", encoding="utf-8") as f:
        messages = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print(f"⚠️ Could not find {TEXT_FILE}")
    messages = []

if not messages:
    print("⚠️ No messages found in file, exiting…")
    exit()

async def main():
    while True:
        msg = random.choice(messages)
        try:
            await client.send_message(TARGET, msg)
            print(f"✅ Sent: {msg}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
        await asyncio.sleep(30)

# ====== Run both Flask + Bot ======
async def runner():
    await client.start()
    asyncio.create_task(main())

if __name__ == "__main__":
    import threading

    # Start Flask in background thread
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000)).start()

    with client:
        client.loop.run_until_complete(runner())

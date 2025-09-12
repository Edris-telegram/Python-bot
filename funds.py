import os
import asyncio
import random
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from flask import Flask
from threading import Thread

# ====== Load environment variables ======
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")  # Your session string
TARGET = int(os.getenv("TARGET"))            # Target group ID
MSG_FILE = os.getenv("MSG_FILE", "text.txt")
PORT = int(os.getenv("PORT", 10000))        # Dummy port for Render

# ====== Load messages ======
with open(MSG_FILE, "r", encoding="utf-8") as f:
    messages = [line.strip() for line in f if line.strip()]

if not messages:
    print("⚠️ No messages found in", MSG_FILE)
    exit()

# ====== Telegram client with StringSession ======
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ====== Telegram bot loop ======
async def bot_loop():
    while True:
        msg = random.choice(messages)
        await client.send_message(TARGET, msg)
        print(f"{datetime.now()} - Sent: {msg}")
        await asyncio.sleep(30)

# ====== Dummy Flask server for Render uptime ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ====== Start Flask in a separate thread ======
Thread(target=run_flask).start()

# ====== Start Telegram bot ======
with client:
    client.loop.run_until_complete(bot_loop())

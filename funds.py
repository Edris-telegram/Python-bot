from telethon import TelegramClient
import asyncio
import random

# ====== Your API credentials ======
API_ID = 10521518
API_HASH = "d66639f32854249745e33231cd1a535a"

# ====== Unique session name for this bot ======
client = TelegramClient("funds_bot", API_ID, API_HASH)

# ====== Load messages from text.txt ======
with open("text.txt", "r", encoding="utf-8") as f:
    messages = [line.strip() for line in f if line.strip()]

if not messages:
    print("⚠️ No messages found in text.txt")
    exit()

# ====== Your group ID (with prefix for supergroups/channels) ======
TARGET = -1003067016330

async def main():
    while True:
        msg = random.choice(messages)
        await client.send_message(TARGET, msg)
        print(f"Sent: {msg}")
        await asyncio.sleep(30)

with client:
    client.loop.run_until_complete(main())

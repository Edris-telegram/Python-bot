from telethon import TelegramClient
import asyncio
import random
import os
import logging

# ====== Setup logging ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ====== Your API credentials from environment ======
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")  # must be set in Render

# ====== Target group/user from environment ======
TARGET = os.getenv("TARGET")  # use str, Telethon handles it

# ====== Message file ======
TEXT_FILE = os.getenv("TEXT_FILE", "text.txt")  # default if not set

if not os.path.exists(TEXT_FILE):
    logger.error(f"⚠️ Message file {TEXT_FILE} not found!")
    exit()

with open(TEXT_FILE, "r", encoding="utf-8") as f:
    messages = [line.strip() for line in f if line.strip()]

if not messages:
    logger.error(f"⚠️ No messages found in {TEXT_FILE}")
    exit()

# ====== Create client ======
client = TelegramClient("funds_bot", API_ID, API_HASH)

async def main():
    logger.info("🚀 Bot started. Sending messages every 30s...")

    while True:
        msg = random.choice(messages)
        try:
            await client.send_message(TARGET, msg)
            logger.info(f"✅ Sent: {msg}")
        except Exception as e:
            logger.error(f"❌ Failed to send: {e}")
        await asyncio.sleep(30)

# ====== Run bot with session string ======
async def run():
    if SESSION_STRING:
        async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
            await main()
    else:
        logger.error("⚠️ SESSION_STRING not set in environment.")
        exit()

if __name__ == "__main__":
    client.loop.run_until_complete(run())async def main():
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

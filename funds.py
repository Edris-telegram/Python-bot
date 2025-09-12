from telethon import TelegramClient
import asyncio
import random
import os
import logging

# ====== Setup logging ======
logging.basicConfig(
    level=logging.CRITICAL  # hides Telethon INFO and ERROR logs
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
    logger.critical(f"⚠️ Message file {TEXT_FILE} not found!")
    exit()

with open(TEXT_FILE, "r", encoding="utf-8") as f:
    messages = [line.strip() for line in f if line.strip()]

if not messages:
    logger.critical(f"⚠️ No messages found in {TEXT_FILE}")
    exit()

# ====== Create client ======
client = TelegramClient("funds_bot", API_ID, API_HASH)

# ====== Main function now accepts client argument ======
async def main(client):
    logger.critical("🚀 Bot started. Sending messages every 30s...")

    while True:
        msg = random.choice(messages)
        try:
            await client.send_message(TARGET, msg)
            logger.critical(f"✅ Sent: {msg}")
        except Exception:
            pass  # hide send errors
        await asyncio.sleep(30)

# ====== Run bot with session string ======
async def run():
    from telethon.sessions import StringSession
    if SESSION_STRING:
        async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as session_client:
            await main(session_client)
    else:
        logger.critical("⚠️ SESSION_STRING not set in environment.")
        exit()

# ====== Dummy port server to satisfy Render ======
async def dummy_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 12345))  # dummy port
    s.listen()
    while True:
        await asyncio.sleep(3600)  # just keep the port open

# ====== Fixed entry point ======
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(dummy_port())  # start dummy port task
    loop.run_until_complete(run())client = TelegramClient("funds_bot", API_ID, API_HASH)

# ====== Main function now accepts client argument ======
async def main(client):
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
    from telethon.sessions import StringSession  # needed for session login
    if SESSION_STRING:
        async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as session_client:
            await main(session_client)  # pass the connected client to main
    else:
        logger.error("⚠️ SESSION_STRING not set in environment.")
        exit()

# ====== Fixed entry point ======
if __name__ == "__main__":
    import asyncio
    asyncio.run(run())

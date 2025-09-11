# bot.py  (use this name or your existing filename)
import os
import asyncio
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

# Load configuration from environment variables
api_id = int(os.environ.get('API_ID', '0'))
api_hash = os.environ.get('API_HASH')
session_str = os.environ.get('SESSION')   # string session you will create
group = int(os.environ.get('GROUP_ID', '-1003067016330'))  # override via env if needed
messages_file = os.environ.get('MESSAGES_FILE', 'messages.txt')
delay_seconds = int(os.environ.get('DELAY_SECONDS', '30'))

if not api_id or not api_hash or not session_str:
    raise RuntimeError("Missing one of API_ID, API_HASH or SESSION environment variables")

client = TelegramClient(StringSession(session_str), api_id, api_hash)

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

if __name__ == '__main__':
    asyncio.run(run())

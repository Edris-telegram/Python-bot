import asyncio
import random
from telethon import TelegramClient, errors

# --- CONFIGURATION ---
api_id = 27403368
api_hash = '7cfc7759b82410f5d90641d6a6fc415f'
group = 3037332500
messages_file = 'messages.txt'
min_delay =5
max_delay = 8
client = TelegramClient('session', api_id, api_hash)

async def main():
    with open(messages_file, 'r', encoding='utf-8') as f:
        messages = [line.strip() for line in f if line.strip()]

    for msg in messages:
        try:
            await client.send_message(group, msg)
            print(f"Sent: {msg}")
        except errors.FloodWaitError as e:
            print(f"⚠️ Flood wait: must wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            continue  # retry after waiting

        # Random delay to avoid spammy behavior
        delay_seconds = random.randint(min_delay, max_delay)
        print(f"Next message in {delay_seconds} seconds")
        await asyncio.sleep(delay_seconds)

with client:
    client.loop.run_until_complete(main())

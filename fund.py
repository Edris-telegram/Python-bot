import asyncio
from telethon import TelegramClient

# --- CONFIGURATION ---
api_id = 27403368
api_hash = '7cfc7759b82410f5d90641d6a6fc415f'
group = 3067016330  # numeric group ID
messages_file = 'messages.txt'
delay_seconds = 30
client = TelegramClient('session_name', api_id, api_hash)

async def main():
    with open(messages_file, 'r', encoding='utf-8') as f:
        messages = [line.strip() for line in f if line.strip()]

    for msg in messages:
        # Check pause flag
        while True:
            with open('pause.txt', 'r') as pf:
                if pf.read().strip() == '0':
                    break
            print("Bot paused... waiting to resume.")
            await asyncio.sleep(5)  # wait 5 seconds before checking again

        await client.send_message(group, msg)
        print(f"Sent: {msg}")
        await asyncio.sleep(delay_seconds)

with client:
    client.loop.run_until_complete(main())

# raid_auto_with_reply_verbose.py
import re
import json
import os
import random
import time
import traceback
from datetime import datetime
from telethon import TelegramClient, events, functions
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from fastapi import FastAPI
import threading
import uvicorn

# ------------------ TELEGRAM CONFIG ------------------
API_ID = 27403368
API_HASH = "7cfc7759b82410f5d90641d6a6fc415f"
SESSION = "session"               # session.session
WATCH_GROUPS = [-1002786329549]   # group id(s)
KNOWN_RAID_BOTS = ["raidar"]      # raid bot usernames
LOG_FILE = "raid_training_data.json"

TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Replying as a test ⚡",
    "Trial reply — automated"
]

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

# ------------------ TWITTER CONFIG ------------------
COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # set as env var
# ----------------------------------------------------

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
    with open(path, "r+", encoding="utf-8") as f:
        try:
            arr = json.load(f)
        except Exception:
            arr = []
        arr.append(entry)
        f.seek(0)
        json.dump(arr, f, indent=2)
        f.truncate()

def extract_tweet(text):
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)  # url, id
    return None, None

def get_random_message(file_path="messages.txt"):
    if not os.path.exists(file_path):
        print(f"[⚠️] {file_path} not found. Using default trial replies.")
        return random.choice(TRIAL_REPLIES)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return random.choice(TRIAL_REPLIES)
        return random.choice(lines)
    except Exception as e:
        print(f"[⚠️] Error reading {file_path}: {e}")
        return random.choice(TRIAL_REPLIES)

client = TelegramClient(SESSION, API_ID, API_HASH)

async def click_inline_button(client, message, match_texts=("👊",)):
    print("[🔘] Searching for inline buttons...")
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        print("[🔘] No inline buttons found")
        return {"clicked": False, "reason": "no_buttons"}

    print("[🔘] Buttons found (printing labels):")
    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", None)
            url = getattr(btn, "url", None)
            print(f"    Label: {lbl} | URL: {url}")

    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    print(f"[🔘] Attempting to click button: {lbl}")
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    print(f"[🔘] Click result: {res}")
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    print(f"[🔘] Error clicking {lbl}: {e}")
                    traceback.print_exc()
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    print("[🔘] No matching label found among buttons")
    return {"clicked": False, "reason": "no_matching_label"}

# ------------------ TWITTER REPLY FUNCTION (VERY VERBOSE) ------------------
def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []
    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                cookies = json.load(f)
                print(f"[🍪] Loaded {len(cookies)} cookies from JSON file '{cookie_input}'")
                return cookies
            except Exception as e:
                print(f"[❌] Failed reading cookies.json: {e}")
                return []
    if "=" not in cookie_input:
        print("[🍪] Cookie input looks like a raw auth_token")
        return [{
            "name": "auth_token",
            "value": cookie_input.strip(),
            "domain": ".x.com",
            "path": "/"
        }]
    parts = [p.strip() for p in cookie_input.split(";") if p.strip()]
    cookies = []
    for p in parts:
        if "=" in p:
            name, val = p.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": val.strip(),
                "domain": ".x.com",
                "path": "/"
            })
    print(f"[🍪] Parsed {len(cookies)} cookies from cookie string")
    return cookies

def try_selectors_with_debug(page, selectors, timeout=5000):
    """Try selectors with debug prints; returns the first that matches or None."""
    for sel in selectors:
        print(f"[🔎] Checking selector: {sel} (waiting up to {timeout}ms)")
        try:
            handle = page.wait_for_selector(sel, timeout=timeout)
            if handle:
                print(f"[🔎] Selector matched: {sel}")
                return sel
            else:
                print(f"[🔎] Selector did not match (no handle returned): {sel}")
        except PlaywrightTimeoutError:
            print(f"[🔎] Timeout waiting for selector: {sel}")
        except Exception as e:
            print(f"[🔎] Error while checking selector {sel}: {e}")
            traceback.print_exc()
    return None

def reply_to_tweet(tweet_url, message, headless=True):
    print("========================================")
    print(f"[🐦] Reply workflow start for: {tweet_url}")
    try:
        cookie_str = COOKIE_AUTH_TOKEN
        if not cookie_str:
            print("ERROR: No cookie found. Set TW_COOKIE env var.")
            return False

        print("[🐦] Parsing cookie input...")
        cookies = parse_cookie_input(cookie_str)
        if not cookies:
            print("ERROR: No cookies parsed; aborting reply.")
            return False

        print("[🐦] Launching Playwright browser (headless=%s) ..." % str(headless))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context()
            try:
                print("[🍪] Adding cookies to context...")
                context.add_cookies(cookies)
                print("[🍪] Cookies added to context successfully.")
                page = context.new_page()

                # Visit home - to let cookies apply
                try:
                    print("[→] Navigating to https://x.com/home ...")
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
                    print("[→] Home loaded.")
                except Exception as e:
                    print(f"[⚠️] Visiting home raised: {e}")
                    traceback.print_exc()

                # Open tweet URL
                try:
                    print(f"[→] Navigating to tweet: {tweet_url}")
                    page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
                    print("[→] Tweet page loaded.")
                except Exception as e:
                    print(f"[❌] Error opening tweet page: {e}")
                    traceback.print_exc()
                    page.screenshot(path="reply_error_opening_tweet.png")
                    print("[❗] Screenshot saved: reply_error_opening_tweet.png")
                    return False

                # Try to find a reply textbox
                textbox_selectors = [
                    "div[aria-label='Tweet text']",
                    "div[role='textbox'][contenteditable='true']",
                    "div[aria-label='Reply'] div[role='textbox']",
                    "div[data-testid='tweetTextarea_0']",
                    "div[aria-label='Tweet text']",  # duplicate to increase chance
                    "textarea[aria-label='Tweet text']"
                ]
                sel = try_selectors_with_debug(page, textbox_selectors, timeout=7000)

                # If not found, attempt reply button then retry
                if not sel:
                    reply_buttons = [
                        "div[data-testid='reply']",
                        "div[role='button'][data-testid='reply']",
                        "a[href$='/reply']",
                        "div[aria-label='Reply']"
                    ]
                    rb = try_selectors_with_debug(page, reply_buttons, timeout=5000)
                    if rb:
                        try:
                            print(f"[→] Clicking reply launcher: {rb}")
                            page.click(rb)
                            print("[→] Clicked reply launcher; waiting briefly...")
                            time.sleep(1.2)
                            sel = try_selectors_with_debug(page, textbox_selectors, timeout=7000)
                        except Exception as e:
                            print(f"[⚠️] Failed clicking reply launcher: {e}")
                            traceback.print_exc()

                if not sel:
                    print("⚠️ Reply textbox not found — cookie may not be logged in or layout changed.")
                    page.screenshot(path="debug_tweet.png")
                    print("[❗] Saved debug_tweet.png — inspect it to see page layout / login state.")
                    return False

                print(f"[→] Using textbox selector: {sel} — focusing and typing message.")
                try:
                    page.click(sel)
                except Exception as e:
                    print(f"[⚠️] click(sel) raised: {e} — continuing to fill anyway.")
                page.fill(sel, message)
                time.sleep(0.4)

                # Try multiple send button selectors, printing each check
                send_selectors = [
                    "div[data-testid='tweetButtonInline']",
                    "div[data-testid='tweetButton']",
                    "div[data-testid='replyButton']",
                    "div[role='button'][data-testid='tweetButton']",
                    "div[aria-label='Reply'] div[role='button']"
                ]
                sent = False
                for s in send_selectors:
                    print(f"[🔎] Looking for send selector: {s}")
                    try:
                        btn = page.query_selector(s)
                        if btn:
                            print(f"[→] Found send button {s} — clicking...")
                            btn.click()
                            sent = True
                            break
                        else:
                            # try wait_for_selector briefly
                            try:
                                btn2 = page.wait_for_selector(s, timeout=2500)
                                if btn2:
                                    print(f"[→] Found send button via wait_for_selector {s} — clicking...")
                                    btn2.click()
                                    sent = True
                                    break
                            except Exception:
                                print(f"[🔎] Not found via wait_for_selector either: {s}")
                    except Exception as e:
                        print(f"[❌] Exception while probing send selector {s}: {e}")
                        traceback.print_exc()

                if not sent:
                    # Fallback to keyboard submit
                    try:
                        print("[→] Fallback: Ctrl+Enter keyboard submit")
                        page.keyboard.down("Control")
                        page.keyboard.press("Enter")
                        page.keyboard.up("Control")
                        sent = True
                    except Exception as e:
                        print(f"[❌] Fallback keyboard submit failed: {e}")
                        traceback.print_exc()
                        sent = False

                if sent:
                    print("[✔] Reply action attempted. Waiting a few seconds for completion...")
                    time.sleep(4)
                    page.screenshot(path="reply_after_send.png")
                    print("[📸] Saved reply_after_send.png for inspection")
                    print("[🐦] Reply workflow completed — check the tweet.")
                    return True
                else:
                    print("❌ Could not trigger send action. Saving debug screenshot.")
                    page.screenshot(path="error_debug.png")
                    print("[❗] Saved error_debug.png")
                    return False

            except Exception as e:
                print("❌ Exception during reply workflow:", e)
                traceback.print_exc()
                try:
                    page.screenshot(path="error_debug_exception.png")
                    print("[❗] Saved error_debug_exception.png")
                except Exception:
                    pass
                return False
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                browser.close()
                print("[🔚] Browser closed.")
    except Exception as e:
        print("❌ Top-level exception in reply_to_tweet:", e)
        traceback.print_exc()
        return False
    finally:
        print("========================================")

# ------------------ FASTAPI DUMMY SERVER ------------------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive", "message": "Service is running"}

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"[🌐] Starting dummy server on port {port} (uvicorn)...")
    uvicorn.run(app, host="0.0.0.0", port=port)

# ------------------ TELEGRAM HANDLER ------------------
@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        if not sender_id or sender_id not in [5994885234]:
            print(f"[DEBUG] Ignored message from sender ID: {sender_id}")
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        print(f"\n🚨 [RAID DETECTED] Tweet: {tweet_url}")

        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        print(f"[🔘] Button click result: {click_result}")

        message_to_send = get_random_message()
        print(f"[💬] Selected reply message: {message_to_send}")

        print(f"[🐦] Replying to {tweet_url} with message: {message_to_send}")
        success = reply_to_tweet(tweet_url, message_to_send, headless=(os.environ.get("HEADLESS","1") != "0"))

        print(f"[🐦] Reply success: {success}")

        entry = {
            "time": now_iso(),
            "chat_id": event.chat_id,
            "message_id": msg.id,
            "tweet_url": tweet_url,
            "smash": click_result,
            "message": message_to_send,
            "reply_success": success
        }
        save_json_append(LOG_FILE, entry)

    except Exception as e:
        print("❌ Error in handler:", repr(e))
        traceback.print_exc()

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting raid_auto_with_reply_verbose...")
    threading.Thread(target=start_dummy_server, daemon=True).start()
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()

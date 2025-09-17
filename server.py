# server.py
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import time

app = Flask(__name__)

# Your Twitter login cookie
TWITTER_COOKIE = {
    "name": "auth_token",
    "value": "132e4b440d7dd8209ad20c6808de973ad11c7412",
    "domain": ".twitter.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "Lax"
}

@app.route("/ping")
def ping():
    return "OK"

@app.route("/reply", methods=["POST"])
def reply_tweet():
    data = request.json
    tweet_url = data.get("tweet_url")
    reply_text = data.get("reply_text")

    if not tweet_url or not reply_text:
        return jsonify({"ok": False, "error": "tweet_url or reply_text missing"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies([TWITTER_COOKIE])
            page = context.new_page()
            page.goto(tweet_url)
            time.sleep(2)  # wait for page to load

            # Click reply button
            page.click('div[data-testid="reply"]')
            time.sleep(1)

            # Type the reply
            page.fill('div[data-testid="tweetTextarea_0"]', reply_text)
            time.sleep(0.5)

            # Click tweet button
            page.click('div[data-testid="tweetButtonInline"]')
            time.sleep(1)

            browser.close()

        return jsonify({"ok": True, "tweet_url": tweet_url, "reply_text": reply_text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Keep alive port 10000 (can be changed if needed)
    app.run(host="0.0.0.0", port=10000)

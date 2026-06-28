#!/usr/bin/env python3
"""
Send a test Telegram notification to verify your bot is working.

Prerequisites:
    export TELEGRAM_BOT_TOKEN=your_bot_token
    export TELEGRAM_CHAT_ID=your_chat_id

Usage:
    python scripts/test_telegram.py
"""
import json
import os
import urllib.parse
import urllib.request

bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    raise SystemExit("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": "✅ *Quillcast — notification test*\n\nTelegram notifications are working correctly.",
    "parse_mode": "Markdown",
}).encode()

req = urllib.request.Request(url, data=data)
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())

if result.get("ok"):
    print("✅ Message sent successfully. Check your Telegram.")
else:
    print(f"❌ Failed: {result}")

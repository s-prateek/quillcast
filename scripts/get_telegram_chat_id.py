#!/usr/bin/env python3
"""
Find your Telegram chat_id after sending a message to your bot.

Prerequisites:
    export TELEGRAM_BOT_TOKEN=your_bot_token

Steps:
    1. Message @BotFather → /newbot → follow prompts → copy the token
    2. Send ANY message to your new bot in Telegram
    3. Run this script: python scripts/get_telegram_chat_id.py
    4. Copy the chat_id shown and add it to your .env file

Usage:
    python scripts/get_telegram_chat_id.py
"""
import json
import os
import urllib.request

bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not bot_token:
    raise SystemExit("ERROR: Set TELEGRAM_BOT_TOKEN environment variable.")

url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read())

if not data.get("result"):
    print("No updates found.")
    print("→ Send a message to your bot in Telegram first, then re-run this script.")
else:
    for update in data["result"]:
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        print(f"chat_id : {chat.get('id')}")
        print(f"name    : {chat.get('first_name', '')} {chat.get('last_name', '')}".strip())
        print(f"username: @{chat.get('username', 'n/a')}")

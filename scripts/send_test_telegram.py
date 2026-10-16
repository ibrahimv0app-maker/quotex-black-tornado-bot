#!/usr/bin/env python3
"""
scripts/send_test_telegram.py
Simple test script to send a message with custom_emoji entities and print Telegram API response.
Usage:
  TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 scripts/send_test_telegram.py

Replace emoji IDs with the ones you want to test.
"""
import os
import json
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in env before running")
    raise SystemExit(1)

emoji_channel_id = "6214983170991853422"
emoji_pair_id = "5231200819986047254"

text = "🔸 قناة تداول كوتكس\n🔹 الزوج: CADCHF-OTC\n\nاختبار custom emoji"

# helpers
def utf16_offset(s, char_index):
    return len(s[:char_index].encode("utf-16-le")) // 2

pos1 = text.index("🔸")
pos2 = text.index("🔹")

entities = [
    {
        "type": "custom_emoji",
        "offset": utf16_offset(text, pos1),
        "length": len("🔸".encode("utf-16-le")) // 2,
        "custom_emoji_id": emoji_channel_id,
    },
    {
        "type": "custom_emoji",
        "offset": utf16_offset(text, pos2),
        "length": len("🔹".encode("utf-16-le")) // 2,
        "custom_emoji_id": emoji_pair_id,
    }
]

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": text, "entities": json.dumps(entities)}

resp = requests.post(url, data=payload)
print("status:", resp.status_code)
try:
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
except Exception:
    print(resp.text)

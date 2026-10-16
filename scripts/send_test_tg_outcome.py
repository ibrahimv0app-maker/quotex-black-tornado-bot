import json
import time
from app.notifications.telegram import TelegramNotifier

notifier = TelegramNotifier()
now_ts = int(time.time())
entry_ts = ((now_ts // 60) + 1) * 60 - 60
expiry_ts = entry_ts + 60

outcome_payload = {
    "signal_id": f"TEST_{entry_ts}_AUDNZD",
    "symbol": "AUDNZD-OTC",
    "direction": "CALL",
    "outcome": "WIN",
    "entry_quote": 1.24162,
    "expiry_quote": 1.24185,
    "price_delta": 0.00023,
    "strategy_name": "Trend Pullback",
    "intended_entry_time": entry_ts,
    "intended_expiry_time": expiry_ts
}

html_message = notifier.format_outcome_message(outcome_payload)
print(html_message)

with open("/tmp/tg_test_outcome_payload.json", "w") as f:
    json.dump({
        "chat_id": "-1003501100081",
        "text": html_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, f)

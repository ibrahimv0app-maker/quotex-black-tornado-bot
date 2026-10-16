import json
import time
import pytz
from datetime import datetime
from app.notifications.telegram import TelegramNotifier
from app.strategies.base import StrategySignal

notifier = TelegramNotifier()
now_ts = int(time.time())
next_entry = ((now_ts // 60) + 1) * 60
expiry = next_entry + 60

sig = StrategySignal(
    strategy_name="Trend Pullback",
    symbol="AUDNZD-OTC",
    direction="CALL",
    score=95.5,
    reason="Bullish EMA stack (9>21>50) with bounce from EMA dynamic support",
    indicators={"EMA9": 1.24158, "EMA21": 1.24140, "RSI": 58.2},
    confirmations=[
        "EMA alignment bullish (9>21>50)",
        "Pullback dynamic support respected",
        "RSI healthy (58.2 in bullish momentum band)",
        "NATR volatility stable"
    ]
)

payload = {
    "signal_id": f"TEST_{next_entry}_AUDNZD",
    "signal": sig,
    "composite_score": 95.5,
    "intended_entry_time": next_entry,
    "signal_sent_time": now_ts,
    "intended_expiry_time": expiry
}

html_message = notifier.format_signal_message(payload)
print(html_message)

with open("/tmp/tg_test_payload.json", "w") as f:
    json.dump({
        "chat_id": "-1003501100081",
        "text": html_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, f)

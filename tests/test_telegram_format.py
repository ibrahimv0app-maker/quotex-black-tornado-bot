from app.notifications.telegram import TelegramNotifier
from app.strategies.base import StrategySignal


def test_telegram_message_formatting():
    notifier = TelegramNotifier()
    sig = StrategySignal(
        strategy_name="BT03 — ADAPTIVE_PULLBACK",
        symbol="EURUSD-OTC",
        direction="CALL",
        score=82.0,
        reason="Healthy pullback to EMA9 with bullish momentum",
        indicators={"EMA9": 1.1125, "EMA21": 1.1120, "RSI": 58.4},
        confirmations=["M1 trend aligned", "M5 trend aligned", "ATR volatility stable"]
    )

    payload = {
        "signal_id": "BT_1792050900_EURUSD",
        "signal": sig,
        "composite_score": 82.0,
        "intended_entry_time": 1792050900,
        "signal_sent_time": 1792050888,
        "intended_expiry_time": 1792050960,
        "volatility_label": "Stable",
        "trend_status": "Trend Confirmed"
    }

    text = notifier.format_signal_message(payload)
    assert "BLACK TORNADO" in text
    assert "EURUSD-OTC" in text
    assert "CALL" in text
    assert "82/100" in text
    assert "Trend Confirmed" in text
    assert "Volatility:" in text
    assert "━━━━━━━━━━━━" in text


def test_telegram_outcome_formatting():
    notifier = TelegramNotifier()
    payload = {
        "signal_id": "BT_1792050900_EURUSD",
        "symbol": "EURUSD-OTC",
        "direction": "CALL",
        "outcome": "WIN",
        "entry_quote": 1.11200,
        "expiry_quote": 1.11225,
        "price_delta": 0.00025,
        "strategy_name": "BT03 — ADAPTIVE_PULLBACK",
        "intended_entry_time": 1792050900,
        "intended_expiry_time": 1792050960,
        "wins_count": 18,
        "losses_count": 7,
        "win_rate_percent": 72.0
    }
    text = notifier.format_outcome_message(payload)
    assert "BLACK TORNADO RESULT" in text
    assert "EURUSD-OTC" in text
    assert "WIN" in text
    assert "1.11200" in text
    assert "1.11225" in text
    assert "<b>Wins:</b> 18 | ❌ <b>Losses:</b> 7" in text
    assert "<b>Win Rate:</b> 72%" in text
    assert "Feed-estimated" in text
    assert "━━━━━━━━━━━━" in text

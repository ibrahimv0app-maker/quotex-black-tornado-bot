"""Tests for honest 1-minute expiry outcome verification."""
import pytest
from app.database.repository import DatabaseRepository
from app.engine.outcome_tracker import OutcomeTracker
from app.feed.candle_store import candle_store


@pytest.mark.asyncio
async def test_outcome_resolution_win_and_loss():
    repo = DatabaseRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db()
    tracker = OutcomeTracker(repo)

    # Simulate candles in candle_store for entry and expiry
    sym = "EURUSD-OTC"
    entry_ts = 1792050000
    expiry_ts = 1792050060

    candle_store.load_initial_candles(sym, [
        {"time": entry_ts, "open": 1.10000, "high": 1.10050, "low": 1.09950, "close": 1.10020, "volume": 50},
        {"time": expiry_ts, "open": 1.10020, "high": 1.10070, "low": 1.10010, "close": 1.10060, "volume": 50}
    ])

    active_sig = {
        "signal_id": "SIG_CALL_1",
        "symbol": sym,
        "direction": "CALL",
        "strategy_name": "Trend Pullback",
        "intended_entry_time": entry_ts,
        "intended_expiry_time": expiry_ts,
        "signal_price": 1.10000
    }

    # At expiry_ts + 5s
    await repo.acquire_signal_lock_and_create(
        signal_id="SIG_CALL_1",
        symbol=sym,
        direction="CALL",
        strategy_name="Trend Pullback",
        setup_score=80.0,
        signal_sent_time=entry_ts - 12,
        intended_entry_time=entry_ts,
        intended_expiry_time=expiry_ts,
        signal_price=1.10000
    )

    # Settle signal
    settled = await tracker.settle_signal(active_sig)
    assert settled is True

    stats = await repo.get_stats()
    assert stats["total_signals"] == 1
    assert stats["wins"] == 1
    assert stats["losses"] == 0
    assert stats["win_rate_percent"] == 100.0

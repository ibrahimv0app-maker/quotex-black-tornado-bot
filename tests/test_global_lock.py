"""Tests for database persistent atomic signal locking."""
import pytest
import asyncio
from app.database.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_global_lock_prevents_simultaneous_signals():
    repo = DatabaseRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db()

    # 1. First signal acquires lock successfully
    success1 = await repo.acquire_signal_lock_and_create(
        signal_id="TEST_001",
        symbol="EURUSD-OTC",
        direction="CALL",
        strategy_name="Trend Pullback",
        setup_score=85.0,
        signal_sent_time=1000,
        intended_entry_time=1012,
        intended_expiry_time=1072,
        signal_price=1.1120
    )
    assert success1 is True

    # 2. Second signal concurrent attempt MUST BE BLOCKED
    success2 = await repo.acquire_signal_lock_and_create(
        signal_id="TEST_002",
        symbol="GBPUSD-OTC",
        direction="PUT",
        strategy_name="Momentum",
        setup_score=90.0,
        signal_sent_time=1001,
        intended_entry_time=1012,
        intended_expiry_time=1072,
        signal_price=1.2500
    )
    assert success2 is False

    # 3. Active signal is retrievable
    active = await repo.get_active_signal()
    assert active is not None
    assert active["signal_id"] == "TEST_001"

    # 4. Once resolved, lock is released
    await repo.resolve_signal(
        signal_id="TEST_001",
        outcome="WIN",
        entry_quote=1.1120,
        expiry_quote=1.1130,
        price_delta=0.0010,
        is_verified=True
    )

    # Now a new signal can be accepted
    active_after = await repo.get_active_signal()
    assert active_after is None

    success3 = await repo.acquire_signal_lock_and_create(
        signal_id="TEST_003",
        symbol="GBPUSD-OTC",
        direction="PUT",
        strategy_name="Momentum",
        setup_score=90.0,
        signal_sent_time=1100,
        intended_entry_time=1112,
        intended_expiry_time=1172,
        signal_price=1.2500
    )
    assert success3 is True

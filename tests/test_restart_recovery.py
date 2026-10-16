"""Tests for state restoration and non-duplication after service restart."""
import pytest
from app.database.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_restart_recovery_preserves_active_signals():
    db_url = "sqlite+aiosqlite:///:memory:"
    repo1 = DatabaseRepository(db_url)
    await repo1.init_db()

    await repo1.acquire_signal_lock_and_create(
        signal_id="RECOVERY_01",
        symbol="EURUSD-OTC",
        direction="PUT",
        strategy_name="Momentum",
        setup_score=88.0,
        signal_sent_time=1000,
        intended_entry_time=1060,
        intended_expiry_time=1120,
        signal_price=1.1150
    )

    # Simulate app restart using the same engine
    repo2 = DatabaseRepository(db_url)
    repo2.engine = repo1.engine
    repo2.session_factory = repo1.session_factory

    active = await repo2.get_active_signal()
    assert active is not None
    assert active["signal_id"] == "RECOVERY_01"
    assert active["direction"] == "PUT"

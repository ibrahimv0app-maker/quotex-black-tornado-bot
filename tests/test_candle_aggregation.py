"""Tests for tick-to-minute candle aggregation and boundary transitions."""
from app.feed.candle_store import CandleStore


def test_single_minute_aggregation():
    store = CandleStore()
    sym = "EURUSD-OTC"

    # Minute boundary 1792050000 (12:00:00)
    store.process_tick(sym, 1.1000, 1792050005) # open = 1.1000
    store.process_tick(sym, 1.1020, 1792050020) # high = 1.1020
    store.process_tick(sym, 1.0980, 1792050040) # low = 1.0980
    store.process_tick(sym, 1.1010, 1792050055) # close = 1.1010

    forming = store.get_forming_candle(sym)
    assert forming is not None
    assert forming["time"] == 1792050000
    assert forming["open"] == 1.1000
    assert forming["high"] == 1.1020
    assert forming["low"] == 1.0980
    assert forming["close"] == 1.1010
    assert forming["volume"] == 4.0


def test_minute_transition_closes_candle():
    store = CandleStore()
    sym = "GBPUSD-OTC"

    store.process_tick(sym, 1.2500, 1792050010)
    store.process_tick(sym, 1.2550, 1792050050)

    # Tick at next minute 1792050060 (12:01:00)
    closed = store.process_tick(sym, 1.2560, 1792050065)
    assert closed is not None
    assert closed.time == 1792050000
    assert closed.open == 1.2500
    assert closed.close == 1.2550

    closed_list = store.get_closed_candles(sym)
    assert len(closed_list) == 1
    assert closed_list[0]["close"] == 1.2550

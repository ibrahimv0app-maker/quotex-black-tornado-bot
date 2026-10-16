import pytest
from app.indicators.black_tornado import black_tornado, aggregate_closed_m5, TornadoOutput
from app.strategies.black_tornado import build_strategies, SPECS


def _generate_synthetic_candles(count: int = 120, trend: float = 0.0001):
    base_time = 1700000000
    base_price = 1.1000
    candles = []
    price = base_price
    for i in range(count):
        price += trend
        o = price
        h = price + 0.0004
        l = price - 0.0002
        c = price + 0.0002
        candles.append({
            "time": base_time + (i * 60),
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": 10.0
        })
    return candles


def test_black_tornado_eval_returns_valid_ranges():
    candles = _generate_synthetic_candles(count=100, trend=0.0002)
    output = black_tornado.evaluate(candles)

    assert isinstance(output, TornadoOutput)
    assert output.bt_data_ok is True
    assert -100.0 <= output.bt_direction <= 100.0
    assert 0.0 <= output.bt_confidence <= 100.0
    assert 0.0 <= output.bt_pressure <= 100.0
    assert 0.0 <= output.bt_turbulence <= 100.0
    assert 0.0 <= output.bt_exhaustion <= 100.0
    assert output.bt_regime in {"TREND_UP", "TREND_DOWN", "RANGE", "SQUEEZE", "EXPANSION", "REVERSAL_RISK", "CHAOS", "UNKNOWN"}
    assert output.bt_structure in {"HH_HL", "LH_LL", "MIXED", "UNKNOWN"}
    assert output.bt_sweep_reclaim in {"NONE", "BULLISH_RECLAIM", "BEARISH_RECLAIM"}
    assert output.bt_breakout in {"NONE", "UPSIDE_BREAKOUT", "DOWNSIDE_BREAKOUT", "FAILED_BREAKOUT"}
    assert output.bt_htf_alignment in {"BULLISH", "BEARISH", "NEUTRAL"}


def test_all_25_strategies_exist_and_instantiate():
    strategies = build_strategies()
    assert len(strategies) == 25
    assert len(SPECS) == 25
    strategy_ids = [s.strategy_id for s in strategies]
    assert strategy_ids[0] == "BT01"
    assert strategy_ids[-1] == "BT25"


def test_black_tornado_causality_and_freshness():
    candles = _generate_synthetic_candles(count=80)
    # Stale data check (e.g. data older than 10s from now)
    now_ts = 1700000000 + (80 * 60) + 30
    last_candle_ts = candles[-1]["time"]
    
    output_stale = black_tornado.evaluate(
        candles,
        data_fresh=True,
        data_timestamp=last_candle_ts,
        now_timestamp=now_ts
    )
    # If stale gap is > 10s, bt_data_ok must be False
    assert output_stale.bt_data_ok is False
    assert output_stale.bt_regime == "UNKNOWN"


def test_m5_aggregation():
    # 15 consecutive M1 candles should yield exactly 3 complete M5 candles
    base_time = 1700000100 - (1700000100 % 300) # aligned to 300s
    candles = []
    for i in range(15):
        candles.append({
            "time": base_time + (i * 60),
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
            "volume": 5.0
        })
    m5 = aggregate_closed_m5(candles)
    assert len(m5) == 3
    assert m5[0]["time"] == base_time
    assert m5[1]["time"] == base_time + 300
    assert m5[2]["time"] == base_time + 600

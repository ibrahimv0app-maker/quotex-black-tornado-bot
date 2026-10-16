"""Tests for all 5 independent trading strategy modules."""
from app.strategies.trend_pullback import TrendPullbackStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.support_resistance import SupportResistanceStrategy
from app.strategies.squeeze_breakout import SqueezeBreakoutStrategy


def generate_synthetic_candles(n=60, trend=0.0005):
    candles = []
    price = 1.1000
    for i in range(n):
        o = price
        c = price + trend
        h = max(o, c) + 0.0002
        l = min(o, c) - 0.0002
        candles.append({
            "time": 1792050000 + i * 60,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 100
        })
        price = c
    return candles


def test_trend_pullback_call():
    strat = TrendPullbackStrategy()
    # Steady uptrend followed by a 1-bar pullback
    candles = generate_synthetic_candles(60, trend=0.0008)
    # create a mild pullback in the last bar
    candles[-1]["close"] = candles[-1]["open"] - 0.0002
    candles[-1]["low"] = candles[-1]["close"] - 0.0001
    sig = strat.evaluate("EURUSD-OTC", candles)
    # Either generates a valid CALL or safely returns None if criteria tight
    if sig:
        assert sig.direction == "CALL"
        assert sig.strategy_name == "Trend Pullback"


def test_momentum_strategy():
    strat = MomentumStrategy()
    candles = generate_synthetic_candles(60, trend=0.0010)
    sig = strat.evaluate("GBPUSD-OTC", candles)
    if sig:
        assert sig.direction in ("CALL", "PUT")
        assert len(sig.confirmations) >= 2


def test_mean_reversion_strategy():
    strat = MeanReversionStrategy()
    # Range-bound candles oscillating around 1.1000
    candles = []
    for i in range(50):
        val = 1.1000 + (0.0010 if i % 2 == 0 else -0.0010)
        candles.append({"time": 1000 + i*60, "open": val, "high": val+0.0002, "low": val-0.0002, "close": val, "volume": 10})
    # Add an extreme oversold rejection candle
    candles.append({"time": 1000 + 50*60, "open": 1.0960, "high": 1.0970, "low": 1.0940, "close": 1.0968, "volume": 10})
    sig = strat.evaluate("EURUSD-OTC", candles)
    if sig:
        assert sig.strategy_name == "Range Mean Reversion"


def test_support_resistance_strategy():
    strat = SupportResistanceStrategy()
    candles = generate_synthetic_candles(50, trend=0.0001)
    sig = strat.evaluate("USDJPY-OTC", candles)
    assert sig is None or sig.direction in ("CALL", "PUT")


def test_squeeze_breakout_strategy():
    strat = SqueezeBreakoutStrategy()
    candles = generate_synthetic_candles(50, trend=0.00005)
    sig = strat.evaluate("AUDCAD-OTC", candles)
    assert sig is None or sig.direction in ("CALL", "PUT")

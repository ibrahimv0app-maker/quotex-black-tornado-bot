"""Tests for technical, volatility, and pattern indicators."""
from app.indicators.technical import calculate_ema, calculate_rsi, calculate_bollinger_bands, calculate_macd
from app.indicators.volatility import calculate_atr, calculate_normalized_atr
from app.indicators.patterns import analyze_candle_structure


def test_ema_computation():
    prices = [1.0 + i * 0.1 for i in range(30)]
    ema10 = calculate_ema(prices, 10)
    assert len(ema10) == 21
    # Moving average should be trending upward
    assert ema10[-1] > ema10[0]


def test_rsi_computation():
    uptrend = [1.0 + i * 0.05 for i in range(30)]
    rsi = calculate_rsi(uptrend, 14)
    assert len(rsi) > 0
    assert rsi[-1] > 80.0  # Strong uptrend leads to high RSI


def test_bollinger_bands():
    prices = [10.0 + (i % 3) for i in range(40)]
    bb = calculate_bollinger_bands(prices, 20, 2.0)
    assert len(bb["upper"]) == 21
    assert bb["upper"][-1] > bb["middle"][-1] > bb["lower"][-1]


def test_atr_and_normalization():
    highs = [1.12 + 0.005 for _ in range(25)]
    lows = [1.12 - 0.005 for _ in range(25)]
    closes = [1.12 for _ in range(25)]
    atr = calculate_atr(highs, lows, closes, period=14)
    assert len(atr) > 0
    assert atr[-1] > 0
    natr = calculate_normalized_atr(atr[-1], 1.12)
    assert natr > 0


def test_candle_structure():
    bullish_pinbar = {"open": 1.1010, "high": 1.1015, "low": 1.0950, "close": 1.1012}
    struct = analyze_candle_structure(bullish_pinbar)
    assert struct["is_bullish"] is True
    assert struct["rejection"] == "BULLISH_REJECTION"
    assert struct["lower_wick_ratio"] > 0.60

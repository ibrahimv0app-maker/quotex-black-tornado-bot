"""Candle pattern and structural price action detection."""
from typing import Dict, Any


def analyze_candle_structure(candle: Dict[str, Any]) -> Dict[str, Any]:
    """Extract candle anatomy: body ratio, wick ratios, and direction."""
    o = candle["open"]
    h = candle["high"]
    l = candle["low"]
    c = candle["close"]

    total_range = h - l
    if total_range <= 0:
        return {
            "is_bullish": False,
            "is_bearish": False,
            "is_doji": True,
            "body_ratio": 0.0,
            "upper_wick_ratio": 0.0,
            "lower_wick_ratio": 0.0,
            "rejection": "NONE"
        }

    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    body_ratio = body / total_range
    upper_wick_ratio = upper_wick / total_range
    lower_wick_ratio = lower_wick / total_range

    is_bullish = c > o
    is_bearish = c < o
    is_doji = body_ratio < 0.10

    rejection = "NONE"
    # Pinbar / Rejection detection (wick > 60% of total candle, small body)
    if lower_wick_ratio >= 0.55 and body_ratio <= 0.35:
        rejection = "BULLISH_REJECTION"  # buyers rejected lower price
    elif upper_wick_ratio >= 0.55 and body_ratio <= 0.35:
        rejection = "BEARISH_REJECTION"  # sellers rejected higher price

    return {
        "is_bullish": is_bullish,
        "is_bearish": is_bearish,
        "is_doji": is_doji,
        "body_ratio": round(body_ratio, 3),
        "upper_wick_ratio": round(upper_wick_ratio, 3),
        "lower_wick_ratio": round(lower_wick_ratio, 3),
        "rejection": rejection
    }

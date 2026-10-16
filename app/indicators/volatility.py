"""Volatility indicators: True Range, Average True Range, and normalization."""
from typing import List, Dict, Any


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Compute Average True Range (Wilder's ATR)."""
    n = len(closes)
    if n < period + 1:
        return []

    tr_list = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        tr_list.append(tr)

    # Initial ATR is simple average
    atr = [sum(tr_list[:period]) / period]
    for i in range(period, len(tr_list)):
        current_atr = (atr[-1] * (period - 1) + tr_list[i]) / period
        atr.append(current_atr)

    return atr


def calculate_normalized_atr(atr_value: float, price: float) -> float:
    """Normalize ATR as basis points (percentage * 100)."""
    if price <= 0:
        return 0.0
    return (atr_value / price) * 10000.0

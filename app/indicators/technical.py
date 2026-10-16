"""Core technical indicator calculations without lookahead bias."""
import math
from typing import List, Tuple, Dict, Optional


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Compute Exponential Moving Average."""
    if len(prices) < period:
        return []
    
    multiplier = 2.0 / (period + 1.0)
    ema_list = []
    
    # Seed with SMA of first 'period' elements
    initial_sma = sum(prices[:period]) / period
    ema_list.append(initial_sma)
    
    for price in prices[period:]:
        new_ema = (price - ema_list[-1]) * multiplier + ema_list[-1]
        ema_list.append(new_ema)
        
    return ema_list


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Compute Relative Strength Index."""
    if len(prices) < period + 1:
        return []

    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))

    # Initial average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    # Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values


def calculate_bollinger_bands(
    prices: List[float], period: int = 20, std_dev: float = 2.0
) -> Dict[str, List[float]]:
    """Compute Bollinger Bands (Upper, Middle, Lower, Bandwidth)."""
    if len(prices) < period:
        return {"upper": [], "middle": [], "lower": [], "bandwidth": []}

    upper = []
    middle = []
    lower = []
    bandwidth = []

    for i in range(period, len(prices) + 1):
        window = prices[i - period : i]
        mean = sum(window) / period
        variance = sum((p - mean) ** 2 for p in window) / period
        std = math.sqrt(variance)

        u = mean + (std_dev * std)
        l = mean - (std_dev * std)
        bw = (u - l) / mean if mean != 0 else 0.0

        middle.append(mean)
        upper.append(u)
        lower.append(l)
        bandwidth.append(bw)

    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": bandwidth}


def calculate_macd(
    prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, List[float]]:
    """Compute MACD line, Signal line, and Histogram."""
    if len(prices) < slow + signal:
        return {"macd": [], "signal": [], "histogram": []}

    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)

    # Align fast to slow
    offset = slow - fast
    aligned_fast = ema_fast[offset:]
    macd_line = [f - s for f, s in zip(aligned_fast, ema_slow)]

    signal_line = calculate_ema(macd_line, signal)
    signal_offset = len(macd_line) - len(signal_line)
    aligned_macd = macd_line[signal_offset:]

    histogram = [m - s for m, s in zip(aligned_macd, signal_line)]

    return {
        "macd": aligned_macd,
        "signal": signal_line,
        "histogram": histogram
    }

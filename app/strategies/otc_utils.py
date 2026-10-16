"""
OTC-specific utilities: ATR, spread/liquidity filter, adaptive sizing, score adjustment.
"""
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd


def atr_from_candles(closed_candles: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    if len(closed_candles) < period + 1:
        return None
    df = pd.DataFrame(closed_candles)
    if {"high", "low", "close"}.difference(df.columns):
        return None
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    if pd.isna(atr):
        return None
    return float(atr)


def should_execute_otc(
    closed_candles: List[Dict[str, Any]],
    context: Dict[str, Any],
    spread_threshold: float = 0.0005,
    min_liquidity: float = 100.0,
    atr_multiplier_threshold: float = 3.0,
    atr_period: int = 14
) -> (bool, Dict[str, Any]):
    """
    Return (allowed, diagnostics). Expect context to possibly include:
    - 'spread' (absolute or relative price units)
    - 'liquidity' (volume / orderbook proxy)
    - 'market_mode' / 'session' optional
    """
    diagnostics = {}
    spread = context.get("spread")
    liquidity = context.get("liquidity")
    atr = atr_from_candles(closed_candles, period=atr_period)

    diagnostics["spread"] = spread
    diagnostics["liquidity"] = liquidity
    diagnostics["atr"] = atr

    if spread is None:
        diagnostics["reason"] = "no_spread_info"
    else:
        if spread > spread_threshold:
            return False, {**diagnostics, "reason": "spread_too_high"}

    if liquidity is not None and liquidity < min_liquidity:
        return False, {**diagnostics, "reason": "insufficient_liquidity"}

    if atr is not None:
        last_price = float(closed_candles[-1]["close"])
        rel_atr = atr / last_price if last_price != 0 else 0
        diagnostics["rel_atr"] = rel_atr
        if rel_atr * 1e4 > atr_multiplier_threshold * 10:
            return False, {**diagnostics, "reason": "atr_too_high"}

    return True, diagnostics


def adaptive_position_size(
    balance: float,
    risk_per_trade: float,
    atr_value: float,
    atr_multiplier: float = 2.0,
    price: float = 1.0,
    min_size: float = 0.0
) -> float:
    """
    Compute size in price-units so that risk_per_trade of balance is risked
    dollar_risk = balance * risk_per_trade
    stop_distance = atr_value * atr_multiplier
    qty = dollar_risk / stop_distance
    """
    if atr_value is None or atr_value <= 0:
        return min_size
    dollar_risk = max(0.0, balance * risk_per_trade)
    stop_distance = atr_value * atr_multiplier
    if stop_distance <= 0:
        return min_size
    qty = dollar_risk / stop_distance
    return max(min_size, qty)


def adjust_score_for_otc(original_score: float, diagnostics: Dict[str, Any], max_penalty: float = 30.0) -> float:
    """
    Lower score if spread or rel_atr or flagged reasons exist.
    """
    score = original_score
    penalty = 0.0
    spread = diagnostics.get("spread")
    rel_atr = diagnostics.get("rel_atr")
    reason = diagnostics.get("reason")

    if spread is not None:
        neutral = 0.0003
        if spread > neutral:
            penalty += min(max_penalty, (spread / neutral - 1) * 100 * 0.5)

    if rel_atr is not None:
        if rel_atr > 0.001:
            penalty += min(max_penalty, (rel_atr / 0.001) * 10)

    if reason is not None and reason != "no_spread_info":
        penalty += 10.0

    final = max(0.0, score - penalty)
    return final

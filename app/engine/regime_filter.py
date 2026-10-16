"""Market regime and data quality filters."""
import time
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.indicators.volatility import calculate_atr, calculate_normalized_atr
from app.indicators.patterns import analyze_candle_structure


class RegimeFilter:
    def __init__(self, stale_seconds: float = 5.0):
        self.stale_seconds = stale_seconds

    def evaluate_pair_health(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        last_quote: Tuple[float, int]
    ) -> Tuple[bool, str]:
        """
        Ensure pair has sufficient historical depth and fresh live updates.
        """
        if not last_quote:
            return False, "NO_TICK_DATA"

        last_price, last_ts = last_quote
        current_ts = int(time.time())

        # Check freshness
        if (current_ts - last_ts) > self.stale_seconds:
            return False, f"STALE_TICK_DATA (age={current_ts - last_ts}s)"

        if len(closed_candles) < 30:
            return False, f"INSUFFICIENT_HISTORY (bars={len(closed_candles)})"

        return True, "HEALTHY"

    def evaluate_volatility_regime(
        self, closed_candles: List[Dict[str, Any]]
    ) -> Tuple[bool, str, float]:
        """
        Evaluate normalized ATR.
        Rejects extreme volatility spikes or dead/flat conditions.
        """
        highs = [c["high"] for c in closed_candles]
        lows = [c["low"] for c in closed_candles]
        closes = [c["close"] for c in closed_candles]

        atr_series = calculate_atr(highs, lows, closes, period=14)
        if not atr_series:
            return False, "ATR_CALC_FAILED", 0.0

        current_atr = atr_series[-1]
        last_price = closes[-1]
        natr_bps = calculate_normalized_atr(current_atr, last_price)

        # Baseline criteria for M1 OTC:
        # Minimum NATR ~ 1.5 bps (avoid completely dead spreads)
        # Maximum NATR ~ 45.0 bps (avoid erratic news/liquidity flash spikes)
        if natr_bps < 1.0:
            return False, f"VOLATILITY_TOO_LOW ({natr_bps:.1f} bps)", natr_bps
        if natr_bps > 55.0:
            return False, f"VOLATILITY_TOO_HIGH ({natr_bps:.1f} bps)", natr_bps

        # Also check last candle size against average ATR
        last_range = highs[-1] - lows[-1]
        if last_range > (current_atr * 3.5):
            return False, "ABNORMAL_IMPULSE_SPIKE", natr_bps

        return True, "STABLE", natr_bps


regime_filter = RegimeFilter(stale_seconds=settings.DATA_STALE_SECONDS)

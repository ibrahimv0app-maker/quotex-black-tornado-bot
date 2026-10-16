"""Strategy D: Support/Resistance Rejection with Pinbar / Engulfing."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.patterns import analyze_candle_structure


class SupportResistanceStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Support/Resistance Rejection")

    def evaluate(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        forming_candle: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        if len(closed_candles) < 30:
            return None

        recent_window = closed_candles[-25:-1]
        swing_high = max(c["high"] for c in recent_window)
        swing_low = min(c["low"] for c in recent_window)

        last_c = closed_candles[-1]
        struct = analyze_candle_structure(last_c)

        # Support Rejection (CALL): Low touched swing low area within 0.05% and rejected
        if abs(last_c["low"] - swing_low) / swing_low < 0.0006 and struct["rejection"] == "BULLISH_REJECTION":
            return StrategySignal(
                strategy_name=self.name,
                symbol=symbol,
                direction="CALL",
                score=78.0,
                reason=f"Pinbar rejection at horizontal swing support ({swing_low:.5f})",
                indicators={"swing_low": swing_low, "rejection": struct["rejection"]},
                confirmations=["Key level test", "Pinbar wick", "Support hold"]
            )

        # Resistance Rejection (PUT): High touched swing high area within 0.05% and rejected
        if abs(last_c["high"] - swing_high) / swing_high < 0.0006 and struct["rejection"] == "BEARISH_REJECTION":
            return StrategySignal(
                strategy_name=self.name,
                symbol=symbol,
                direction="PUT",
                score=78.0,
                reason=f"Pinbar rejection at horizontal swing resistance ({swing_high:.5f})",
                indicators={"swing_high": swing_high, "rejection": struct["rejection"]},
                confirmations=["Key level test", "Pinbar wick", "Resistance hold"]
            )

        return None

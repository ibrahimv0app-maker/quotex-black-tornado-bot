"""Strategy C: Range Mean Reversion (Bollinger Bands + RSI Extremes + Wick Rejection)."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.technical import calculate_bollinger_bands, calculate_rsi
from app.indicators.patterns import analyze_candle_structure


class MeanReversionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Range Mean Reversion")

    def evaluate(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        forming_candle: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        if len(closed_candles) < 30:
            return None

        closes = [c["close"] for c in closed_candles]
        bb = calculate_bollinger_bands(closes, 20, 2.0)
        rsi = calculate_rsi(closes, 14)

        if not (bb["upper"] and rsi):
            return None

        last_c = closed_candles[-1]
        u = bb["upper"][-1]
        l = bb["lower"][-1]
        r = rsi[-1]
        struct = analyze_candle_structure(last_c)

        # CALL setup: Price pierced lower band, formed a bullish rejection wick, RSI oversold
        if last_c["low"] <= l and r <= 32.0 and struct["lower_wick_ratio"] >= 0.40:
            return StrategySignal(
                strategy_name=self.name,
                symbol=symbol,
                direction="CALL",
                score=84.0,
                reason="Bollinger Lower Band pierce with lower wick rejection and oversold RSI",
                indicators={"bb_lower": round(l, 5), "rsi": round(r, 1)},
                confirmations=["Lower band bounce", "RSI oversold", "Bullish rejection wick"]
            )

        # PUT setup: Price pierced upper band, formed an upper wick rejection, RSI overbought
        if last_c["high"] >= u and r >= 68.0 and struct["upper_wick_ratio"] >= 0.40:
            return StrategySignal(
                strategy_name=self.name,
                symbol=symbol,
                direction="PUT",
                score=84.0,
                reason="Bollinger Upper Band pierce with upper wick rejection and overbought RSI",
                indicators={"bb_upper": round(u, 5), "rsi": round(r, 1)},
                confirmations=["Upper band bounce", "RSI overbought", "Bearish rejection wick"]
            )

        return None

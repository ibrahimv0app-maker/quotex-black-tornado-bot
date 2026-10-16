"""Strategy B: Momentum Continuation (MACD + Directional Consistency)."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.technical import calculate_macd, calculate_ema
from app.indicators.patterns import analyze_candle_structure


class MomentumStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Momentum Continuation")

    def evaluate(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        forming_candle: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        if len(closed_candles) < 35:
            return None

        closes = [c["close"] for c in closed_candles]
        macd = calculate_macd(closes, 12, 26, 9)
        ema20 = calculate_ema(closes, 20)

        if not (macd["histogram"] and len(macd["histogram"]) >= 3 and ema20):
            return None

        h = macd["histogram"]
        last_c = closed_candles[-1]
        prev_c = closed_candles[-2]
        s_last = analyze_candle_structure(last_c)

        # Bullish momentum: Histogram positive & growing, consecutive bullish closes
        if h[-1] > 0 and h[-1] > h[-2] > h[-3] and closes[-1] > ema20[-1]:
            if s_last["is_bullish"] and s_last["body_ratio"] >= 0.45:
                return StrategySignal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction="CALL",
                    score=80.0,
                    reason="Expanding bullish MACD histogram with strong directional body",
                    indicators={"macd_hist": round(h[-1], 6), "ema20": ema20[-1]},
                    confirmations=["MACD expansion", "Above EMA20", "Healthy candle body"]
                )

        # Bearish momentum: Histogram negative & descending, consecutive bearish closes
        if h[-1] < 0 and h[-1] < h[-2] < h[-3] and closes[-1] < ema20[-1]:
            if s_last["is_bearish"] and s_last["body_ratio"] >= 0.45:
                return StrategySignal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction="PUT",
                    score=80.0,
                    reason="Expanding bearish MACD histogram with strong directional body",
                    indicators={"macd_hist": round(h[-1], 6), "ema20": ema20[-1]},
                    confirmations=["MACD bearish expansion", "Below EMA20", "Healthy candle body"]
                )

        return None

"""Strategy A: Trend Pullback (EMA Alignment + Pullback + RSI)."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.technical import calculate_ema, calculate_rsi
from app.indicators.patterns import analyze_candle_structure


class TrendPullbackStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Trend Pullback")

    def evaluate(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        forming_candle: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        if len(closed_candles) < 55:
            return None

        closes = [c["close"] for c in closed_candles]
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        rsi = calculate_rsi(closes, 14)

        if not (ema9 and ema21 and ema50 and rsi):
            return None

        last_close = closes[-1]
        e9, e21, e50 = ema9[-1], ema21[-1], ema50[-1]
        r = rsi[-1]
        last_struct = analyze_candle_structure(closed_candles[-1])

        # 1. Bullish Trend Pullback: EMA9 > EMA21 > EMA50, price near EMA21, RSI between 42 and 65
        if e9 > e21 > e50 and (e21 > ema21[-5]):
            # Price pulled back to EMA9/EMA21 zone
            if last_close >= (e21 * 0.999) and (last_struct["is_bullish"] or last_struct["rejection"] == "BULLISH_REJECTION"):
                if 42.0 <= r <= 68.0:
                    return StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        direction="CALL",
                        score=82.0,
                        reason="Bullish EMA stack (9>21>50) with bounce from EMA dynamic support",
                        indicators={"ema9": e9, "ema21": e21, "ema50": e50, "rsi": round(r, 1)},
                        confirmations=["EMA alignment bullish", "Pullback support respected", "RSI healthy"]
                    )

        # 2. Bearish Trend Pullback: EMA9 < EMA21 < EMA50, price near EMA21, RSI between 32 and 58
        if e9 < e21 < e50 and (e21 < ema21[-5]):
            if last_close <= (e21 * 1.001) and (last_struct["is_bearish"] or last_struct["rejection"] == "BEARISH_REJECTION"):
                if 32.0 <= r <= 58.0:
                    return StrategySignal(
                        strategy_name=self.name,
                        symbol=symbol,
                        direction="PUT",
                        score=82.0,
                        reason="Bearish EMA stack (9<21<50) with rejection from EMA dynamic resistance",
                        indicators={"ema9": e9, "ema21": e21, "ema50": e50, "rsi": round(r, 1)},
                        confirmations=["EMA alignment bearish", "Pullback resistance respected", "RSI healthy"]
                    )

        return None

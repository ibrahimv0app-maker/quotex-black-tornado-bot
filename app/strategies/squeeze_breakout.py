"""Strategy E: Volatility Squeeze Breakout."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.technical import calculate_bollinger_bands
from app.indicators.patterns import analyze_candle_structure


class SqueezeBreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Volatility Squeeze Breakout")

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
        bw = bb["bandwidth"]

        if not bw or len(bw) < 10:
            return None

        # Check if bandwidth was compressed in prior 8 bars
        prior_bw = bw[-8:-1]
        avg_prior_bw = sum(prior_bw) / len(prior_bw)
        current_bw = bw[-1]

        # Breakout expansion: current bandwidth expanded by at least 30% over squeeze
        if current_bw > avg_prior_bw * 1.3:
            last_c = closed_candles[-1]
            struct = analyze_candle_structure(last_c)

            # Bullish expansion break
            if last_c["close"] > bb["upper"][-1] and struct["is_bullish"]:
                return StrategySignal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction="CALL",
                    score=79.0,
                    reason="Volatility expansion breakout above upper Bollinger band",
                    indicators={"bandwidth_expansion": round(current_bw / avg_prior_bw, 2)},
                    confirmations=["Squeeze release", "Band expansion", "Bullish candle close"]
                )

            # Bearish expansion break
            if last_c["close"] < bb["lower"][-1] and struct["is_bearish"]:
                return StrategySignal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction="PUT",
                    score=79.0,
                    reason="Volatility expansion breakout below lower Bollinger band",
                    indicators={"bandwidth_expansion": round(current_bw / avg_prior_bw, 2)},
                    confirmations=["Squeeze release", "Band expansion", "Bearish candle close"]
                )

        return None

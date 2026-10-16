"""Chronological backtesting engine without lookahead bias."""
from typing import List, Dict, Any, Optional
from app.strategies.base import BaseStrategy
from app.engine.regime_filter import regime_filter
from app.engine.candidate_scorer import candidate_scorer


class BacktestEngine:
    def __init__(self, strategies: List[BaseStrategy], min_score: float = 75.0):
        self.strategies = strategies
        self.min_score = min_score

    def run(self, symbol: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run backtest over chronological series of candles.
        Candle i: Decision time.
        Candle i+1: Trade execution and expiry (M1).
        """
        if len(candles) < 60:
            return {
                "symbol": symbol,
                "error": "Insufficient history (<60 bars)",
                "total_trades": 0,
                "win_rate": 0.0
            }

        trades = []
        in_trade_until_index = -1
        consecutive_losses = 0
        max_consecutive_losses = 0

        # Iterate through historical candles
        for i in range(50, len(candles) - 1):
            if i <= in_trade_until_index:
                continue  # In active trade lifecycle (global lock)

            # Strictly past candles available at decision time
            closed_slice = candles[: i + 1]

            vol_ok, _, natr_bps = regime_filter.evaluate_volatility_regime(closed_slice)
            if not vol_ok:
                continue

            candidates = []
            for strat in self.strategies:
                sig = strat.evaluate(symbol, closed_slice)
                if sig:
                    score = candidate_scorer.score_candidate(sig, closed_slice, natr_bps)
                    candidates.append({"signal": sig, "composite_score": score})

            winner = candidate_scorer.select_best_candidate(candidates)
            if not winner:
                continue

            # Trade entered on next candle i+1
            trade_candle = candles[i + 1]
            entry_price = trade_candle["open"]
            expiry_price = trade_candle["close"]
            direction = winner["signal"].direction

            delta = expiry_price - entry_price
            if abs(delta) < 1e-6:
                outcome = "DRAW"
            elif direction == "CALL":
                outcome = "WIN" if delta > 0 else "LOSS"
            else:  # PUT
                outcome = "WIN" if delta < 0 else "LOSS"

            if outcome == "LOSS":
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            elif outcome == "WIN":
                consecutive_losses = 0

            trades.append({
                "entry_time": trade_candle["time"],
                "strategy": winner["signal"].strategy_name,
                "direction": direction,
                "entry_price": entry_price,
                "expiry_price": expiry_price,
                "delta": delta,
                "outcome": outcome,
                "score": winner["composite_score"]
            })

            in_trade_until_index = i + 1  # lock released after candle i+1

        wins = sum(1 for t in trades if t["outcome"] == "WIN")
        losses = sum(1 for t in trades if t["outcome"] == "LOSS")
        draws = sum(1 for t in trades if t["outcome"] == "DRAW")
        decisive = wins + losses
        win_rate = round((wins / decisive * 100), 2) if decisive > 0 else 0.0

        return {
            "symbol": symbol,
            "candles_analyzed": len(candles),
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": win_rate,
            "max_consecutive_losses": max_consecutive_losses,
            "trades": trades
        }

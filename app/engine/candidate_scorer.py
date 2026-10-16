"""Candidate ranking and multi-factor composite scoring engine with Black Tornado integration."""
from typing import List, Dict, Any, Optional
from app.config import settings
from app.strategies.base import StrategySignal


class CandidateScorer:
    def __init__(self, min_score: float = 75.0):
        self.min_score = min_score

    def score_candidate(
        self,
        signal: StrategySignal,
        closed_candles: List[Dict[str, Any]],
        natr_bps: float,
        tornado_output: Any = None
    ) -> float:
        """
        Compute transparent 0-100 composite score based on Black Tornado outputs:
        1. Strategy setup quality: 25 pts
        2. BT Directional / candle pressure: 20 pts
        3. Higher-timeframe / Structure alignment: 20 pts
        4. Volatility stability & low turbulence: 20 pts
        5. BT Confidence / internal consistency: 15 pts
        """
        # 1. Strategy setup points (normalized from strategy's base score)
        p_strat = min(25.0, (signal.score / 100.0) * 25.0)

        # 2. BT Directional strength & candle pressure
        p_dir = 10.0
        if tornado_output:
            direction_mag = abs(getattr(tornado_output, 'bt_direction', 0.0))
            p_dir = min(20.0, (direction_mag / 100.0) * 20.0)
        else:
            last_c = closed_candles[-1]
            is_bull = last_c["close"] > last_c["open"]
            is_bear = last_c["close"] < last_c["open"]
            if (signal.direction == "CALL" and is_bull) or (signal.direction == "PUT" and is_bear):
                p_dir = 20.0

        # 3. Structure & HTF alignment
        p_align = 10.0
        if tornado_output:
            htf = getattr(tornado_output, 'bt_htf_alignment', 'NEUTRAL')
            struct = getattr(tornado_output, 'bt_structure', 'MIXED')
            if (signal.direction == "CALL" and htf == "BULLISH") or (signal.direction == "PUT" and htf == "BEARISH"):
                p_align += 5.0
            if (signal.direction == "CALL" and struct == "HH_HL") or (signal.direction == "PUT" and struct == "LH_LL"):
                p_align += 5.0
        else:
            p_align = 15.0

        # 4. Volatility stability (ideal range: 5 to 30 bps, low turbulence)
        p_vol = 15.0
        if tornado_output:
            turb = getattr(tornado_output, 'bt_turbulence', 0.0)
            if turb < 30 and 5.0 <= natr_bps <= 35.0:
                p_vol = 20.0
            elif turb > 60 or natr_bps > 45.0:
                p_vol = 8.0
        else:
            if 5.0 <= natr_bps <= 25.0:
                p_vol = 20.0

        # 5. BT Confidence / internal consistency
        p_conf = 10.0
        if tornado_output:
            conf = getattr(tornado_output, 'bt_confidence', 50.0)
            p_conf = min(15.0, (conf / 100.0) * 15.0)
        else:
            p_conf = min(15.0, len(signal.confirmations) * 5.0)

        total_score = round(p_strat + p_dir + p_align + p_vol + p_conf, 1)
        return min(100.0, total_score)

    def select_best_candidate(
        self, scored_signals: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Filter candidates below threshold and select the single best opportunity.
        """
        qualified = [s for s in scored_signals if s["composite_score"] >= self.min_score]
        if not qualified:
            return None

        # Sort descending by composite score, then by strategy score
        qualified.sort(key=lambda s: (s["composite_score"], s["signal"].score), reverse=True)
        return qualified[0]


candidate_scorer = CandidateScorer(min_score=settings.MIN_SETUP_SCORE)

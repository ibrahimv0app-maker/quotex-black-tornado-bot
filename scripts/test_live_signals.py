import asyncio
import time
from app.config import settings
from app.feed.client import feed_client
from app.feed.candle_store import candle_store
from app.engine.regime_filter import regime_filter
from app.engine.candidate_scorer import candidate_scorer
from app.strategies.trend_pullback import TrendPullbackStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.support_resistance import SupportResistanceStrategy
from app.strategies.squeeze_breakout import SqueezeBreakoutStrategy

async def main():
    strategies = [
        TrendPullbackStrategy(),
        MomentumStrategy(),
        MeanReversionStrategy(),
        SupportResistanceStrategy(),
        SqueezeBreakoutStrategy()
    ]
    print("Connecting to live feed https://quotexfeed.lovable.app ...")
    candidates = []

    # Check active pairs
    symbols = settings.ACTIVE_SYMBOLS[:30]
    for sym in symbols:
        try:
            candles = await feed_client.fetch_candles(sym, interval="1m", limit=60)
            if not candles or len(candles) < 30:
                continue
            candle_store.load_initial_candles(sym, candles)
            closed = candle_store.get_closed_candles(sym, limit=60)
            quote = candle_store.get_last_quote(sym)

            # Volatility check
            vol_ok, v_reason, natr_bps = regime_filter.evaluate_volatility_regime(closed)

            for strat in strategies:
                sig = strat.evaluate(sym, closed)
                if sig:
                    score = candidate_scorer.score_candidate(sig, closed, natr_bps)
                    candidates.append({
                        "signal": sig,
                        "composite_score": score,
                        "natr_bps": natr_bps,
                        "last_price": quote[0] if quote else closed[-1]["close"],
                        "last_candle_time": closed[-1]["time"]
                    })
        except Exception as e:
            pass

    await feed_client.close()

    print(f"\n=======================================================")
    print(f"LIVE SCAN RESULT: Found {len(candidates)} candidate signals across 30 pairs")
    print(f"=======================================================")

    winner = candidate_scorer.select_best_candidate(candidates)
    if winner:
        sig = winner["signal"]
        print(f"\n🏆 TOP SELECTED SIGNAL (Meets >= {settings.MIN_SETUP_SCORE} Threshold):")
        print(f"   Pair:        {sig.symbol}")
        print(f"   Direction:   {sig.direction}")
        print(f"   Strategy:    {sig.strategy_name}")
        print(f"   Score:       {winner['composite_score']:.1f} / 100")
        print(f"   Quote:       {winner['last_price']}")
        print(f"   Reason:      {sig.reason}")
        print(f"   Confirmations:")
        for c in sig.confirmations:
            print(f"     • {c}")
    else:
        print(f"\n⚠️ NO SIGNAL MET THE STRICT THRESHOLD (>= {settings.MIN_SETUP_SCORE}/100)")
        print("Here are the top runner-up candidate scores:")
        for c in sorted(candidates, key=lambda x: x["composite_score"], reverse=True)[:5]:
            s = c["signal"]
            print(f"   - {s.symbol:<14} {s.direction:<4} [{c['composite_score']:.1f}/100] via {s.strategy_name:<22} | {s.reason}")

if __name__ == "__main__":
    asyncio.run(main())

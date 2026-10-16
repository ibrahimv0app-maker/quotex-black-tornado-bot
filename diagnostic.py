"""Diagnostic CLI tool for Quotex M1 Feed validation, pair health, and backtesting."""
import sys
import time
import asyncio
import aiohttp
from app.config import settings
from app.feed.client import feed_client
from app.feed.symbol_registry import symbol_registry
from app.backtesting.engine import BacktestEngine
from app.backtesting.reports import generate_backtest_summary_text
from app.strategies.trend_pullback import TrendPullbackStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.support_resistance import SupportResistanceStrategy
from app.strategies.squeeze_breakout import SqueezeBreakoutStrategy


async def run_pair_discovery():
    print("=" * 60)
    print("QUOTEX FEED: SCANNING ALL 48 DOCUMENTED PAIRS")
    print("=" * 60)
    available = []
    empty_or_failed = []

    sem = asyncio.Semaphore(5)

    async def check(sym: str):
        async with sem:
            t0 = time.time()
            diag = await feed_client.health_check_symbol(sym)
            latency_ms = round((time.time() - t0) * 1000)
            if diag["status"] == "HEALTHY":
                available.append((sym, diag["candle_count"], diag["last_candle_time"], latency_ms))
            else:
                empty_or_failed.append((sym, diag["status"], latency_ms))

    tasks = [check(s) for s in symbol_registry.ALL_SYMBOLS]
    await asyncio.gather(*tasks)

    print(f"\n[AVAILABLE WITH DATA: {len(available)} / {len(symbol_registry.ALL_SYMBOLS)}]")
    for sym, cnt, last_time, lat in sorted(available):
        print(f"  ✓ {sym:<15} | Candles: {cnt:<5} | Last Time: {last_time} | Latency: {lat}ms")

    if empty_or_failed:
        print(f"\n[NO CANDLES / RETURNING 0 BARS: {len(empty_or_failed)}]")
        for sym, stat, lat in sorted(empty_or_failed):
            print(f"  ✗ {sym:<15} | Status: {stat} | Latency: {lat}ms")

    await feed_client.close()


async def run_sample_backtest(symbol: str = "EURUSD-OTC"):
    print("=" * 60)
    print(f"RUNNING HISTORICAL BACKTEST FOR {symbol}")
    print("=" * 60)
    candles = await feed_client.fetch_candles(symbol, interval="1m", limit=300)
    if not candles:
        print(f"Error: Could not fetch candle data for {symbol}")
        await feed_client.close()
        return

    strategies = [
        TrendPullbackStrategy(),
        MomentumStrategy(),
        MeanReversionStrategy(),
        SupportResistanceStrategy(),
        SqueezeBreakoutStrategy()
    ]
    engine = BacktestEngine(strategies, min_score=75.0)
    report = engine.run(symbol, candles)
    print(generate_backtest_summary_text(report))
    await feed_client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        target = sys.argv[2] if len(sys.argv) > 2 else "EURUSD-OTC"
        asyncio.run(run_sample_backtest(target))
    else:
        asyncio.run(run_pair_discovery())

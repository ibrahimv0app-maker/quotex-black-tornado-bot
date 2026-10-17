"""Backtest historical simulator for Quotex Black Tornado Bot.

Usage:
  python scripts/backtest_historical.py --symbols EURUSD-OTC,USDJPY-OTC --from 2026-09-01 --to 2026-09-30

This script replays minute candles from the database and simulates the scheduler + outcome lifecycle
including single-step martingale recovery behavior implemented in the engine. Results are written to
backtest_trades.csv and backtest_summary.json in the repository root.

Notes:
- Designed to run in PAPER_MODE. It uses the repository candle table for historical data.
- It attempts to reuse the same evaluation logic as the live scheduler: Black Tornado composite,
  25 strategies (build_strategies), candidate_scorer selection, regime_filter volatility checks.
- The backtest simplifies some real-time assumptions (network timing, feed freshness). It's meant
  for comparative experiments (disable/enable martingale, change thresholds).
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.config import settings
from app.database.repository import DatabaseRepository
from app.database.models import CandleRecord
from app.engine.candidate_scorer import candidate_scorer
from app.engine.regime_filter import regime_filter
from app.indicators.black_tornado import black_tornado, TornadoOutput
from app.strategies.black_tornado import build_strategies
from app.notifications.telegram import telegram_notifier

logger = logging.getLogger("backtest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def fetch_candles(repo: DatabaseRepository, symbol: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    """Fetch candles for symbol between start_ts and end_ts inclusive, ordered by time asc."""
    async with repo.session_factory() as session:
        stmt = (
            session.execute
        )
        # Use raw query via SQLAlchemy select
        from sqlalchemy import select, and_
        q = select(CandleRecord).where(and_(CandleRecord.symbol == symbol, CandleRecord.time >= start_ts, CandleRecord.time <= end_ts)).order_by(CandleRecord.time.asc())
        res = await session.execute(q)
        rows = res.scalars().all()
        candles = []
        for r in rows:
            candles.append({
                "time": int(r.time),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume or 0.0),
            })
        return candles


def candles_to_map(candles: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {c["time"]: c for c in candles}


def timestamp_from_date(s: str) -> int:
    # accept YYYY-MM-DD
    dt = datetime.fromisoformat(s)
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


async def run_backtest(symbols: List[str], start_ts: int, end_ts: int, martingale_enabled: bool):
    repo = DatabaseRepository()
    strategies = build_strategies()

    # load candles per symbol
    symbol_candles: Dict[str, List[Dict[str, Any]]] = {}
    symbol_maps: Dict[str, Dict[int, Dict[str, Any]]] = {}
    all_times = set()
    for sym in symbols:
        c = await fetch_candles(repo, sym, start_ts, end_ts)
        if not c:
            logger.warning(f"No candles for {sym} in range; skipping")
            continue
        symbol_candles[sym] = c
        m = candles_to_map(c)
        symbol_maps[sym] = m
        all_times.update([candle["time"] for candle in c])

    if not symbol_candles:
        logger.error("No symbols with candles found. Abort.")
        return

    # timeline sorted
    times = sorted(all_times)

    # state
    simulated_signals: List[Dict[str, Any]] = []
    outcomes: List[Dict[str, Any]] = []
    pending_recovery: Dict[str, Dict[str, Any]] = {}  # symbol -> parent signal dict

    # helper to resolve signal immediately using candle-map (simulated expiry)
    def resolve_signal(signal: Dict[str, Any]):
        symbol = signal["symbol"]
        entry = signal["intended_entry_time"]
        expiry = signal["intended_expiry_time"]
        smap = symbol_maps.get(symbol, {})
        entry_c = smap.get(entry)
        expiry_c = smap.get(expiry)
        entry_q = entry_c["open"] if entry_c else signal.get("signal_price")
        expiry_q = expiry_c["open"] if expiry_c else (entry_c["close"] if entry_c else None)
        outcome = "UNVERIFIED"
        reason = None
        delta = None
        verified = False
        if entry_q is not None and expiry_q is not None:
            delta = expiry_q - entry_q
            verified = True
            if abs(delta) < 1e-9:
                outcome = "DRAW"
                reason = "identical"
            elif signal["direction"] == "CALL":
                outcome = "WIN" if delta > 0 else "LOSS"
                reason = f"delta={delta:.6f}"
            else:
                outcome = "WIN" if delta < 0 else "LOSS"
                reason = f"delta={delta:.6f}"
        else:
            outcome = "UNVERIFIED"
            reason = "missing_quotes"

        return {
            "signal_id": signal["signal_id"],
            "symbol": symbol,
            "direction": signal["direction"],
            "outcome": outcome,
            "reason": reason,
            "entry_quote": entry_q,
            "expiry_quote": expiry_q,
            "price_delta": delta,
            "is_verified": verified,
            "evaluated_at": expiry or int(time.time()),
            "is_recovery": signal.get("is_recovery", False),
            "parent_id": signal.get("recovery_parent")
        }

    # main simulation loop over times
    for now_ts in times:
        # emulate scheduler timing: evaluate at second before the next minute (we just consider minute slots)
        for sym, candles in symbol_candles.items():
            # form closed candles prior to now_ts (excluding current candle?) use candles with time < now_ts
            closed = [c for c in candles if c["time"] < now_ts]
            if len(closed) < 30:
                continue

            # check health + volatility via regime_filter
            vol_ok, v_reason, natr_bps = regime_filter.evaluate_volatility_regime(closed)
            if not vol_ok:
                continue

            # run black tornado
            tornado_out = black_tornado.evaluate(closed, data_fresh=True, data_timestamp=now_ts, now_timestamp=now_ts)
            if not tornado_out.bt_data_ok or tornado_out.bt_regime in {"CHAOS", "UNKNOWN"}:
                continue

            eval_context = {"tornado": tornado_out, "data_fresh": True, "data_timestamp": now_ts, "now_timestamp": now_ts}

            # evaluate strategies
            candidates = []
            for strat in strategies:
                sig = strat.evaluate(sym, closed, context=eval_context)
                if sig:
                    score = candidate_scorer.score_candidate(sig, closed, natr_bps, tornado_output=tornado_out)
                    last_price = symbol_maps[sym].get(closed[-1]["time"], {}).get("close", closed[-1]["close"])
                    candidates.append({"signal": sig, "composite_score": score, "natr_bps": natr_bps, "closed_candles": closed, "tornado_output": tornado_out, "last_price": last_price})

            if not candidates:
                continue

            # pick best
            winner = candidate_scorer.select_best_candidate(candidates)
            if not winner:
                continue

            sig = winner["signal"]
            score = winner["composite_score"]

            # construct simulated signal
            entry_slot = now_ts  # use current slot as entry
            expiry_slot = entry_slot + settings.EXPIRY_SECONDS
            signal_id = f"BT_{entry_slot}_{sym.replace('-', '')}_{len(simulated_signals)}"

            # compute pos_size if provided in indicators, else simple fixed sizing
            indicators = getattr(sig, "indicators", {}) or {}
            pos_size = indicators.get("pos_size") or settings.RISK_PER_TRADE

            # determine martingale application: if a pending recovery exists for this symbol and conditions match
            is_recovery = False
            recovery_parent = None
            if martingale_enabled and sym in pending_recovery:
                parent = pending_recovery[sym]
                # only apply recovery for same direction
                if parent["direction"] == sig.direction:
                    is_recovery = True
                    recovery_parent = parent["signal_id"]
                    # apply multiplier to pos_size
                    pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
                    # clear pending
                    del pending_recovery[sym]

            simulated = {
                "signal_id": signal_id,
                "symbol": sym,
                "direction": sig.direction,
                "strategy_name": sig.strategy_name,
                "setup_score": score,
                "signal_sent_time": now_ts,
                "intended_entry_time": entry_slot,
                "intended_expiry_time": expiry_slot,
                "signal_price": winner["last_price"],
                "status": "ACTIVE",
                "details": {"confirmations": sig.confirmations, "indicators": indicators, "pos_size": pos_size, "martingale_applied": is_recovery, "recovery_parent": recovery_parent},
                "is_recovery": is_recovery,
                "recovery_parent": recovery_parent
            }

            simulated_signals.append(simulated)

            # resolve immediately at expiry (for backtest we can fast-forward)
            res = resolve_signal(simulated)

            # If not recovery and LOSS and martingale enabled -> mark pending
            if res["outcome"] == "LOSS" and not res["is_recovery"] and martingale_enabled:
                # store parent to pending_recovery keyed by symbol
                pending_recovery[sym] = simulated
                # do not record outcome yet (waiting for recovery)
                logger.info(f"Backtest: signal {simulated['signal_id']} LOST -> pending recovery")
            else:
                # if recovery signal and has parent, we must also mark parent outcome accordingly
                if res["is_recovery"] and res.get("parent_id"):
                    parent_id = res.get("parent_id")
                    # find parent in simulated_signals
                    parent = next((s for s in simulated_signals if s["signal_id"] == parent_id), None)
                    if parent:
                        if res["outcome"] == "WIN":
                            # recovered: parent considered WIN
                            outcomes.append({**res, "final_for": parent_id, "recovered": True})
                            # also record parent as recovered outcome
                            outcomes.append({"signal_id": parent_id, "symbol": parent["symbol"], "direction": parent["direction"], "outcome": "RECOVERED", "reason": f"Recovered by {simulated['signal_id']}", "evaluated_at": res["evaluated_at"], "is_recovery": False})
                        else:
                            # recovery failed: record both as LOSS
                            outcomes.append({**res, "final_for": parent_id, "recovered": False})
                            outcomes.append({"signal_id": parent_id, "symbol": parent["symbol"], "direction": parent["direction"], "outcome": "LOSS", "reason": f"Recovery {simulated['signal_id']} failed", "evaluated_at": res["evaluated_at"], "is_recovery": False})
                    else:
                        outcomes.append(res)
                else:
                    # normal resolved signal
                    outcomes.append(res)

            # Every time we append outcomes, if total outcomes % 10 == 0, send summary via telegram_notifier (DRY-RUN logs if no token)
            if len(outcomes) > 0 and len(outcomes) % 10 == 0:
                recent = outcomes[-10:]
                # format to expected dict list for notifier
                recent_fmt = [{"signal_id": o.get("signal_id"), "symbol": o.get("symbol"), "direction": o.get("direction"), "outcome": o.get("outcome"), "evaluated_at": o.get("evaluated_at")} for o in recent]
                await telegram_notifier.broadcast_summary(recent_fmt)

    # write CSV of trades
    csv_path = os.path.join(os.getcwd(), "backtest_trades.csv")
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["signal_id", "symbol", "direction", "outcome", "is_recovery", "parent_id", "evaluated_at"]) 
        for o in outcomes:
            writer.writerow([o.get("signal_id"), o.get("symbol"), o.get("direction"), o.get("outcome"), o.get("is_recovery"), o.get("parent_id"), o.get("evaluated_at")])

    # summary per-pair
    summary = {}
    for sym in symbols:
        stats = await repo.get_pair_stats(sym)
        summary[sym] = stats

    summary_path = os.path.join(os.getcwd(), "backtest_summary.json")
    with open(summary_path, "w", encoding='utf-8') as f:
        json.dump({"summary": summary, "trades_count": len(outcomes)}, f, indent=2, default=str)

    logger.info(f"Backtest complete. Trades: {len(outcomes)}. CSV: {csv_path} JSON: {summary_path}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", type=str, required=True, help="Comma separated symbols")
    p.add_argument("--from", dest="from_date", type=str, required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--to", dest="to_date", type=str, required=True, help="End date YYYY-MM-DD")
    p.add_argument("--no-martingale", dest="no_mart", action="store_true", help="Disable martingale during backtest")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    start_ts = timestamp_from_date(args.from_date)
    # include entire to day by adding 86399 seconds
    end_ts = timestamp_from_date(args.to_date) + 86399
    mart = not args.no_mart
    asyncio.run(run_backtest(syms, start_ts, end_ts, mart))

"""Precision clock-driven scheduler and multi-pair evaluation pipeline using Black Tornado v1.0."""
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.feed.symbol_registry import symbol_registry
from app.feed.candle_store import candle_store
from app.feed.client import feed_client
from app.database.repository import DatabaseRepository
from app.engine.regime_filter import regime_filter
from app.engine.candidate_scorer import candidate_scorer
from app.engine.outcome_tracker import OutcomeTracker
from app.notifications.telegram import telegram_notifier

# Import Black Tornado composite and 25 strategies
from app.indicators.black_tornado import black_tornado, TornadoOutput
from app.strategies.black_tornado import build_strategies

logger = logging.getLogger(__name__)


class SignalScheduler:
    def __init__(self, db_repo: DatabaseRepository):
        self.db = db_repo
        self.outcome_tracker = OutcomeTracker(db_repo)
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.strategies = build_strategies()
        self.last_evaluated_slot: int = 0
        self.diagnostic_stats = {
            "cycles_run": 0,
            "candidates_evaluated": 0,
            "signals_dispatched": 0,
            "last_scan_time": 0
        }

    async def start(self):
        self.is_running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info(f"SignalScheduler 24/7 scanning loop started with {len(self.strategies)} Black Tornado strategies.")

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SignalScheduler stopped.")

    async def _main_loop(self):
        while self.is_running:
            try:
                t0 = time.time()
                await self._tick()
                elapsed = time.time() - t0
                sleep_time = max(0.1, settings.SCAN_INTERVAL_SECONDS - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _tick(self):
        now_ts = int(time.time())
        self.diagnostic_stats["cycles_run"] += 1
        self.diagnostic_stats["last_scan_time"] = now_ts

        # 1. Check if there is an active unresolved signal awaiting outcome settlement
        active_sig = await self.db.get_active_signal()
        if active_sig:
            settled = await self.outcome_tracker.settle_signal(active_sig)
            if not settled:
                # Active signal still underway; global lock enforces NO NEW SIGNALS
                return

        if settings.KILL_SWITCH_ACTIVE:
            return

        # 2. Timing check: target entry is the start of the next minute
        next_entry_slot = ((now_ts // 60) + 1) * 60
        seconds_to_entry = next_entry_slot - now_ts

        # Check if we are within the notification window (e.g. 10 to 15 seconds before entry)
        in_lead_window = (10 <= seconds_to_entry <= 15)

        if not in_lead_window:
            return

        # Prevent re-scanning the same entry slot
        if self.last_evaluated_slot == next_entry_slot:
            return

        self.last_evaluated_slot = next_entry_slot
        logger.info(f"Targeting slot {next_entry_slot} ({seconds_to_entry}s lead time). Evaluating pairs with Black Tornado v1.0...")

        # 3. Evaluate all pairs
        candidates = []
        for symbol in settings.ACTIVE_SYMBOLS:
            closed = candle_store.get_closed_candles(symbol, limit=120)
            quote = candle_store.get_last_quote(symbol)

            # Health filter
            healthy, h_reason = regime_filter.evaluate_pair_health(symbol, closed, quote)
            if not healthy:
                continue

            # Volatility filter
            vol_ok, v_reason, natr_bps = regime_filter.evaluate_volatility_regime(closed)
            if not vol_ok:
                continue

            # Run Black Tornado Composite
            last_quote_time = quote[1] if quote else int(time.time())
            tornado_out = black_tornado.evaluate(
                closed,
                data_fresh=True,
                data_timestamp=last_quote_time,
                now_timestamp=now_ts
            )

            if not tornado_out.bt_data_ok or tornado_out.bt_regime in {"CHAOS", "UNKNOWN"}:
                continue

            eval_context = {
                "tornado": tornado_out,
                "data_fresh": True,
                "data_timestamp": last_quote_time,
                "now_timestamp": now_ts
            }

            # Run all 25 Black Tornado strategies against standard output
            for strat in self.strategies:
                sig = strat.evaluate(symbol, closed, context=eval_context)
                if sig:
                    score = candidate_scorer.score_candidate(
                        sig, closed, natr_bps, tornado_output=tornado_out
                    )
                    candidates.append({
                        "signal": sig,
                        "composite_score": score,
                        "natr_bps": natr_bps,
                        "closed_candles": closed,
                        "tornado_output": tornado_out,
                        "last_price": quote[0] if quote else closed[-1]["close"]
                    })

        self.diagnostic_stats["candidates_evaluated"] += len(candidates)

        # 4. Global selection: rank and pick at most ONE best candidate
        winner = candidate_scorer.select_best_candidate(candidates)
        if not winner:
            logger.info("Cycle complete: NO QUALIFIED SIGNAL met criteria.")
            return

        sig = winner["signal"]
        score = winner["composite_score"]
        t_out = winner["tornado_output"]
        signal_id = f"BT_{next_entry_slot}_{sig.symbol.split('-')[0]}"
        expiry_slot = next_entry_slot + settings.EXPIRY_SECONDS

        # 5. Acquire atomic database lock
        lock_acquired = await self.db.acquire_signal_lock_and_create(
            signal_id=signal_id,
            symbol=sig.symbol,
            direction=sig.direction,
            strategy_name=sig.strategy_name,
            setup_score=score,
            signal_sent_time=now_ts,
            intended_entry_time=next_entry_slot,
            intended_expiry_time=expiry_slot,
            signal_price=winner["last_price"],
            details={
                "confirmations": sig.confirmations,
                "indicators": sig.indicators,
                "natr_bps": winner["natr_bps"],
                "reason": sig.reason,
                "bt_direction": t_out.bt_direction,
                "bt_confidence": t_out.bt_confidence,
                "bt_regime": t_out.bt_regime,
                "bt_turbulence": t_out.bt_turbulence
            }
        )

        if not lock_acquired:
            logger.warning("Could not acquire global signal lock. Signal publication aborted.")
            return

        # 6. Dispatch to Telegram
        logger.info(f"DISPATCHING BLACK TORNADO SIGNAL #{signal_id}: {sig.symbol} {sig.direction} (Score: {score})")
        vol_label = "Stable"
        if t_out.bt_turbulence < 25:
            vol_label = "Optimal / Low Noise"
        elif t_out.bt_turbulence < 55:
            vol_label = "Stable"
        else:
            vol_label = "Moderate Volatility"

        trend_status = "Trend Confirmed"
        if t_out.bt_htf_alignment != "NEUTRAL":
            trend_status = f"M5/M1 {t_out.bt_htf_alignment.title()} Aligned"
        elif t_out.bt_regime.startswith("TREND"):
            trend_status = "Trend Confirmed"
        elif t_out.bt_regime == "RANGE":
            trend_status = "Range Boundary Confirmed"

        payload = {
            "signal_id": signal_id,
            "signal": sig,
            "composite_score": score,
            "intended_entry_time": next_entry_slot,
            "signal_sent_time": now_ts,
            "intended_expiry_time": expiry_slot,
            "volatility_label": vol_label,
            "trend_status": trend_status
        }
        await telegram_notifier.broadcast_signal(payload)
        self.diagnostic_stats["signals_dispatched"] += 1

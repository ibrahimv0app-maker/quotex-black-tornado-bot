"""Settlement engine tracking 1-minute expiry prices and calculating honest outcomes."""
import time
import logging
import json
from typing import Dict, Any, Optional, Any as AnyType
from app.config import settings
from app.feed.candle_store import candle_store
from app.database.repository import DatabaseRepository
from app.notifications.telegram import telegram_notifier

logger = logging.getLogger(__name__)


class OutcomeTracker:
    def __init__(self, db_repo: DatabaseRepository):
        self.db = db_repo

    def _get_field(self, obj: AnyType, *keys, default=None):
        """Helper to retrieve a value from either a mapping or an ORM object.
        Checks keys in order and returns the first found value; otherwise default.
        """
        # Mapping-like access
        try:
            if isinstance(obj, dict):
                for k in keys:
                    if k in obj:
                        return obj[k]
                return default
        except Exception:
            pass

        # Attribute access for ORM objects
        for k in keys:
            if hasattr(obj, k):
                return getattr(obj, k)
        return default

    async def settle_signal(self, active_sig: Dict[str, Any]) -> bool:
        """
        Evaluate candle prices for entry and expiry, record result, and broadcast.
        Accepts either a dict-like active_sig (legacy) or an ORM SignalRecord instance.
        """
        sig_id = self._get_field(active_sig, "signal_id", "id")
        symbol = self._get_field(active_sig, "symbol")
        direction = self._get_field(active_sig, "direction")
        entry_ts = self._get_field(active_sig, "intended_entry_time", "entry_time")
        expiry_ts = self._get_field(active_sig, "intended_expiry_time", "expiry_time")

        now_ts = int(time.time())
        # Check if enough time has passed (expiry time + small buffer for feed to settle)
        if expiry_ts is None or now_ts < (expiry_ts + 2):
            return False  # not ready to settle yet

        # Retrieve closed candles for this pair
        candles = candle_store.get_closed_candles(symbol, limit=20)
        candle_map = {c["time"]: c for c in candles}

        entry_candle = candle_map.get(entry_ts)
        expiry_candle = candle_map.get(expiry_ts)

        # Fallback to last recorded quotes if exact candle boundary is missing
        entry_quote: Optional[float] = None
        expiry_quote: Optional[float] = None
        outcome = "UNVERIFIED"
        reason = None
        delta: Optional[float] = None
        verified = False

        if entry_candle:
            entry_quote = entry_candle.get("open")
        else:
            entry_quote = self._get_field(active_sig, "signal_price", "entry_price_est")

        # Prefer explicit expiry candle when available
        if expiry_candle:
            expiry_quote = expiry_candle.get("open")
        elif entry_candle:
            # Fallback behavior: use the close of the entry candle if that's all we have
            expiry_quote = entry_candle.get("close")

        if entry_quote is not None and expiry_quote is not None:
            delta = expiry_quote - entry_quote
            verified = True

            if abs(delta) < 1e-6:
                outcome = "DRAW"
                reason = "Entry and Expiry prices were identical"
            elif direction == "CALL":
                if delta > 0:
                    outcome = "WIN"
                    reason = f"Bullish close: +{delta:.5f}"
                else:
                    outcome = "LOSS"
                    reason = f"Bearish close: {delta:.5f}"
            elif direction == "PUT":
                if delta < 0:
                    outcome = "WIN"
                    reason = f"Bearish close: {delta:.5f}"
                else:
                    outcome = "LOSS"
                    reason = f"Bullish close: +{delta:.5f}"
        else:
            outcome = "UNVERIFIED"
            reason = "Missing reliable tick/candle feed observation at settlement time"

        logger.info(f"Settling signal #{sig_id} ({symbol} {direction}): {outcome} (Entry={entry_quote}, Expiry={expiry_quote})")

        # Prepare outcome payload for DB call (repository.resolve_signal expects signal_id + outcome_data dict)
        outcome_data = {
            "outcome": outcome,
            "entry_quote": entry_quote,
            "expiry_quote": expiry_quote,
            "price_delta": delta,
            "is_verified": verified,
            "reason": reason,
            "evaluated_at": now_ts,
        }

        # Extract details from active_sig (support dict or ORM SignalRecord)
        details = {}
        try:
            if isinstance(active_sig, dict):
                details = active_sig.get("details", {}) or {}
            else:
                details = json.loads(getattr(active_sig, "details_json", "{}") or "{}")
        except Exception:
            details = {}

        recovery_parent = details.get("recovery_parent")

        # If this signal is a recovery attempt and has parent, handle combined resolution
        if recovery_parent:
            # Resolve the recovery signal first
            await self.db.resolve_signal(sig_id, outcome_data)

            # Now resolve the parent depending on recovery outcome
            parent_id = recovery_parent
            if outcome == "WIN":
                parent_outcome = {
                    "outcome": "WIN",
                    "entry_quote": None,
                    "expiry_quote": outcome_data.get("expiry_quote"),
                    "price_delta": None,
                    "is_verified": True,
                    "reason": f"Recovered by martingale (recovery_signal={sig_id})",
                    "evaluated_at": now_ts
                }
                # Resolve parent as recovered WIN
                await self.db.resolve_signal(parent_id, parent_outcome)

                # Compose a single notification summarizing recovery
                stats = await self.db.get_cumulative_stats()
                wins_count = stats.get("wins", 0)
                losses_count = stats.get("losses", 0)
                win_rate = stats.get("win_rate", 0.0)

                outcome_payload = {
                    "signal_id": parent_id,
                    "symbol": symbol,
                    "direction": direction,
                    "outcome": "RECOVERED",
                    "recovery_signal": sig_id,
                    "entry_quote": entry_quote,
                    "expiry_quote": outcome_data.get("expiry_quote"),
                    "price_delta": delta,
                    "strategy_name": self._get_field(active_sig, "strategy_name", default="Black Tornado"),
                    "intended_entry_time": entry_ts,
                    "intended_expiry_time": expiry_ts,
                    "wins_count": wins_count,
                    "losses_count": losses_count,
                    "win_rate_percent": win_rate,
                    "note": "Recovered by single-step martingale"
                }
                await telegram_notifier.broadcast_outcome(outcome_payload)
                return True
            else:
                # Recovery failed — mark both recovery and parent as LOSS
                parent_outcome = {
                    "outcome": "LOSS",
                    "entry_quote": None,
                    "expiry_quote": outcome_data.get("expiry_quote"),
                    "price_delta": None,
                    "is_verified": True,
                    "reason": f"Recovery attempt failed (recovery_signal={sig_id})",
                    "evaluated_at": now_ts
                }
                await self.db.resolve_signal(parent_id, parent_outcome)

                stats = await self.db.get_cumulative_stats()
                wins_count = stats.get("wins", 0)
                losses_count = stats.get("losses", 0)
                win_rate = stats.get("win_rate", 0.0)

                outcome_payload = {
                    "signal_id": parent_id,
                    "symbol": symbol,
                    "direction": direction,
                    "outcome": "FINAL_LOSS",
                    "recovery_signal": sig_id,
                    "entry_quote": entry_quote,
                    "expiry_quote": outcome_data.get("expiry_quote"),
                    "price_delta": delta,
                    "strategy_name": self._get_field(active_sig, "strategy_name", default="Black Tornado"),
                    "intended_entry_time": entry_ts,
                    "intended_expiry_time": expiry_ts,
                    "wins_count": wins_count,
                    "losses_count": losses_count,
                    "win_rate_percent": win_rate,
                    "note": "Recovery attempt failed — final loss recorded"
                }
                await telegram_notifier.broadcast_outcome(outcome_payload)
                return True

        # If this is NOT a recovery signal and result is LOSS, consider marking pending recovery
        if outcome == "LOSS" and settings.ENABLE_MARTINGALE:
            try:
                # Mark original signal as pending recovery instead of resolving immediately
                await self.db.mark_signal_pending_recovery(sig_id, details_update={"recovery_expected": True})
                logger.info(f"Signal #{sig_id} LOSS -> marked PENDING_RECOVERY for possible martingale recovery.")
                # Do not create OutcomeRecord yet; wait for recovery attempt
                return True
            except Exception as e:
                logger.error(f"Failed to mark signal {sig_id} pending recovery: {e}")
                # Fall through and record the LOSS if marking pending failed

        # Normal flow: record outcome for this signal (existing behavior)
        await self.db.resolve_signal(sig_id, outcome_data)

        # Fetch cumulative win/loss counts for Telegram notification
        stats = await self.db.get_cumulative_stats()
        wins_count = stats.get("wins", 0)
        losses_count = stats.get("losses", 0)
        win_rate = stats.get("win_rate", 0.0)

        # Dispatch Telegram notification in Black Tornado format
        outcome_payload = {
            "signal_id": sig_id,
            "symbol": symbol,
            "direction": direction,
            "outcome": outcome,
            "entry_quote": entry_quote,
            "expiry_quote": expiry_quote,
            "price_delta": delta,
            "strategy_name": self._get_field(active_sig, "strategy_name", default="Black Tornado"),
            "intended_entry_time": entry_ts,
            "intended_expiry_time": expiry_ts,
            "wins_count": wins_count,
            "losses_count": losses_count,
            "win_rate_percent": win_rate,
        }
        await telegram_notifier.broadcast_outcome(outcome_payload)
        return True

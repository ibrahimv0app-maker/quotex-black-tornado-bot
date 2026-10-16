"""Settlement engine tracking 1-minute expiry prices and calculating honest outcomes."""
import time
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.feed.candle_store import candle_store
from app.database.repository import DatabaseRepository
from app.notifications.telegram import telegram_notifier

logger = logging.getLogger(__name__)


class OutcomeTracker:
    def __init__(self, db_repo: DatabaseRepository):
        self.db = db_repo

    async def settle_signal(self, active_sig: Dict[str, Any]) -> bool:
        """
        Evaluate candle prices for entry and expiry, record result, and broadcast.
        """
        sig_id = active_sig["signal_id"]
        symbol = active_sig["symbol"]
        direction = active_sig["direction"]
        entry_ts = active_sig["intended_entry_time"]
        expiry_ts = active_sig["intended_expiry_time"]

        now_ts = int(time.time())
        # Check if enough time has passed (expiry time + small buffer for feed to settle)
        if now_ts < (expiry_ts + 2):
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
            entry_quote = entry_candle["open"]
        else:
            entry_quote = active_sig.get("signal_price")

        if entry_candle:
            # Expiry quote is the close of the 1-minute trade candle (which completed at expiry_ts)
            expiry_quote = entry_candle["close"]
        elif expiry_candle:
            expiry_quote = expiry_candle["open"]

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

        # Save to database (releases global lock)
        await self.db.resolve_signal(
            signal_id=sig_id,
            outcome=outcome,
            entry_quote=entry_quote,
            expiry_quote=expiry_quote,
            price_delta=delta,
            is_verified=verified,
            reason=reason
        )

        # Fetch cumulative win/loss counts for Telegram notification
        stats = await self.db.get_stats()
        wins_count = stats.get("wins", 0)
        losses_count = stats.get("losses", 0)
        win_rate = stats.get("win_rate_percent", 0.0)

        # Dispatch Telegram notification in Black Tornado format
        outcome_payload = {
            "signal_id": sig_id,
            "symbol": symbol,
            "direction": direction,
            "outcome": outcome,
            "entry_quote": entry_quote,
            "expiry_quote": expiry_quote,
            "price_delta": delta,
            "strategy_name": active_sig.get("strategy_name", "Black Tornado"),
            "intended_entry_time": entry_ts,
            "intended_expiry_time": expiry_ts,
            "wins_count": wins_count,
            "losses_count": losses_count,
            "win_rate_percent": win_rate
        }
        await telegram_notifier.broadcast_outcome(outcome_payload)
        return True

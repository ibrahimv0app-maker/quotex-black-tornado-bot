@@
         if outcome == "LOSS" and settings.ENABLE_MARTINGALE:
             try:
                 # Mark original signal as pending recovery instead of resolving immediately
-                await self.db.mark_signal_pending_recovery(sig_id, details_update={"recovery_expected": True})
-                logger.info(f"Signal #{sig_id} LOSS -> marked PENDING_RECOVERY for possible martingale recovery.")
-                # Do not create OutcomeRecord yet; wait for recovery attempt
-                return True
+                await self.db.mark_signal_pending_recovery(sig_id, details_update={"recovery_expected": True})
+                logger.info(f"Signal #{sig_id} LOSS -> marked PENDING_RECOVERY for possible martingale recovery.")
+                # Send immediate Telegram notice indicating LOSS and that martingale recovery will be attempted
+                stats = await self.db.get_cumulative_stats()
+                wins_count = stats.get("wins", 0)
+                losses_count = stats.get("losses", 0)
+                win_rate = stats.get("win_rate", 0.0)
+
+                outcome_payload = {
+                    "signal_id": sig_id,
+                    "symbol": symbol,
+                    "direction": direction,
+                    "outcome": "LOSS",
+                    "entry_quote": entry_quote,
+                    "expiry_quote": expiry_quote,
+                    "price_delta": delta,
+                    "strategy_name": self._get_field(active_sig, "strategy_name", default="Black Tornado"),
+                    "intended_entry_time": entry_ts,
+                    "intended_expiry_time": expiry_ts,
+                    "wins_count": wins_count,
+                    "losses_count": losses_count,
+                    "win_rate_percent": win_rate,
+                    "pending_recovery": True,
+                    "note": "Initial LOSS — martingale recovery will be attempted"
+                }
+                await telegram_notifier.broadcast_outcome(outcome_payload)
+                # Do not create OutcomeRecord yet; wait for recovery attempt
+                return True
             except Exception as e:
                 logger.error(f"Failed to mark signal {sig_id} pending recovery: {e}")
                 # Fall through and record the LOSS if marking pending failed
***

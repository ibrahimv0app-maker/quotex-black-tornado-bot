@@
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
-        await telegram_notifier.broadcast_signal(payload)
+        # attach per-pair statistics for enriched message
+        try:
+            pair_stats = await self.db.get_pair_stats(sig.symbol)
+            payload["pair_stats"] = pair_stats
+        except Exception:
+            payload["pair_stats"] = None
+
+        await telegram_notifier.broadcast_signal(payload)
         self.diagnostic_stats["signals_dispatched"] += 1

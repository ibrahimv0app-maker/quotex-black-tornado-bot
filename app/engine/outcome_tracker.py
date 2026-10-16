@@
         # Dispatch Telegram notification in Black Tornado format
         outcome_payload = {
@@
         await telegram_notifier.broadcast_outcome(outcome_payload)
+        # After broadcasting single outcome, send a summary every 10 resolved outcomes
+        try:
+            stats = await self.db.get_cumulative_stats()
+            total = stats.get("total_signals", 0)
+            if total > 0 and total % 10 == 0:
+                recent = await self.db.get_recent_outcomes_dict(limit=10)
+                if recent:
+                    await telegram_notifier.broadcast_summary(recent)
+        except Exception as e:
+            logger.error(f"Failed to send periodic summary: {e}")
         return True

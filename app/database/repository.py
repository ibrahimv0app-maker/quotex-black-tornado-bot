@@
     async def get_recent_outcomes(self, limit: int = 50) -> List[OutcomeRecord]:
@@
             return []
 
     async def get_consecutive_losses(self, symbol: str, max_lookback: int = 5) -> int:
@@
             return 0
+
+    async def get_last_outcome_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
+        """
+        Return the most recent resolved outcome for a given symbol joined with its signal details.
+        Returns a dict with keys: outcome, signal_id, direction, intended_entry_time, intended_expiry_time, evaluated_at
+        or None if not found.
+        """
+        try:
+            async with self.session_factory() as session:
+                stmt = (
+                    select(OutcomeRecord, SignalRecord)
+                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
+                    .where(SignalRecord.symbol == symbol)
+                    .order_by(desc(OutcomeRecord.id))
+                    .limit(1)
+                )
+                res = await session.execute(stmt)
+                row = res.first()
+                if not row:
+                    return None
+                outcome_row, sig_row = row[0], row[1]
+                return {
+                    "outcome": outcome_row.outcome,
+                    "signal_id": outcome_row.signal_id,
+                    "direction": sig_row.direction,
+                    "intended_entry_time": sig_row.intended_entry_time,
+                    "intended_expiry_time": sig_row.intended_expiry_time,
+                    "evaluated_at": outcome_row.evaluated_at
+                }
+        except Exception as e:
+            logger.error(f"Error fetching last outcome for {symbol}: {e}")
+            return None

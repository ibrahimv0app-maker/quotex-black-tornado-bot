@@
     async def get_recent_outcomes(self, limit: int = 50) -> List[OutcomeRecord]:
@@
         except Exception as e:
             logger.error(f"Error getting recent outcomes: {e}")
             return []
+
+    async def get_consecutive_losses(self, symbol: str, max_lookback: int = 5) -> int:
+        """
+        Count consecutive LOSS outcomes for the given symbol by looking back up to max_lookback outcomes.
+        Returns count of consecutive losses (0 if last outcome is not a loss or no outcomes found).
+        """
+        try:
+            async with self.session_factory() as session:
+                # Join OutcomeRecord -> SignalRecord to filter by symbol
+                stmt = (
+                    select(OutcomeRecord, SignalRecord)
+                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
+                    .where(SignalRecord.symbol == symbol)
+                    .order_by(desc(OutcomeRecord.id))
+                    .limit(max_lookback)
+                )
+                res = await session.execute(stmt)
+                rows = res.all()
+                count = 0
+                for row in rows:
+                    outcome_row = row[0]
+                    if outcome_row.outcome == 'LOSS':
+                        count += 1
+                    else:
+                        break
+                return count
+        except Exception as e:
+            logger.error(f"Error getting consecutive losses for {symbol}: {e}")
+            return 0

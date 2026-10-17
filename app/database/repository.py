@@
     async def get_recent_outcomes_dict(self, limit: int = 10) -> List[Dict[str, Any]]:
@@
         except Exception as e:
             logger.error(f"Error getting recent outcomes dict: {e}")
             return []
+
+    async def get_last_outcome_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
+        """
+        Return the most recent outcome for a symbol joined with its signal metadata.
+        """
+        try:
+            async with self.session_factory() as session:
+                stmt = (
+                    select(OutcomeRecord, SignalRecord)
+                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
+                    .where(SignalRecord.symbol == symbol)
+                    .order_by(desc(OutcomeRecord.evaluated_at))
+                    .limit(1)
+                )
+                res = await session.execute(stmt)
+                row = res.first()
+                if not row:
+                    return None
+                outcome_row, sig_row = row[0], row[1]
+                return {
+                    "signal_id": outcome_row.signal_id,
+                    "outcome": outcome_row.outcome,
+                    "evaluated_at": outcome_row.evaluated_at,
+                    "intended_expiry_time": sig_row.intended_expiry_time,
+                    "direction": sig_row.direction,
+                }
+        except Exception as e:
+            logger.error(f"Error getting last outcome for {symbol}: {e}")
+            return None
+
+    async def mark_signal_pending_recovery(self, signal_id: str, details_update: Dict[str, Any] = None) -> bool:
+        """
+        Mark an active signal as PENDING_RECOVERY and merge optional details into details_json.
+        Returns True if updated.
+        """
+        try:
+            async with self.session_factory() as session:
+                sig = await session.get(SignalRecord, signal_id)
+                if not sig:
+                    return False
+                try:
+                    details = json.loads(sig.details_json or "{}")
+                except Exception:
+                    details = {}
+                if details_update:
+                    details.update(details_update)
+                sig.details_json = json.dumps(details)
+                sig.status = "PENDING_RECOVERY"
+                await session.commit()
+                await session.refresh(sig)
+                logger.info(f"Signal {signal_id} marked PENDING_RECOVERY")
+                return True
+        except Exception as e:
+            logger.error(f"Error marking {signal_id} pending recovery: {e}")
+            return False

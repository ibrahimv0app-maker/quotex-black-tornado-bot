@@
     async def resolve_signal(self, signal_id: str, outcome_data: Dict[str, Any]) -> Optional[OutcomeRecord]:
@@
                 logger.info(f"Signal #{signal_id} marked RESOLVED with outcome {outcome.outcome}")
                 return outcome
         except Exception as e:
             logger.error(f"Error resolving signal #{signal_id}: {e}")
             return None
+
+    async def mark_signal_pending_recovery(self, signal_id: str, details_update: Optional[Dict[str, Any]] = None) -> bool:
+        """
+        Mark an existing signal as pending recovery so it no longer blocks new ACTIVE signals.
+        Optionally merge details_update into the existing details_json.
+        """
+        try:
+            async with self.session_factory() as session:
+                sig = await session.get(SignalRecord, signal_id)
+                if not sig:
+                    return False
+                # Merge details JSON
+                existing = {}
+                try:
+                    existing = json.loads(sig.details_json) if sig.details_json else {}
+                except Exception:
+                    existing = {}
+                if details_update:
+                    existing.update(details_update)
+                sig.details_json = json.dumps(existing)
+                sig.status = "PENDING_RECOVERY"
+                await session.commit()
+                logger.info(f"Signal #{signal_id} marked PENDING_RECOVERY")
+                return True
+        except Exception as e:
+            logger.error(f"Error marking signal #{signal_id} pending recovery: {e}")
+            return False
+
+    async def get_signal(self, signal_id: str) -> Optional[SignalRecord]:
+        """Fetch signal record by id."""
+        try:
+            async with self.session_factory() as session:
+                sig = await session.get(SignalRecord, signal_id)
+                return sig
+        except Exception as e:
+            logger.error(f"Error fetching signal {signal_id}: {e}")
+            return None

@@
     async def get_cumulative_stats(self) -> Dict[str, Any]:
@@
                 return {
                     "wins": wins,
                     "losses": losses,
                     "draws": draws,
                     "unverified": unverified,
                     "total_signals": wins + losses + draws + unverified,
                     "win_rate": winrate
                 }
         except Exception as e:
             logger.error(f"Error getting stats: {e}")
             return {"wins": 0, "losses": 0, "draws": 0, "unverified": 0, "total_signals": 0, "win_rate": 0.0}
+
+    async def get_pair_stats(self, symbol: str) -> Dict[str, Any]:
+        """
+        Return per-symbol statistics: wins, losses, max_consecutive_wins, max_consecutive_losses.
+        """
+        try:
+            async with self.session_factory() as session:
+                stmt = (
+                    select(OutcomeRecord, SignalRecord)
+                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
+                    .where(SignalRecord.symbol == symbol)
+                    .order_by(OutcomeRecord.evaluated_at.asc())
+                )
+                res = await session.execute(stmt)
+                rows = res.all()
+                wins = 0
+                losses = 0
+                max_consec_wins = 0
+                max_consec_losses = 0
+                cur_w = 0
+                cur_l = 0
+                for row in rows:
+                    outcome_row = row[0]
+                    o = outcome_row.outcome
+                    if o == 'WIN':
+                        wins += 1
+                        cur_w += 1
+                        cur_l = 0
+                    elif o == 'LOSS':
+                        losses += 1
+                        cur_l += 1
+                        cur_w = 0
+                    else:
+                        cur_w = 0
+                        cur_l = 0
+                    if cur_w > max_consec_wins:
+                        max_consec_wins = cur_w
+                    if cur_l > max_consec_losses:
+                        max_consec_losses = cur_l
+                return {
+                    "symbol": symbol,
+                    "wins": wins,
+                    "losses": losses,
+                    "max_consecutive_wins": max_consec_wins,
+                    "max_consecutive_losses": max_consec_losses,
+                }
+        except Exception as e:
+            logger.error(f"Error getting pair stats for {symbol}: {e}")
+            return {"symbol": symbol, "wins": 0, "losses": 0, "max_consecutive_wins": 0, "max_consecutive_losses": 0}
+
+    async def get_recent_outcomes_dict(self, limit: int = 10) -> List[Dict[str, Any]]:
+        """
+        Return recent outcomes as list of dicts including signal metadata.
+        """
+        try:
+            async with self.session_factory() as session:
+                stmt = (
+                    select(OutcomeRecord, SignalRecord)
+                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
+                    .order_by(desc(OutcomeRecord.evaluated_at))
+                    .limit(limit)
+                )
+                res = await session.execute(stmt)
+                rows = res.all()
+                out = []
+                for row in rows:
+                    outcome_row, sig_row = row[0], row[1]
+                    out.append({
+                        "signal_id": outcome_row.signal_id,
+                        "symbol": sig_row.symbol,
+                        "direction": sig_row.direction,
+                        "outcome": outcome_row.outcome,
+                        "reason": outcome_row.reason,
+                        "evaluated_at": outcome_row.evaluated_at.isoformat() if outcome_row.evaluated_at else None
+                    })
+                return out
+        except Exception as e:
+            logger.error(f"Error getting recent outcomes dict: {e}")
+            return []

@@
-        # Apply martingale one-step doubling if allowed and recent outcome was a loss
-        indicators = sig.indicators or {}
-        diagnostics = indicators.get("otc_diagnostics", {})
-        pos_size = indicators.get("pos_size")
-        # Fallback compute if not provided
-        if not pos_size:
-            balance = float(eval_context.get("balance") if isinstance(eval_context.get("balance"), (int,float,str)) else eval_context.get("account_balance", 100.0))
-            atr_val = diagnostics.get("atr") or atr_from_candles(winner["closed_candles"], period=settings.OTC_ATR_PERIOD) or 0.0
-            pos_size = adaptive_position_size(balance, settings.RISK_PER_TRADE, atr_val, atr_multiplier=settings.OTC_ATR_SIZE_MULT, price=winner["last_price"])
-
-        martingale_applied = False
-        try:
-            if settings.ENABLE_MARTINGALE:
-                consecutive_losses = await self.db.get_consecutive_losses(sig.symbol, max_lookback=settings.MARTINGALE_MAX_STEPS + 1)
-                if consecutive_losses >= 1 and consecutive_losses <= settings.MARTINGALE_MAX_STEPS:
-                    # Double position size once
-                    pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
-                    martingale_applied = True
-        except Exception:
-            martingale_applied = False
-
-        details = {
-            "confirmations": sig.confirmations,
-            "indicators": {**(sig.indicators or {}), "pos_size": pos_size},
-            "natr_bps": winner.get("natr_bps"),
-            "reason": sig.reason,
-            "bt_direction": t_out.bt_direction,
-            "bt_confidence": t_out.bt_confidence,
-            "bt_regime": t_out.bt_regime,
-            "bt_turbulence": t_out.bt_turbulence,
-            "martingale_applied": martingale_applied
-        }
+        # Apply single-step martingale only if the immediate previous outcome for this symbol was a LOSS
+        # and the loss happened on the candle that just expired (i.e. intended_expiry_time == next_entry_slot)
+        indicators = sig.indicators or {}
+        diagnostics = indicators.get("otc_diagnostics", {})
+        pos_size = indicators.get("pos_size")
+        # Fallback compute if not provided
+        if not pos_size:
+            balance = float(eval_context.get("balance") if isinstance(eval_context.get("balance"), (int,float,str)) else eval_context.get("account_balance", 100.0))
+            atr_val = diagnostics.get("atr") or atr_from_candles(winner["closed_candles"], period=settings.OTC_ATR_PERIOD) or 0.0
+            pos_size = adaptive_position_size(balance, settings.RISK_PER_TRADE, atr_val, atr_multiplier=settings.OTC_ATR_SIZE_MULT, price=winner["last_price"])
+
+        martingale_applied = False
+        try:
+            if settings.ENABLE_MARTINGALE:
+                last_outcome = await self.db.get_last_outcome_for_symbol(sig.symbol)
+                # Check that last outcome exists, was LOSS, occurred on the candle that just expired
+                if last_outcome and last_outcome.get("outcome") == "LOSS" and last_outcome.get("intended_expiry_time") == next_entry_slot:
+                    # Only apply martingale if the direction matches the previous losing signal
+                    if last_outcome.get("direction") == sig.direction:
+                        pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
+                        martingale_applied = True
+        except Exception:
+            martingale_applied = False
+
+        details = {
+            "confirmations": sig.confirmations,
+            "indicators": {**(sig.indicators or {}), "pos_size": pos_size},
+            "natr_bps": winner.get("natr_bps"),
+            "reason": sig.reason,
+            "bt_direction": t_out.bt_direction,
+            "bt_confidence": t_out.bt_confidence,
+            "bt_regime": t_out.bt_regime,
+            "bt_turbulence": t_out.bt_turbulence,
+            "martingale_applied": martingale_applied
+        }
***

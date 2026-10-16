@@
 from app.indicators.black_tornado import black_tornado, TornadoOutput
 from app.strategies.black_tornado import build_strategies
+from app.strategies.otc_utils import adaptive_position_size, atr_from_candles
@@
         # 5. Acquire atomic database lock
-        lock_acquired = await self.db.acquire_signal_lock_and_create(
-            signal_id=signal_id,
-            symbol=sig.symbol,
-            direction=sig.direction,
-            strategy_name=sig.strategy_name,
-            setup_score=score,
-            signal_sent_time=now_ts,
-            intended_entry_time=next_entry_slot,
-            intended_expiry_time=expiry_slot,
-            signal_price=winner["last_price"],
-            details={
-                "confirmations": sig.confirmations,
-                "indicators": sig.indicators,
-                "natr_bps": winner["natr_bps"],
-                "reason": sig.reason,
-                "bt_direction": t_out.bt_direction,
-                "bt_confidence": t_out.bt_confidence,
-                "bt_regime": t_out.bt_regime,
-                "bt_turbulence": t_out.bt_turbulence
-            }
-        )
+        # Apply martingale one-step doubling if allowed and recent outcome was a loss
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
+                consecutive_losses = await self.db.get_consecutive_losses(sig.symbol, max_lookback=settings.MARTINGALE_MAX_STEPS + 1)
+                if consecutive_losses >= 1 and consecutive_losses <= settings.MARTINGALE_MAX_STEPS:
+                    # Double position size once
+                    pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
+                    martingale_applied = True
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
+
+        lock_acquired = await self.db.acquire_signal_lock_and_create(
+            signal_id=signal_id,
+            symbol=sig.symbol,
+            direction=sig.direction,
+            strategy_name=sig.strategy_name,
+            setup_score=score,
+            signal_sent_time=now_ts,
+            intended_entry_time=next_entry_slot,
+            intended_expiry_time=expiry_slot,
+            signal_price=winner["last_price"],
+            details=details
+        )
***

@@
-            # compute pos_size if provided in indicators, else simple fixed sizing
-            indicators = getattr(sig, "indicators", {}) or {}
-            pos_size = indicators.get("pos_size") or settings.RISK_PER_TRADE
-
-            # determine martingale application: if a pending recovery exists for this symbol and conditions match
-            is_recovery = False
-            recovery_parent = None
-            if martingale_enabled and sym in pending_recovery:
-                parent = pending_recovery[sym]
-                # only apply recovery for same direction
-                if parent["direction"] == sig.direction:
-                    is_recovery = True
-                    recovery_parent = parent["signal_id"]
-                    # apply multiplier to pos_size
-                    pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
-                    # clear pending
-                    del pending_recovery[sym]
+            # compute pos_size if provided in indicators, else simple fixed sizing
+            indicators = getattr(sig, "indicators", {}) or {}
+            pos_size = indicators.get("pos_size") or settings.RISK_PER_TRADE
+
+            # determine martingale application: if a pending recovery exists for this symbol and conditions match
+            is_recovery = False
+            recovery_parent = None
+            if martingale_enabled and sym in pending_recovery:
+                parent = pending_recovery[sym]
+                # only apply recovery for same direction
+                if parent["direction"] == sig.direction:
+                    is_recovery = True
+                    recovery_parent = parent["signal_id"]
+                    # apply multiplier to pos_size
+                    pos_size = pos_size * settings.MARTINGALE_MULTIPLIER
+                    # clear pending
+                    del pending_recovery[sym]
+
+            # enforce cap fraction for backtest sizing and live execution: treat pos_size as fraction if <=1
+            try:
+                account_balance = settings.DEFAULT_ACCOUNT_BALANCE
+                # pos_size may be fractional (<=1) or absolute (>1). Normalize to fraction then cap.
+                if isinstance(pos_size, (int, float)):
+                    if pos_size > 1.0:
+                        pos_frac = pos_size / max(account_balance, 1.0)
+                    else:
+                        pos_frac = pos_size
+                    capped = min(pos_frac, settings.MARTINGALE_CAP_FRACTION)
+                    # convert back: keep fractional representation for simulation
+                    pos_size = capped
+            except Exception:
+                pass
***

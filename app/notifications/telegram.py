@@
     def format_outcome_message(self, outcome_data: Dict[str, Any]) -> str:
@@
-        text = (
-            "🌪️ <b>BLACK TORNADO RESULT</b>\n"
-            f"💱 <b>Pair:</b> <code>{sym}</code>\n"
-            f"{sig_icon} <b>Signal:</b> {dir_val}\n"
-            f"🏆 <b>Result:</b> {res_str}\n"
-            f"📈 <b>Entry:</b> {entry_str}\n"
-            f"📉 <b>Expiry:</b> {expiry_str}\n"
-            f"✅ <b>Wins:</b> {wins_count} | ❌ <b>Losses:</b> {losses_count}\n"
-            f"🎯 <b>Win Rate:</b> {int(round(win_rate))}%\n"
-            "⚠️ <b>Result:</b> Feed-estimated\n"
-            "━━━━━━━━━━━━"
-        )
+        text = (
+            "🌪️ <b>BLACK TORNADO RESULT</b>\n"
+            f"💱 <b>Pair:</b> <code>{sym}</code>\n"
+            f"{sig_icon} <b>Signal:</b> {dir_val}\n"
+            f"🏆 <b>Result:</b> {res_str}\n"
+            f"📈 <b>Entry:</b> {entry_str}\n"
+            f"📉 <b>Expiry:</b> {expiry_str}\n"
+            f"✅ <b>Wins:</b> {wins_count} | ❌ <b>Losses:</b> {losses_count}\n"
+            f"🎯 <b>Win Rate:</b> {int(round(win_rate))}%\n"
+        )
+
+        # Additional flags for martingale/pending recovery
+        if outcome_data.get("pending_recovery"):
+            text += "⏳ <b>Pending Recovery:</b> Martingale recovery will be attempted\n"
+
+        if outcome_data.get("recovery_signal"):
+            text += f"🔁 <b>Recovery Signal:</b> {outcome_data.get('recovery_signal')}\n"
+
+        if outcome_data.get("note"):
+            text += f"📝 <b>Note:</b> {outcome_data.get('note')}\n"
+
+        text += "⚠️ <b>Result:</b> Feed-estimated\n"
+        text += "━━━━━━━━━━━━"
         return text
***

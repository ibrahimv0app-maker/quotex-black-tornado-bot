@@
     def format_signal_message(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
@@
-        text = (
-            f"{placeholder_channel} قناة تداول كوتكس\n\n"
-            f"{placeholder_pair} الزوج: {sig.symbol}\n\n"
-            f"🎯(UTC 3+) نقطة الدخول: {entry_time_str} \n\n"
-            f"🔴 الأتجاه: {sig.direction} ⬇️\n"
-            f"📊 BT Score: {int(round(score))}/100\n"
-            f"✅ M5/M1 Bearish Aligned\n"
-            f"⚡️ Volatility: Optimal / Low Noise"
-        )
+        pair_stats = signal_data.get("pair_stats") or {}
+        wins = pair_stats.get("wins") if pair_stats else None
+        losses = pair_stats.get("losses") if pair_stats else None
+        max_cw = pair_stats.get("max_consecutive_wins") if pair_stats else None
+        max_cl = pair_stats.get("max_consecutive_losses") if pair_stats else None
+
+        pair_stats_lines = ""
+        if pair_stats:
+            pair_stats_lines = (
+                f"\nعدد مرات ربح الزوج: {wins} | عدد مرات خسارة الزوج: {losses}\n"
+                f"أقصى ربح متتالي: {max_cw} | أقصى خسارة متتالية: {max_cl}\n"
+            )
+
+        text = (
+            f"{placeholder_channel} قناة تداول كوتكس\n\n"
+            f"{placeholder_pair} الزوج: {sig.symbol}\n"
+            f"{pair_stats_lines}\n"
+            f"🎯(UTC 3+) نقطة الدخول: {entry_time_str} \n\n"
+            f"🔴 الأتجاه: {sig.direction} ⬇️\n"
+            f"📊 BT Score: {int(round(score))}/100\n"
+            f"✅ M5/M1 Bearish Aligned\n"
+            f"⚡️ Volatility: Optimal / Low Noise"
+        )
@@
     async def broadcast_outcome(self, outcome_data: Dict[str, Any]) -> bool:
         text = self.format_outcome_message(outcome_data)
@@
         try:
             async with aiohttp.ClientSession() as session:
                 async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                     if resp.status == 200:
                         return True
                     err = await resp.text()
                     logger.error(f"Telegram dispatch failed (outcome): HTTP {resp.status} - {err}")
                     return False
         except Exception as e:
             logger.error(f"Exception during Telegram broadcast (outcome): {e}")
             return False
+
+    def format_summary_message(self, outcomes: List[Dict[str, Any]]) -> str:
+        """
+        Format a summary message listing recent outcomes.
+        """
+        lines = ["📊 ملخص آخر 10 صفقات:"]
+        for o in outcomes:
+            sym = o.get("symbol")
+            dirv = o.get("direction")
+            res = o.get("outcome")
+            time = o.get("evaluated_at")
+            if res == "WIN":
+                icon = "✅"
+            elif res == "LOSS":
+                icon = "❌"
+            elif res == "RECOVERED":
+                icon = "🔄✅"
+            elif res == "FINAL_LOSS":
+                icon = "🔄❌"
+            else:
+                icon = "⚠️"
+            lines.append(f"{icon} {sym} {dirv} — {res} ({time})")
+        return "\n".join(lines)
+
+    async def broadcast_summary(self, outcomes: List[Dict[str, Any]]) -> bool:
+        text = self.format_summary_message(outcomes)
+        return await self.send_message(text)

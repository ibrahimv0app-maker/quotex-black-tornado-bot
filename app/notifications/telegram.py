"""Telegram bot notification dispatcher with exact Black Tornado v1.0 layout."""
import aiohttp
import pytz
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        tz_name: str = settings.DISPLAY_TIMEZONE
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.tz = pytz.timezone(tz_name)

    def _format_time(self, ts: int) -> str:
        dt = datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(self.tz)
        return dt.strftime("%H:%M:%S PKT")

    def format_signal_message(self, signal_data: Dict[str, Any]) -> str:
        """
        User-specified format:
        🌪️ BLACK TORNADO
        💱 Pair: EURUSD-OTC
        🟢 Signal: CALL ⬆️
        ⏱️ Expiry: 1 Minute
        🎯 Entry: 12:13:00 PKT
        📊 BT Score: 82/100
        ✅ Trend Confirmed
        ⚡ Volatility: Stable
        ━━━━━━━━━━━━
        """
        sig = signal_data["signal"]
        score = signal_data.get("composite_score", sig.score)
        entry_time_str = self._format_time(signal_data["intended_entry_time"])

        is_call = sig.direction == "CALL"
        sig_icon = "🟢" if is_call else "🔴"
        dir_arrow = "⬆️" if is_call else "⬇️"
        
        # Volatility assessment
        vol_label = signal_data.get("volatility_label", "Stable")
        trend_status = signal_data.get("trend_status", "Trend Confirmed")

        text = (
            "🌪️ <b>BLACK TORNADO</b>\n"
            f"💱 <b>Pair:</b> <code>{sig.symbol}</code>\n"
            f"{sig_icon} <b>Signal:</b> <b>{sig.direction}</b> {dir_arrow}\n"
            "⏱️ <b>Expiry:</b> 1 Minute\n"
            f"🎯 <b>Entry:</b> {entry_time_str}\n"
            f"📊 <b>BT Score:</b> {int(round(score))}/100\n"
            f"✅ <b>{trend_status}</b>\n"
            f"⚡ <b>Volatility:</b> {vol_label}\n"
            "━━━━━━━━━━━━"
        )
        return text

    def format_outcome_message(self, outcome_data: Dict[str, Any]) -> str:
        """
        User-specified format:
        🌪️ BLACK TORNADO RESULT
        💱 Pair: EURUSD-OTC
        🟢 Signal: CALL
        🏆 Result: ✅ WIN
        📈 Entry: 1.12345
        📉 Expiry: 1.12358
        ✅ Wins: 18 | ❌ Losses: 7
        🎯 Win Rate: 72%
        ⚠️ Result: Feed-estimated
        ━━━━━━━━━━━━
        """
        sym = outcome_data["symbol"]
        dir_val = outcome_data["direction"]
        outcome = outcome_data["outcome"]
        entry_quote = outcome_data.get("entry_quote")
        expiry_quote = outcome_data.get("expiry_quote")

        wins_count = outcome_data.get("wins_count", 0)
        losses_count = outcome_data.get("losses_count", 0)
        win_rate = outcome_data.get("win_rate_percent", 0.0)

        is_call = dir_val == "CALL"
        sig_icon = "🟢" if is_call else "🔴"

        if outcome == "WIN":
            res_str = "✅ WIN"
        elif outcome == "LOSS":
            res_str = "❌ LOSS"
        elif outcome == "DRAW":
            res_str = "⚖️ DRAW"
        else:
            res_str = "⚠️ UNVERIFIED"

        entry_str = f"{entry_quote:.5f}" if entry_quote is not None else "N/A"
        expiry_str = f"{expiry_quote:.5f}" if expiry_quote is not None else "N/A"

        text = (
            "🌪️ <b>BLACK TORNADO RESULT</b>\n"
            f"💱 <b>Pair:</b> <code>{sym}</code>\n"
            f"{sig_icon} <b>Signal:</b> {dir_val}\n"
            f"🏆 <b>Result:</b> {res_str}\n"
            f"📈 <b>Entry:</b> {entry_str}\n"
            f"📉 <b>Expiry:</b> {expiry_str}\n"
            f"✅ <b>Wins:</b> {wins_count} | ❌ <b>Losses:</b> {losses_count}\n"
            f"🎯 <b>Win Rate:</b> {int(round(win_rate))}%\n"
            "⚠️ <b>Result:</b> Feed-estimated\n"
            "━━━━━━━━━━━━"
        )
        return text

    async def send_message(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.info(f"[DRY-RUN / NO BOT CREDENTIALS] Telegram message:\n{text}")
            return True

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return True
                    err = await resp.text()
                    logger.error(f"Telegram dispatch failed: HTTP {resp.status} - {err}")
                    return False
        except Exception as e:
            logger.error(f"Exception during Telegram broadcast: {e}")
            return False

    async def broadcast_signal(self, signal_data: Dict[str, Any]) -> bool:
        text = self.format_signal_message(signal_data)
        return await self.send_message(text)

    async def broadcast_outcome(self, outcome_data: Dict[str, Any]) -> bool:
        text = self.format_outcome_message(outcome_data)
        return await self.send_message(text)


telegram_notifier = TelegramNotifier()

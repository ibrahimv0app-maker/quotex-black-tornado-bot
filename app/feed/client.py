"""Asynchronous REST client for quotexfeed API."""
import time
import logging
from typing import Dict, List, Any, Optional
import aiohttp
from app.config import settings

logger = logging.getLogger(__name__)


class QuotexFeedClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "QuotexSignalBot/1.0 (Production 24/7)"}
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_candles(
        self, symbol: str, interval: str = "1m", limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical candles from GET /api/public/candles
        """
        session = await self.get_session()
        url = f"{self.base_url}/api/public/candles"
        params = {"symbol": symbol, "interval": interval, "limit": min(limit, 2001)}

        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candles = data.get("candles", [])
                    return candles
                else:
                    text = await resp.text()
                    logger.warning(f"REST candle error {symbol}: HTTP {resp.status} - {text[:100]}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}")
            return []

    async def test_symbol_health(self, symbol: str) -> Dict[str, Any]:
        """Test symbol availability and measure REST latency."""
        t0 = time.perf_counter()
        candles = await self.fetch_candles(symbol, interval="1m", limit=5)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "symbol": symbol,
            "status": "OK" if len(candles) > 0 else "NO_DATA",
            "latency_ms": latency_ms,
            "candle_count": len(candles),
            "latest_candle": candles[-1] if candles else None
        }


feed_client = QuotexFeedClient()

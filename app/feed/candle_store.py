"""In-memory rolling candle store and tick-to-candle aggregator."""
import time
import logging
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)


class Candle:
    __slots__ = ("time", "open", "high", "low", "close", "volume")

    def __init__(self, time: int, open: float, high: float, low: float, close: float, volume: float = 1.0):
        self.time = int(time)
        self.open = float(open)
        self.high = float(high)
        self.low = float(low)
        self.close = float(close)
        self.volume = float(volume)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CandleStore:
    def __init__(self, max_history: int = 500):
        self.max_history = max_history
        # symbol -> deque of closed Candle
        self._closed: Dict[str, deque[Candle]] = {}
        # symbol -> forming open Candle
        self._forming: Dict[str, Candle] = {}
        # symbol -> (last_price, last_tick_time)
        self._last_ticks: Dict[str, tuple[float, int]] = {}

    def load_initial_candles(self, symbol: str, raw_candles: List[Dict[str, Any]]) -> int:
        """Seed closed candle history from REST API response."""
        if symbol not in self._closed:
            self._closed[symbol] = deque(maxlen=self.max_history)

        current_time = int(time.time())
        current_minute_bucket = (current_time // 60) * 60

        loaded = 0
        for rc in raw_candles:
            c_time = int(rc["time"])
            candle = Candle(
                time=c_time,
                open=rc["open"],
                high=rc["high"],
                low=rc["low"],
                close=rc["close"],
                volume=rc.get("volume", 1.0)
            )
            # If candle is strictly in the past, store as closed
            if c_time < current_minute_bucket:
                self._closed[symbol].append(candle)
                loaded += 1
            else:
                self._forming[symbol] = candle

        if self._closed[symbol]:
            last_c = self._closed[symbol][-1]
            self._last_ticks[symbol] = (last_c.close, last_c.time + 59)

        return loaded

    def process_tick(self, symbol: str, price: float, tick_time: int) -> Optional[Candle]:
        """
        Aggregate a live tick into 1-minute candle.
        Returns a newly closed Candle if a minute boundary was crossed.
        """
        self._last_ticks[symbol] = (price, tick_time)
        bucket = (tick_time // 60) * 60

        if symbol not in self._closed:
            self._closed[symbol] = deque(maxlen=self.max_history)

        forming = self._forming.get(symbol)
        closed_candle: Optional[Candle] = None

        if forming is None:
            # First tick starting a new candle
            self._forming[symbol] = Candle(bucket, price, price, price, price, 1.0)
        elif bucket == forming.time:
            # Tick within current minute
            if price > forming.high:
                forming.high = price
            if price < forming.low:
                forming.low = price
            forming.close = price
            forming.volume += 1.0
        elif bucket > forming.time:
            # Minute completed! Close previous candle and push to history
            closed_candle = forming
            self._closed[symbol].append(closed_candle)
            # Start new forming candle
            self._forming[symbol] = Candle(bucket, price, price, price, price, 1.0)

        return closed_candle

    def get_closed_candles(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get strictly completed candles in chronological order."""
        hist = self._closed.get(symbol)
        if not hist:
            return []
        items = list(hist)
        if len(items) > limit:
            items = items[-limit:]
        return [c.to_dict() for c in items]

    def get_forming_candle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the ongoing, not yet closed candle for current minute."""
        forming = self._forming.get(symbol)
        return forming.to_dict() if forming else None

    def get_last_quote(self, symbol: str) -> Optional[tuple[float, int]]:
        """Returns (last_price, last_timestamp)."""
        return self._last_ticks.get(symbol)

    def is_stale(self, symbol: str, current_time: int, max_gap: float = 5.0) -> bool:
        """Check if symbol received no updates in the last max_gap seconds."""
        quote = self._last_ticks.get(symbol)
        if not quote:
            return True
        _, last_ts = quote
        return (current_time - last_ts) > max_gap


candle_store = CandleStore()

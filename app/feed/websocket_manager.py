"""Real-time multi-connection stream manager (SSE / WebSocket)."""
import json
import time
import asyncio
import random
import logging
from typing import List, Dict, Optional, Callable
import aiohttp
from app.config import settings
from app.feed.symbol_registry import symbol_registry
from app.feed.candle_store import candle_store

logger = logging.getLogger(__name__)


class StreamWorker:
    """Manages an individual stream connection for a subset of up to 10 symbols."""
    def __init__(self, worker_id: int, symbols: List[str], base_url: str):
        self.worker_id = worker_id
        self.symbols = symbols
        self.base_url = base_url
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_event_time = 0.0

    async def start(self):
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        sym_param = ",".join(self.symbols)
        stream_url = f"{self.base_url}/api/public/stream?symbols={sym_param}"
        backoff = 1.0

        while self.is_running:
            try:
                logger.info(f"[Worker {self.worker_id}] Connecting stream for {len(self.symbols)} pairs: {sym_param[:40]}...")
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(stream_url) as resp:
                        if resp.status != 200:
                            logger.warning(f"[Worker {self.worker_id}] Stream HTTP {resp.status}. Reconnecting...")
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2.0, 30.0)
                            continue

                        backoff = 1.0  # reset backoff upon success
                        logger.info(f"[Worker {self.worker_id}] Stream active.")

                        async for line in resp.content:
                            if not self.is_running:
                                break
                            if not line:
                                continue
                            decoded = line.decode("utf-8").strip()
                            if not decoded.startswith("data:"):
                                continue

                            payload_str = decoded[5:].strip()
                            if not payload_str:
                                continue

                            try:
                                data = json.loads(payload_str)
                                self._handle_tick(data)
                            except json.JSONDecodeError:
                                pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[Worker {self.worker_id}] Stream error: {e}. Retrying in {backoff:.1f}s...")
                jitter = random.uniform(0.1, 0.5)
                await asyncio.sleep(backoff + jitter)
                backoff = min(backoff * 1.5, 30.0)

    def _handle_tick(self, data: Dict):
        raw_symbol = data.get("symbol")
        price = data.get("price")
        timestamp = data.get("timestamp")

        if not raw_symbol or price is None or timestamp is None:
            return

        canonical = symbol_registry.normalize(raw_symbol)
        if not canonical:
            return

        self.last_event_time = time.time()
        # Feed tick to candle aggregator
        candle_store.process_tick(canonical, float(price), int(timestamp))


class StreamManager:
    """Manages pool of stream workers to cover all active symbols."""
    def __init__(self, symbols: Optional[List[str]] = None, batch_size: int = 8):
        self.symbols = symbols or list(symbol_registry.get_all_canonical())
        self.batch_size = min(batch_size, 10)  # max 10 per connection as per docs
        self.workers: List[StreamWorker] = []

    async def start(self):
        # Partition symbols into batches
        batches = [
            self.symbols[i : i + self.batch_size]
            for i in range(0, len(self.symbols), self.batch_size)
        ]
        logger.info(f"Starting {len(batches)} stream workers for {len(self.symbols)} total symbols.")
        for idx, batch in enumerate(batches):
            worker = StreamWorker(
                worker_id=idx + 1,
                symbols=batch,
                base_url=settings.API_BASE_URL
            )
            self.workers.append(worker)
            await worker.start()

    async def stop(self):
        logger.info("Stopping all stream workers.")
        for w in self.workers:
            await w.stop()
        self.workers.clear()


stream_manager = StreamManager()

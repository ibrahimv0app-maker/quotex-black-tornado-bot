"""Main application entry point for 24/7 Railway deployment."""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.config import settings
from app.database.repository import DatabaseRepository
from app.feed.client import feed_client
from app.feed.candle_store import candle_store
from app.feed.websocket_manager import stream_manager
from app.engine.scheduler import SignalScheduler
from app.api.health import router as health_router
from app.api.stats import router as stats_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("quotex_m1_bot")

db_repo = DatabaseRepository()
scheduler = SignalScheduler(db_repo)


async def seed_initial_history():
    """Download initial historical candles for active symbols to prime indicators."""
    logger.info("Downloading initial M1 candle history for active pairs...")
    tasks = []
    sem = asyncio.Semaphore(5)

    async def fetch_one(sym: str):
        async with sem:
            try:
                candles = await feed_client.fetch_candles(sym, interval="1m", limit=120)
                if candles:
                    loaded = candle_store.load_initial_candles(sym, candles)
                    await db_repo.upsert_candles(sym, candles[-30:])
                    logger.debug(f"Loaded {loaded} bars for {sym}")
            except Exception as e:
                logger.warning(f"Could not load initial history for {sym}: {e}")

    for s in settings.ACTIVE_SYMBOLS:
        tasks.append(fetch_one(s))

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Initial candle history loaded.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management: startup & graceful shutdown."""
    logger.info("Starting Quotex M1 Signal Bot (Railway 24/7 Service)...")
    
    # 1. Initialize DB schema
    await db_repo.init_db()

    # 2. Prime candle cache from REST
    await seed_initial_history()

    # 3. Start real-time stream manager
    await stream_manager.start()

    # 4. Start scheduler loop
    await scheduler.start()

    yield

    # Shutdown
    logger.info("Initiating graceful shutdown...")
    await scheduler.stop()
    await stream_manager.stop()
    await feed_client.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Quotex M1 Signal Bot",
    description="Quantitative 24/7 OTC Signal Engine & Railway Persistent Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health_router)
app.include_router(stats_router)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run("app.main:app", host=settings.HOST, port=port, reload=False)

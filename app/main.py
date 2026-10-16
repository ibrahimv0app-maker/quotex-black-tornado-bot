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


async def background_startup_sequence():
    """Run initial REST seeding and stream connects in background so port binds immediately."""
    logger.info("Initializing database schema...")
    await db_repo.init_db()

    logger.info("Seeding initial M1 candle history for active OTC pairs...")
    sem = asyncio.Semaphore(5)

    async def fetch_one(sym: str):
        async with sem:
            try:
                candles = await feed_client.fetch_candles(sym, interval="1m", limit=120)
                if candles:
                    candle_store.load_initial_candles(sym, candles)
                    await db_repo.upsert_candles(sym, candles[-30:])
            except Exception as e:
                logger.warning(f"Could not load initial history for {sym}: {e}")

    tasks = [fetch_one(s) for s in settings.ACTIVE_SYMBOLS]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Initial candle history loaded.")

    logger.info("Starting real-time multi-stream workers...")
    await stream_manager.start()

    logger.info("Starting SignalScheduler 24/7 scanning loop...")
    await scheduler.start()
    logger.info("Bot engine fully online and actively scanning.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management: instant bind + background startup."""
    logger.info("Starting Quotex M1 Signal Bot (Railway 24/7 Service)...")
    
    # Launch startup sequence in background so FastAPI binds to $PORT immediately
    startup_task = asyncio.create_task(background_startup_sequence())

    yield

    # Graceful shutdown
    logger.info("Initiating graceful shutdown...")
    if not startup_task.done():
        startup_task.cancel()
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
    port_env = os.environ.get("PORT", "8000")
    try:
        port = int(port_env)
    except (ValueError, TypeError):
        port = 8000
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Binding server to {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

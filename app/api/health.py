"""HTTP health check routes for Railway persistent monitoring."""
import time
from fastapi import APIRouter
from app.config import settings
from app.feed.candle_store import candle_store
from app.feed.websocket_manager import stream_manager

router = APIRouter(tags=["Health"])
START_TIME = time.time()


@router.get("/health")
async def health_check():
    """Railway compatible primary health endpoint."""
    active_workers = sum(1 for w in stream_manager.workers if w.is_running)
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "kill_switch_active": settings.KILL_SWITCH_ACTIVE,
        "active_stream_workers": active_workers,
        "total_stream_workers": len(stream_manager.workers),
        "configured_symbols_count": len(settings.ACTIVE_SYMBOLS)
    }


@router.get("/health/feeds")
async def feed_health():
    """Real-time data freshness per pair."""
    now = int(time.time())
    feed_report = []

    for sym in settings.ACTIVE_SYMBOLS:
        quote = candle_store.get_last_quote(sym)
        closed_count = len(candle_store.get_closed_candles(sym, limit=200))
        if quote:
            price, ts = quote
            age = now - ts
            status = "HEALTHY" if age <= settings.DATA_STALE_SECONDS else "STALE"
        else:
            price, ts, age, status = None, 0, None, "NO_DATA"

        feed_report.append({
            "symbol": sym,
            "status": status,
            "last_price": price,
            "last_tick_timestamp": ts,
            "age_seconds": age,
            "closed_candles_in_memory": closed_count
        })

    return {
        "timestamp": now,
        "total_pairs": len(feed_report),
        "healthy_pairs": sum(1 for f in feed_report if f["status"] == "HEALTHY"),
        "feeds": feed_report
    }

"""Database repository managing schema, queries, and atomic signal locks."""
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, desc, func, and_
from app.config import settings
from app.database.models import Base, CandleRecord, PairHealthRecord, SignalRecord, OutcomeRecord, SystemDiagnosticEvent

logger = logging.getLogger(__name__)


class DatabaseRepository:
    def __init__(self, db_url: Optional[str] = None):
        self.url = db_url or settings.DATABASE_URL
        # Normalize postgresql:// to postgresql+asyncpg:// if needed
        if self.url.startswith("postgres://"):
            self.url = self.url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.url.startswith("postgresql://") and not self.url.startswith("postgresql+asyncpg://"):
            self.url = self.url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self.engine = create_async_engine(self.url, echo=False, future=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Create tables if they do not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized.")

    async def upsert_candles(self, symbol: str, candles: List[Dict[str, Any]]) -> int:
        """Upsert candles into database."""
        if not candles:
            return 0
        inserted = 0
        async with self.session_factory() as session:
            for c in candles:
                time_val = int(c["time"])
                # Check existence
                stmt = select(CandleRecord).where(
                    and_(CandleRecord.symbol == symbol, CandleRecord.time == time_val)
                )
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    rec = CandleRecord(
                        symbol=symbol,
                        time=time_val,
                        open=float(c["open"]),
                        high=float(c["high"]),
                        low=float(c["low"]),
                        close=float(c["close"]),
                        volume=float(c.get("volume", 1.0))
                    )
                    session.add(rec)
                    inserted += 1
            await session.commit()
        return inserted

    async def get_recent_candles(self, symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Retrieve the most recent candles for a symbol sorted chronologically ascending."""
        async with self.session_factory() as session:
            stmt = select(CandleRecord).where(
                CandleRecord.symbol == symbol
            ).order_by(desc(CandleRecord.time)).limit(limit)
            res = await session.execute(stmt)
            records = res.scalars().all()
            # Return ascending order
            return [
                {
                    "time": r.time,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume
                }
                for r in reversed(records)
            ]

    async def update_pair_health(
        self,
        symbol: str,
        last_tick_time: int,
        last_tick_price: Optional[float],
        latency_ms: float,
        is_stale: bool,
        status: str,
        active_candles: int = 0
    ):
        """Update or insert pair health record."""
        async with self.session_factory() as session:
            stmt = select(PairHealthRecord).where(PairHealthRecord.symbol == symbol)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.last_tick_time = last_tick_time
                if last_tick_price is not None:
                    existing.last_tick_price = last_tick_price
                existing.latency_ms = latency_ms
                existing.is_stale = is_stale
                existing.status = status
                existing.active_candles_count = active_candles
            else:
                new_rec = PairHealthRecord(
                    symbol=symbol,
                    last_tick_time=last_tick_time,
                    last_tick_price=last_tick_price,
                    latency_ms=latency_ms,
                    is_stale=is_stale,
                    status=status,
                    active_candles_count=active_candles
                )
                session.add(new_rec)
            await session.commit()

    async def get_all_pair_health(self) -> List[Dict[str, Any]]:
        """Fetch all pair health records."""
        async with self.session_factory() as session:
            stmt = select(PairHealthRecord)
            res = await session.execute(stmt)
            return [
                {
                    "symbol": r.symbol,
                    "last_tick_time": r.last_tick_time,
                    "last_tick_price": r.last_tick_price,
                    "latency_ms": r.latency_ms,
                    "is_stale": r.is_stale,
                    "status": r.status,
                    "active_candles": r.active_candles_count
                }
                for r in res.scalars().all()
            ]

    async def get_active_signal(self) -> Optional[Dict[str, Any]]:
        """Retrieve the currently active unresolved signal if any exists."""
        async with self.session_factory() as session:
            stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE").limit(1)
            res = await session.execute(stmt)
            sig = res.scalar_one_or_none()
            if not sig:
                return None
            return {
                "signal_id": sig.signal_id,
                "symbol": sig.symbol,
                "direction": sig.direction,
                "strategy_name": sig.strategy_name,
                "setup_score": sig.setup_score,
                "signal_sent_time": sig.signal_sent_time,
                "intended_entry_time": sig.intended_entry_time,
                "intended_expiry_time": sig.intended_expiry_time,
                "signal_price": sig.signal_price,
                "status": sig.status,
                "details": json.loads(sig.details_json) if sig.details_json else {}
            }

    async def acquire_signal_lock_and_create(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        strategy_name: str,
        setup_score: float,
        signal_sent_time: int,
        intended_entry_time: int,
        intended_expiry_time: int,
        signal_price: Optional[float],
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Atomic creation of a signal.
        Guarantees that no other active signal exists (Global Lock).
        """
        async with self.session_factory() as session:
            async with session.begin():
                # Check for active signal
                stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE").with_for_update()
                res = await session.execute(stmt)
                if res.scalar_one_or_none():
                    logger.warning("Global lock active: existing unresolved signal prevents new dispatch.")
                    return False

                # Ensure signal_id or entry slot is unique
                slot_stmt = select(SignalRecord).where(
                    SignalRecord.intended_entry_time == intended_entry_time
                )
                if (await session.execute(slot_stmt)).scalar_one_or_none():
                    logger.warning(f"Slot {intended_entry_time} already has an entry. Skipping.")
                    return False

                new_sig = SignalRecord(
                    signal_id=signal_id,
                    symbol=symbol,
                    direction=direction,
                    strategy_name=strategy_name,
                    setup_score=setup_score,
                    signal_sent_time=signal_sent_time,
                    intended_entry_time=intended_entry_time,
                    intended_expiry_time=intended_expiry_time,
                    signal_price=signal_price,
                    status="ACTIVE",
                    details_json=json.dumps(details)
                )
                session.add(new_sig)
                await session.flush()
                return True

    async def resolve_signal(
        self,
        signal_id: str,
        outcome: str,
        entry_quote: Optional[float],
        expiry_quote: Optional[float],
        price_delta: Optional[float],
        is_verified: bool,
        reason: Optional[str] = None
    ) -> bool:
        """Record the outcome and mark signal as RESOLVED (releases global lock)."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = select(SignalRecord).where(SignalRecord.signal_id == signal_id)
                res = await session.execute(stmt)
                sig = res.scalar_one_or_none()
                if not sig:
                    return False

                sig.status = "RESOLVED"
                outcome_rec = OutcomeRecord(
                    signal_id=signal_id,
                    outcome=outcome,
                    entry_quote=entry_quote,
                    expiry_quote=expiry_quote,
                    price_delta=price_delta,
                    is_verified=is_verified,
                    reason=reason
                )
                session.add(outcome_rec)
                await session.flush()
                return True

    async def get_stats(self) -> Dict[str, Any]:
        """Compute honest statistical summary."""
        async with self.session_factory() as session:
            total_signals_stmt = select(func.count(SignalRecord.signal_id))
            total_signals = (await session.execute(total_signals_stmt)).scalar() or 0

            outcomes_stmt = select(OutcomeRecord.outcome, func.count(OutcomeRecord.id)).group_by(OutcomeRecord.outcome)
            outcome_counts = dict((await session.execute(outcomes_stmt)).all())

            wins = outcome_counts.get("WIN", 0)
            losses = outcome_counts.get("LOSS", 0)
            draws = outcome_counts.get("DRAW", 0)
            unverified = outcome_counts.get("UNVERIFIED", 0)

            # Strict denominator: Wins / (Wins + Losses)
            decisive_trades = wins + losses
            win_rate = round((wins / decisive_trades * 100), 2) if decisive_trades > 0 else 0.0

            return {
                "total_signals": total_signals,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "unverified": unverified,
                "win_rate_percent": win_rate,
                "sample_size": decisive_trades
            }

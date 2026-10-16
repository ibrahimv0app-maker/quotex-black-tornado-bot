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
        self.raw_url = db_url or settings.DATABASE_URL
        self.url = self._normalize_url(self.raw_url)
        self.engine = create_async_engine(self.url, echo=False, future=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def _normalize_url(self, raw: str) -> str:
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw.startswith("postgresql://") and not raw.startswith("postgresql+asyncpg://"):
            return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        return raw

    async def init_db(self):
        """Create tables if they do not exist, falling back to SQLite if Postgres connection fails."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to connect to primary DB ({self.url}): {e}. Falling back to SQLite...")
            self.url = "sqlite+aiosqlite:///quotex_bot.db"
            self.engine = create_async_engine(self.url, echo=False, future=True)
            self.session_factory = async_sessionmaker(
                bind=self.engine, class_=AsyncSession, expire_on_commit=False
            )
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Fallback SQLite schema initialized.")

    async def upsert_candles(self, symbol: str, candles: List[Dict[str, Any]]) -> int:
        """Upsert candles into database."""
        if not candles:
            return 0
        inserted = 0
        try:
            async with self.session_factory() as session:
                for c in candles:
                    time_val = int(c["time"])
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
        except Exception as e:
            logger.warning(f"Error in upsert_candles for {symbol}: {e}")
        return inserted

    async def acquire_signal_lock(self, signal_data: Dict[str, Any]) -> Optional[SignalRecord]:
        """Atomically insert a new signal only if no ACTIVE signal exists."""
        async with self.session_factory() as session:
            stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE")
            res = await session.execute(stmt)
            active = res.scalar_one_or_none()
            if active:
                logger.info(f"Lock denied: existing ACTIVE signal #{active.id} on {active.symbol} is pending.")
                return None

            sig = SignalRecord(
                symbol=signal_data["symbol"],
                direction=signal_data["direction"],
                strategy_name=signal_data["strategy_name"],
                entry_time=signal_data["entry_time"],
                expiry_time=signal_data["expiry_time"],
                entry_price_est=signal_data.get("entry_price_est"),
                score=signal_data.get("score", 0.0),
                features_snapshot=json.dumps(signal_data.get("features", {})),
                telegram_message_id=signal_data.get("telegram_message_id"),
                status="ACTIVE"
            )
            session.add(sig)
            await session.commit()
            await session.refresh(sig)
            logger.info(f"Signal lock acquired: created ACTIVE signal #{sig.id} on {sig.symbol} {sig.direction}")
            return sig

    async def get_active_signal(self) -> Optional[SignalRecord]:
        """Fetch the currently active unresolved signal."""
        try:
            async with self.session_factory() as session:
                stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE").order_by(desc(SignalRecord.id))
                res = await session.execute(stmt)
                return res.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting active signal: {e}")
            return None

    async def resolve_signal(self, signal_id: int, outcome_data: Dict[str, Any]) -> Optional[OutcomeRecord]:
        """Atomically mark signal resolved and record outcome."""
        try:
            async with self.session_factory() as session:
                sig = await session.get(SignalRecord, signal_id)
                if not sig:
                    return None

                sig.status = "RESOLVED"

                outcome = OutcomeRecord(
                    signal_id=signal_id,
                    entry_price=outcome_data["entry_price"],
                    expiry_price=outcome_data["expiry_price"],
                    outcome=outcome_data["outcome"],
                    diff=outcome_data.get("diff", 0.0),
                    data_source=outcome_data.get("data_source", "REST_INTERPOLATED"),
                    tolerance_status=outcome_data.get("tolerance_status", "VALID"),
                    evaluated_at=outcome_data.get("evaluated_at", 0)
                )
                session.add(outcome)
                await session.commit()
                await session.refresh(outcome)
                logger.info(f"Signal #{signal_id} marked RESOLVED with outcome {outcome.outcome}")
                return outcome
        except Exception as e:
            logger.error(f"Error resolving signal #{signal_id}: {e}")
            return None

    async def get_recent_outcomes(self, limit: int = 50) -> List[OutcomeRecord]:
        """Fetch list of recent resolved outcomes."""
        try:
            async with self.session_factory() as session:
                stmt = select(OutcomeRecord).order_by(desc(OutcomeRecord.id)).limit(limit)
                res = await session.execute(stmt)
                return list(res.scalars().all())
        except Exception as e:
            logger.error(f"Error getting recent outcomes: {e}")
            return []

    async def get_cumulative_stats(self) -> Dict[str, Any]:
        """Calculate verified win, loss, and winrate."""
        try:
            async with self.session_factory() as session:
                wins = await session.scalar(select(func.count(OutcomeRecord.id)).where(OutcomeRecord.outcome == "WIN")) or 0
                losses = await session.scalar(select(func.count(OutcomeRecord.id)).where(OutcomeRecord.outcome == "LOSS")) or 0
                draws = await session.scalar(select(func.count(OutcomeRecord.id)).where(OutcomeRecord.outcome == "DRAW")) or 0
                unverified = await session.scalar(select(func.count(OutcomeRecord.id)).where(OutcomeRecord.outcome == "UNVERIFIED")) or 0

                decisive = wins + losses
                winrate = round((wins / decisive * 100), 1) if decisive > 0 else 0.0

                return {
                    "wins": wins,
                    "losses": losses,
                    "draws": draws,
                    "unverified": unverified,
                    "total_signals": wins + losses + draws + unverified,
                    "win_rate": winrate
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"wins": 0, "losses": 0, "draws": 0, "unverified": 0, "total_signals": 0, "win_rate": 0.0}

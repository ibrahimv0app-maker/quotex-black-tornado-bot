"""Database repository managing schema, queries, and atomic signal locks."""
import json
import logging
import time
import datetime
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
        """Atomically insert a new signal only if no ACTIVE signal exists.

        This method accepts a flexible dict (legacy support). It will map common
        keys into the current SignalRecord schema. Prefer using
        `acquire_signal_lock_and_create` which matches the scheduler call-site.
        """
        async with self.session_factory() as session:
            stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE")
            res = await session.execute(stmt)
            active = res.scalar_one_or_none()
            if active:
                # model uses signal_id as primary key
                logger.info(f"Lock denied: existing ACTIVE signal #{active.signal_id} on {active.symbol} is pending.")
                return None

            # Map legacy keys to current model fields
            sig_id = signal_data.get("signal_id") or signal_data.get("id") or f"SIG_{int(time.time())}"
            setup_score = signal_data.get("score") or signal_data.get("setup_score") or 0.0
            signal_sent_time = signal_data.get("signal_sent_time") or signal_data.get("entry_time") or int(time.time())
            intended_entry_time = signal_data.get("intended_entry_time") or signal_data.get("entry_time") or signal_sent_time
            intended_expiry_time = signal_data.get("intended_expiry_time") or signal_data.get("expiry_time") or signal_sent_time + settings.EXPIRY_SECONDS
            signal_price = signal_data.get("signal_price") or signal_data.get("entry_price_est") or None
            details = signal_data.get("details") or signal_data.get("features") or {}

            sig = SignalRecord(
                signal_id=sig_id,
                symbol=signal_data.get("symbol"),
                direction=signal_data.get("direction"),
                strategy_name=signal_data.get("strategy_name"),
                setup_score=setup_score,
                signal_sent_time=signal_sent_time,
                intended_entry_time=intended_entry_time,
                intended_expiry_time=intended_expiry_time,
                signal_price=signal_price,
                status="ACTIVE",
                details_json=json.dumps(details)
            )
            session.add(sig)
            await session.commit()
            await session.refresh(sig)
            logger.info(f"Signal lock acquired: created ACTIVE signal #{sig.signal_id} on {sig.symbol} {sig.direction}")
            return sig

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
        details: Dict[str, Any]
    ) -> bool:
        """Atomic method used by the scheduler to acquire global signal lock and create the signal.

        Returns True if lock acquired and signal created, False if an ACTIVE signal already exists.
        """
        try:
            async with self.session_factory() as session:
                stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE")
                res = await session.execute(stmt)
                active = res.scalar_one_or_none()
                if active:
                    logger.info(f"Lock denied: existing ACTIVE signal #{active.signal_id} on {active.symbol} is pending.")
                    return False

                sig = SignalRecord(
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
                    details_json=json.dumps(details if details is not None else {})
                )
                session.add(sig)
                await session.commit()
                await session.refresh(sig)
                logger.info(f"Signal lock acquired: created ACTIVE signal #{sig.signal_id} on {sig.symbol} {sig.direction}")
                return True
        except Exception as e:
            logger.error(f"Error acquiring signal lock/create for {signal_id}: {e}")
            return False

    async def get_active_signal(self) -> Optional[SignalRecord]:
        """Fetch the currently active unresolved signal."""
        try:
            async with self.session_factory() as session:
                # order by newest created_at to find the most recent ACTIVE signal
                stmt = select(SignalRecord).where(SignalRecord.status == "ACTIVE").order_by(desc(SignalRecord.created_at))
                res = await session.execute(stmt)
                return res.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting active signal: {e}")
            return None

    async def resolve_signal(self, signal_id: str, outcome_data: Dict[str, Any]) -> Optional[OutcomeRecord]:
        """Atomically mark signal resolved and record outcome."""
        try:
            async with self.session_factory() as session:
                sig = await session.get(SignalRecord, signal_id)
                if not sig:
                    return None

                sig.status = "RESOLVED"

                # normalize evaluated_at to a datetime if an int timestamp was provided
                evaluated_at = outcome_data.get("evaluated_at")
                if isinstance(evaluated_at, (int, float)):
                    try:
                        evaluated_dt = datetime.datetime.utcfromtimestamp(int(evaluated_at))
                    except Exception:
                        evaluated_dt = None
                elif isinstance(evaluated_at, datetime.datetime):
                    evaluated_dt = evaluated_at
                else:
                    evaluated_dt = None

                outcome = OutcomeRecord(
                    signal_id=signal_id,
                    entry_quote=outcome_data.get("entry_quote") or outcome_data.get("entry_price"),
                    expiry_quote=outcome_data.get("expiry_quote") or outcome_data.get("expiry_price"),
                    outcome=outcome_data.get("outcome"),
                    price_delta=outcome_data.get("diff") or outcome_data.get("price_delta"),
                    is_verified=outcome_data.get("is_verified", False),
                    reason=outcome_data.get("reason"),
                    evaluated_at=evaluated_dt
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

    async def get_last_outcome_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Return the most recent outcome for a symbol joined with its signal metadata.
        """
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(OutcomeRecord, SignalRecord)
                    .join(SignalRecord, OutcomeRecord.signal_id == SignalRecord.signal_id)
                    .where(SignalRecord.symbol == symbol)
                    .order_by(desc(OutcomeRecord.evaluated_at))
                    .limit(1)
                )
                res = await session.execute(stmt)
                row = res.first()
                if not row:
                    return None
                outcome_row, sig_row = row[0], row[1]
                return {
                    "signal_id": outcome_row.signal_id,
                    "outcome": outcome_row.outcome,
                    "evaluated_at": outcome_row.evaluated_at,
                    "intended_expiry_time": sig_row.intended_expiry_time,
                    "direction": sig_row.direction,
                }
        except Exception as e:
            logger.error(f"Error getting last outcome for {symbol}: {e}")
            return None

    async def mark_signal_pending_recovery(self, signal_id: str, details_update: Dict[str, Any] = None) -> bool:
        """
        Mark an active signal as PENDING_RECOVERY and merge optional details into details_json.
        Returns True if updated.
        """
        try:
            async with self.session_factory() as session:
                sig = await session.get(SignalRecord, signal_id)
                if not sig:
                    return False
                try:
                    details = json.loads(sig.details_json or "{}")
                except Exception:
                    details = {}
                if details_update:
                    details.update(details_update)
                sig.details_json = json.dumps(details)
                sig.status = "PENDING_RECOVERY"
                await session.commit()
                await session.refresh(sig)
                logger.info(f"Signal {signal_id} marked PENDING_RECOVERY")
                return True
        except Exception as e:
            logger.error(f"Error marking {signal_id} pending recovery: {e}")
            return False

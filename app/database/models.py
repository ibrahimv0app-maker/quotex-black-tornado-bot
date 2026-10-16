"""Database models using SQLAlchemy async declarative base."""
import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, BigInteger, Index, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CandleRecord(Base):
    """Historical and aggregated 1-minute candle records."""
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    time = Column(BigInteger, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_symbol_time_unique", "symbol", "time", unique=True),
    )


class PairHealthRecord(Base):
    """Real-time data stream health tracker per symbol."""
    __tablename__ = "pair_health"

    symbol = Column(String(32), primary_key=True)
    last_tick_time = Column(BigInteger, default=0)
    last_tick_price = Column(Float, nullable=True)
    latency_ms = Column(Float, default=0.0)
    is_stale = Column(Boolean, default=False)
    active_candles_count = Column(Integer, default=0)
    status = Column(String(32), default="DISCONNECTED")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class SignalRecord(Base):
    """Dispatched signals and their lifecycle state."""
    __tablename__ = "signals"

    signal_id = Column(String(32), primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # CALL or PUT
    strategy_name = Column(String(64), nullable=False)
    setup_score = Column(Float, nullable=False)
    
    # Timestamps (Unix seconds)
    signal_sent_time = Column(BigInteger, nullable=False)
    intended_entry_time = Column(BigInteger, nullable=False, index=True)
    intended_expiry_time = Column(BigInteger, nullable=False)
    
    # Observed price at signal time
    signal_price = Column(Float, nullable=True)
    status = Column(String(32), default="ACTIVE")  # ACTIVE, RESOLVED, CANCELLED, UNVERIFIED
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    outcome = relationship("OutcomeRecord", uselist=False, back_populates="signal")


class OutcomeRecord(Base):
    """Settlement outcome for a signal after expiry."""
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(32), ForeignKey("signals.signal_id"), unique=True, nullable=False)
    outcome = Column(String(32), nullable=False)  # WIN, LOSS, DRAW, UNVERIFIED
    entry_quote = Column(Float, nullable=True)
    expiry_quote = Column(Float, nullable=True)
    price_delta = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False)
    reason = Column(String(255), nullable=True)
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow)

    signal = relationship("SignalRecord", back_populates="outcome")


class SystemDiagnosticEvent(Base):
    """Audit log of cycle scans and rejection diagnostics."""
    __tablename__ = "system_diagnostics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    evaluated_candidates = Column(Integer, default=0)
    top_candidate = Column(String(32), nullable=True)
    top_score = Column(Float, default=0.0)
    decision = Column(String(32), default="NO_SIGNAL")
    notes = Column(Text, nullable=True)

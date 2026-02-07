"""Signal database model"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Index
from sqlalchemy.sql import func
from .base import Base


class SignalModel(Base):
    """
    Database model for signals.
    Optimized for time-series queries using TimescaleDB.
    """

    __tablename__ = "signals"

    # Use TimescaleDB hypertable on timestamp
    # Will be created via: SELECT create_hypertable('signals', 'timestamp');

    id = Column(String, primary_key=True)  # UUID
    company_id = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)  # Store as string to avoid circular import

    # Temporal
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    # Signal values
    raw_value = Column(JSON, nullable=False)
    normalized_value = Column(Float, nullable=False)
    score = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)

    # Metadata
    signal_metadata = Column(JSON, nullable=False)
    description = Column(String, nullable=True)
    tags = Column(JSON, default=list)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_company_timestamp', 'company_id', 'timestamp'),
        Index('idx_company_signal_type', 'company_id', 'signal_type'),
        Index('idx_signal_type_timestamp', 'signal_type', 'timestamp'),
        Index('idx_category_timestamp', 'category', 'timestamp'),
        Index('idx_score', 'score'),
    )

    def __repr__(self):
        return f"<Signal {self.signal_type} for {self.company_id} at {self.timestamp}>"

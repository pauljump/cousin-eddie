"""
Market data models for backtesting.

Stock prices, options data, and other market information.
This is the dependent variable we're trying to predict with signals.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class StockPrice(Base):
    """Daily stock price data (OHLCV)"""

    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # OHLCV
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    adj_close = Column(Float, nullable=True)  # Adjusted for splits/dividends
    volume = Column(Integer, nullable=False)

    # Derived metrics
    daily_return = Column(Float, nullable=True)  # (close - prev_close) / prev_close
    intraday_range = Column(Float, nullable=True)  # (high - low) / open

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date'),
        Index('ix_ticker_date', 'ticker', 'date'),
    )


class IntradayPrice(Base):
    """Intraday price data (minute-level or finer)"""

    __tablename__ = "intraday_prices"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # OHLCV for the interval
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

    # Interval (e.g., "1m", "5m", "1h")
    interval = Column(String, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('ticker', 'timestamp', 'interval', name='uix_ticker_timestamp_interval'),
        Index('ix_ticker_timestamp', 'ticker', 'timestamp'),
    )


class OptionsChain(Base):
    """Options chain snapshot - all available strikes/expirations at a point in time"""

    __tablename__ = "options_chains"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)

    # Option details
    expiration_date = Column(Date, nullable=False, index=True)
    strike = Column(Float, nullable=False)
    option_type = Column(String, nullable=False)  # "call" or "put"

    # Pricing
    last_price = Column(Float, nullable=True)
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)

    # Volume and interest
    volume = Column(Integer, nullable=True)
    open_interest = Column(Integer, nullable=True)

    # Greeks
    delta = Column(Float, nullable=True)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    rho = Column(Float, nullable=True)

    # Implied volatility
    implied_volatility = Column(Float, nullable=True)

    # Moneyness
    in_the_money = Column(Boolean, nullable=True)

    # Underlying price at time of snapshot
    underlying_price = Column(Float, nullable=True)

    # Days to expiration
    days_to_expiration = Column(Integer, nullable=True)

    # Raw data from API
    raw_data = Column(JSONB, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            'ticker', 'snapshot_date', 'expiration_date', 'strike', 'option_type',
            name='uix_options_chain_unique'
        ),
        Index('ix_ticker_snapshot', 'ticker', 'snapshot_date'),
        Index('ix_expiration', 'expiration_date'),
    )


class OptionsMetrics(Base):
    """Aggregated options market metrics - overall market sentiment indicators"""

    __tablename__ = "options_metrics"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Put/Call ratios
    put_call_ratio_volume = Column(Float, nullable=True)  # Put volume / Call volume
    put_call_ratio_oi = Column(Float, nullable=True)  # Put OI / Call OI

    # Implied volatility metrics
    iv_30day = Column(Float, nullable=True)  # 30-day implied volatility
    iv_rank = Column(Float, nullable=True)  # Where current IV sits in 52-week range
    iv_percentile = Column(Float, nullable=True)  # Percentile of IV over past year

    # Skew
    call_skew = Column(Float, nullable=True)  # OTM call IV vs ATM
    put_skew = Column(Float, nullable=True)  # OTM put IV vs ATM

    # Volume
    total_call_volume = Column(Integer, nullable=True)
    total_put_volume = Column(Integer, nullable=True)
    total_call_oi = Column(Integer, nullable=True)
    total_put_oi = Column(Integer, nullable=True)

    # Stock price at time of calculation
    underlying_price = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date_options_metrics'),
        Index('ix_ticker_date_metrics', 'ticker', 'date'),
    )


class MarketIndex(Base):
    """Market index data for comparison (SPY, QQQ, etc.)"""

    __tablename__ = "market_indices"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)  # SPY, QQQ, DIA, etc.
    date = Column(Date, nullable=False, index=True)

    # OHLCV
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

    # Daily return
    daily_return = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uix_symbol_date'),
        Index('ix_symbol_date', 'symbol', 'date'),
    )

"""
Stock price data fetcher using yfinance.

Fetches historical daily OHLCV data.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import yfinance as yf
from loguru import logger
from sqlalchemy.orm import Session

from ..models.market_data import StockPrice
from ..models.base import SessionLocal


class StockPriceFetcher:
    """Fetch and store stock price data"""

    def __init__(self):
        pass

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        session: Optional[Session] = None
    ) -> int:
        """
        Fetch daily stock prices and store in database.

        Returns:
            Number of new price records stored
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            logger.info(f"Fetching stock prices for {ticker} from {start_date.date()} to {end_date.date()}")

            # Fetch data from yfinance
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, auto_adjust=False)

            if df.empty:
                logger.warning(f"No price data found for {ticker}")
                return 0

            logger.info(f"Retrieved {len(df)} price records for {ticker}")

            # Calculate daily returns
            df['daily_return'] = df['Close'].pct_change()
            df['intraday_range'] = (df['High'] - df['Low']) / df['Open']

            # Store in database
            count = 0
            for date, row in df.iterrows():
                # Check if already exists
                existing = session.query(StockPrice).filter(
                    StockPrice.ticker == ticker,
                    StockPrice.date == date.date()
                ).first()

                if existing:
                    continue

                price_record = StockPrice(
                    ticker=ticker,
                    date=date.date(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    adj_close=float(row['Close']) if 'Adj Close' not in row else float(row['Adj Close']),
                    volume=int(row['Volume']),
                    daily_return=float(row['daily_return']) if not pd.isna(row['daily_return']) else None,
                    intraday_range=float(row['intraday_range']) if not pd.isna(row['intraday_range']) else None,
                )

                session.add(price_record)
                count += 1

            session.commit()
            logger.info(f"Stored {count} new price records for {ticker}")

            return count

        except Exception as e:
            logger.error(f"Error fetching stock prices for {ticker}: {e}")
            session.rollback()
            return 0

        finally:
            if close_session:
                session.close()

    def fetch_intraday_prices(
        self,
        ticker: str,
        interval: str = "1m",  # 1m, 5m, 15m, 1h, etc.
        period: str = "7d",  # max for 1m is 7d
        session: Optional[Session] = None
    ) -> int:
        """
        Fetch intraday stock prices.

        Note: yfinance has limitations on intraday data:
        - 1m: max 7 days
        - 5m: max 60 days
        - 1h: max 730 days
        """
        from ..models.market_data import IntradayPrice

        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            logger.info(f"Fetching {interval} intraday data for {ticker} (period: {period})")

            stock = yf.Ticker(ticker)
            df = stock.history(interval=interval, period=period)

            if df.empty:
                logger.warning(f"No intraday data found for {ticker}")
                return 0

            logger.info(f"Retrieved {len(df)} intraday records for {ticker}")

            # Store in database
            count = 0
            for timestamp, row in df.iterrows():
                # Check if already exists
                existing = session.query(IntradayPrice).filter(
                    IntradayPrice.ticker == ticker,
                    IntradayPrice.timestamp == timestamp,
                    IntradayPrice.interval == interval
                ).first()

                if existing:
                    continue

                intraday_record = IntradayPrice(
                    ticker=ticker,
                    timestamp=timestamp,
                    interval=interval,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                )

                session.add(intraday_record)
                count += 1

            session.commit()
            logger.info(f"Stored {count} new intraday records for {ticker}")

            return count

        except Exception as e:
            logger.error(f"Error fetching intraday data for {ticker}: {e}")
            session.rollback()
            return 0

        finally:
            if close_session:
                session.close()


# Pandas import
import pandas as pd

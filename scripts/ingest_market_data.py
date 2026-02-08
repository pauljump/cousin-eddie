#!/usr/bin/env python3
"""
Ingest market data (stock prices, options) for backtesting.

Usage:
    python scripts/ingest_market_data.py --ticker UBER --start 2019-01-01
    python scripts/ingest_market_data.py --ticker UBER --start 2019-01-01 --options
    python scripts/ingest_market_data.py --ticker UBER --intraday --period 7d
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.market_data.stock_prices import StockPriceFetcher
from src.market_data.options_data import OptionsDataFetcher
from src.models.base import SessionLocal, engine, Base

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)


def main():
    parser = argparse.ArgumentParser(description="Ingest market data for backtesting")
    parser.add_argument("--ticker", type=str, required=True, help="Stock ticker (e.g., UBER)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD, defaults to today)")
    parser.add_argument("--options", action="store_true", help="Fetch options chain data")
    parser.add_argument("--intraday", action="store_true", help="Fetch intraday price data")
    parser.add_argument("--interval", type=str, default="1m", help="Intraday interval (1m, 5m, 15m, 1h)")
    parser.add_argument("--period", type=str, default="7d", help="Intraday period (7d, 60d, etc.)")

    args = parser.parse_args()

    ticker = args.ticker.upper()

    logger.info("=" * 60)
    logger.info("Market Data Ingestion")
    logger.info("=" * 60)
    logger.info(f"Ticker: {ticker}")
    logger.info("=" * 60)
    logger.info("")

    session = SessionLocal()

    try:
        # Fetch daily prices
        if args.start:
            start_date = datetime.strptime(args.start, "%Y-%m-%d")
            end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()

            logger.info(f"Fetching daily prices from {start_date.date()} to {end_date.date()}")

            price_fetcher = StockPriceFetcher()
            count = price_fetcher.fetch_daily_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                session=session
            )

            logger.info(f"✓ Stored {count} daily price records")
            logger.info("")

        # Fetch intraday data
        if args.intraday:
            logger.info(f"Fetching intraday data ({args.interval} bars for {args.period})")

            price_fetcher = StockPriceFetcher()
            count = price_fetcher.fetch_intraday_prices(
                ticker=ticker,
                interval=args.interval,
                period=args.period,
                session=session
            )

            logger.info(f"✓ Stored {count} intraday price records")
            logger.info("")

        # Fetch options chain
        if args.options:
            logger.info("Fetching current options chain")

            options_fetcher = OptionsDataFetcher()
            count = options_fetcher.fetch_options_chain(
                ticker=ticker,
                session=session
            )

            logger.info(f"✓ Stored {count} option contracts")
            logger.info("")

    except Exception as e:
        logger.error(f"Error during market data ingestion: {e}")
        import traceback
        traceback.print_exc()

    finally:
        session.close()

    logger.info("=" * 60)
    logger.info("Market data ingestion complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

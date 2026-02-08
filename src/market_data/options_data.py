"""
Options chain data fetcher using yfinance.

Fetches options chain (strikes, prices, greeks, IV) for all expirations.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import yfinance as yf
import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from ..models.market_data import OptionsChain, OptionsMetrics
from ..models.base import SessionLocal


class OptionsDataFetcher:
    """Fetch and store options chain data"""

    def __init__(self):
        pass

    def fetch_options_chain(
        self,
        ticker: str,
        snapshot_date: Optional[datetime] = None,
        session: Optional[Session] = None
    ) -> int:
        """
        Fetch full options chain for all expirations and store in database.

        Args:
            ticker: Stock symbol
            snapshot_date: Date of snapshot (defaults to today)
            session: Database session

        Returns:
            Number of option contracts stored
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        if snapshot_date is None:
            snapshot_date = datetime.now()

        try:
            logger.info(f"Fetching options chain for {ticker} on {snapshot_date.date()}")

            stock = yf.Ticker(ticker)

            # Get current stock price
            try:
                current_price = float(stock.history(period="1d")['Close'].iloc[-1])
            except:
                logger.warning(f"Could not fetch current price for {ticker}, using None")
                current_price = None

            # Get all expiration dates
            expirations = stock.options

            if not expirations:
                logger.warning(f"No options expirations found for {ticker}")
                return 0

            logger.info(f"Found {len(expirations)} expiration dates for {ticker}")

            total_count = 0

            for expiration_str in expirations:
                try:
                    # Fetch options chain for this expiration
                    opt_chain = stock.option_chain(expiration_str)

                    # Process calls
                    calls_count = self._store_options_data(
                        session=session,
                        ticker=ticker,
                        snapshot_date=snapshot_date.date(),
                        expiration_str=expiration_str,
                        options_df=opt_chain.calls,
                        option_type="call",
                        underlying_price=current_price
                    )

                    # Process puts
                    puts_count = self._store_options_data(
                        session=session,
                        ticker=ticker,
                        snapshot_date=snapshot_date.date(),
                        expiration_str=expiration_str,
                        options_df=opt_chain.puts,
                        option_type="put",
                        underlying_price=current_price
                    )

                    total_count += calls_count + puts_count
                    logger.debug(f"  {expiration_str}: {calls_count} calls, {puts_count} puts")

                except Exception as e:
                    logger.error(f"Error processing expiration {expiration_str}: {e}")
                    continue

            session.commit()
            logger.info(f"Stored {total_count} option contracts for {ticker}")

            # Calculate and store aggregated metrics
            self._calculate_options_metrics(session, ticker, snapshot_date.date())

            return total_count

        except Exception as e:
            logger.error(f"Error fetching options chain for {ticker}: {e}")
            session.rollback()
            return 0

        finally:
            if close_session:
                session.close()

    def _store_options_data(
        self,
        session: Session,
        ticker: str,
        snapshot_date: datetime.date,
        expiration_str: str,
        options_df: pd.DataFrame,
        option_type: str,
        underlying_price: Optional[float]
    ) -> int:
        """Store options data from DataFrame"""

        if options_df.empty:
            return 0

        expiration_date = datetime.strptime(expiration_str, "%Y-%m-%d").date()
        days_to_expiration = (expiration_date - snapshot_date).days

        count = 0

        for _, row in options_df.iterrows():
            # Check if already exists
            existing = session.query(OptionsChain).filter(
                OptionsChain.ticker == ticker,
                OptionsChain.snapshot_date == snapshot_date,
                OptionsChain.expiration_date == expiration_date,
                OptionsChain.strike == float(row['strike']),
                OptionsChain.option_type == option_type
            ).first()

            if existing:
                continue

            # Calculate moneyness
            in_the_money = None
            if underlying_price:
                if option_type == "call":
                    in_the_money = underlying_price > row['strike']
                else:  # put
                    in_the_money = underlying_price < row['strike']

            # Convert row to dict and handle JSON serialization
            raw_data_dict = {}
            for k, v in row.items():
                if pd.isna(v):
                    raw_data_dict[k] = None
                elif isinstance(v, pd.Timestamp):
                    raw_data_dict[k] = v.isoformat()
                elif isinstance(v, (int, float, str, bool)):
                    raw_data_dict[k] = v
                else:
                    raw_data_dict[k] = str(v)

            option_record = OptionsChain(
                ticker=ticker,
                snapshot_date=snapshot_date,
                expiration_date=expiration_date,
                strike=float(row['strike']),
                option_type=option_type,
                last_price=float(row.get('lastPrice', 0)) if not pd.isna(row.get('lastPrice')) else None,
                bid=float(row.get('bid', 0)) if not pd.isna(row.get('bid')) else None,
                ask=float(row.get('ask', 0)) if not pd.isna(row.get('ask')) else None,
                volume=int(row.get('volume', 0)) if not pd.isna(row.get('volume')) else None,
                open_interest=int(row.get('openInterest', 0)) if not pd.isna(row.get('openInterest')) else None,
                implied_volatility=float(row.get('impliedVolatility', 0)) if not pd.isna(row.get('impliedVolatility')) else None,
                in_the_money=in_the_money,
                underlying_price=underlying_price,
                days_to_expiration=days_to_expiration,
                raw_data=raw_data_dict
            )

            session.add(option_record)
            count += 1

        return count

    def _calculate_options_metrics(
        self,
        session: Session,
        ticker: str,
        date: datetime.date
    ):
        """Calculate and store aggregated options metrics"""

        # Check if metrics already exist
        existing = session.query(OptionsMetrics).filter(
            OptionsMetrics.ticker == ticker,
            OptionsMetrics.date == date
        ).first()

        if existing:
            return

        # Get all options for this ticker and date
        options = session.query(OptionsChain).filter(
            OptionsChain.ticker == ticker,
            OptionsChain.snapshot_date == date
        ).all()

        if not options:
            return

        # Separate calls and puts
        calls = [o for o in options if o.option_type == "call"]
        puts = [o for o in options if o.option_type == "put"]

        # Calculate totals
        total_call_volume = sum(o.volume or 0 for o in calls)
        total_put_volume = sum(o.volume or 0 for o in puts)
        total_call_oi = sum(o.open_interest or 0 for o in calls)
        total_put_oi = sum(o.open_interest or 0 for o in puts)

        # Put/call ratios
        put_call_ratio_volume = total_put_volume / total_call_volume if total_call_volume > 0 else None
        put_call_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else None

        # Get underlying price
        underlying_price = options[0].underlying_price if options else None

        # Calculate 30-day IV (average IV of options expiring in ~30 days)
        iv_30day = None
        thirty_day_options = [o for o in options if o.days_to_expiration and 25 <= o.days_to_expiration <= 35]
        if thirty_day_options:
            ivs = [o.implied_volatility for o in thirty_day_options if o.implied_volatility]
            if ivs:
                iv_30day = sum(ivs) / len(ivs)

        metrics = OptionsMetrics(
            ticker=ticker,
            date=date,
            put_call_ratio_volume=put_call_ratio_volume,
            put_call_ratio_oi=put_call_ratio_oi,
            iv_30day=iv_30day,
            total_call_volume=total_call_volume,
            total_put_volume=total_put_volume,
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            underlying_price=underlying_price
        )

        session.add(metrics)
        session.commit()

        logger.info(f"Calculated options metrics for {ticker} on {date}")
        logger.info(f"  P/C Ratio (Volume): {put_call_ratio_volume:.2f}" if put_call_ratio_volume else "  P/C Ratio (Volume): N/A")
        logger.info(f"  P/C Ratio (OI): {put_call_ratio_oi:.2f}" if put_call_ratio_oi else "  P/C Ratio (OI): N/A")
        logger.info(f"  30-day IV: {iv_30day:.2%}" if iv_30day else "  30-day IV: N/A")

    def fetch_historical_options_metrics(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        frequency: str = "weekly"  # daily, weekly, monthly
    ) -> int:
        """
        Fetch options chain snapshots over a historical period.

        Note: This can be expensive - each snapshot is a full options chain fetch.
        Use 'weekly' or 'monthly' for long time periods.

        Returns:
            Number of snapshots fetched
        """
        # Generate snapshot dates based on frequency
        dates = []
        current = start_date

        if frequency == "daily":
            while current <= end_date:
                if current.weekday() < 5:  # Skip weekends
                    dates.append(current)
                current += timedelta(days=1)

        elif frequency == "weekly":
            while current <= end_date:
                if current.weekday() == 4:  # Fridays
                    dates.append(current)
                current += timedelta(days=1)

        elif frequency == "monthly":
            while current <= end_date:
                # Third Friday of each month (typical expiration)
                if current.weekday() == 4 and 15 <= current.day <= 21:
                    dates.append(current)
                current += timedelta(days=1)

        logger.info(f"Fetching {len(dates)} options chain snapshots for {ticker}")
        logger.warning("Note: Historical options data from yfinance only shows CURRENT chain")
        logger.warning("For true historical options data, need paid data provider (CBOE, OptionMetrics, etc.)")

        # For now, just fetch current chain
        # TODO: Integrate with paid options data provider for historical chains
        count = self.fetch_options_chain(ticker)

        return count if count > 0 else 0

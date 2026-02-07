"""
Historical Data Backfill Script

Exhaustively seeds all signal types with historical data.

This script:
1. Fetches maximum available historical data for each signal type
2. Processes and stores signals in the database
3. Tracks progress and handles errors gracefully
4. Can be run for specific companies or all companies
5. Can be limited to specific signal types

Usage:
    # Backfill all signals for all companies
    python scripts/backfill_signals.py

    # Backfill specific company
    python scripts/backfill_signals.py --company UBER

    # Backfill specific signal types
    python scripts/backfill_signals.py --signals sec_financials,google_trends

    # Backfill with custom date range
    python scripts/backfill_signals.py --start 2020-01-01 --end 2026-02-07

    # Dry run (don't save to database)
    python scripts/backfill_signals.py --dry-run
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from typing import List, Optional
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.company import Company
from src.core.registry import get_processor_registry
from src.models.signal import SignalModel
from src.models.company import CompanyModel
from src.database import init_db


class BackfillManager:
    """Manages historical data backfilling"""

    def __init__(
        self,
        database_url: str,
        dry_run: bool = False,
        batch_size: int = 100
    ):
        self.database_url = database_url
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.registry = get_processor_registry()

        if not dry_run:
            self.engine = create_engine(database_url)
        else:
            self.engine = None
            logger.info("DRY RUN MODE - no data will be saved to database")

    async def backfill_company(
        self,
        company: Company,
        signal_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        Backfill all applicable signals for a company.

        Args:
            company: Company to backfill
            signal_types: Optional list of specific signal types to backfill
            start_date: Start date for historical data
            end_date: End date for historical data
        """
        logger.info(f"=== Backfilling {company.ticker} ===")

        # Default date range: last 2 years
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=730)  # 2 years

        logger.info(f"Date range: {start_date.date()} to {end_date.date()}")

        # Get all applicable processors
        processors_to_run = []
        for signal_type, processor in self.registry._processors.items():
            # Skip if not applicable to company
            if not processor.is_applicable(company):
                continue

            # Skip if specific signal types requested and this isn't one of them
            if signal_types and signal_type not in signal_types:
                continue

            processors_to_run.append((signal_type, processor))

        logger.info(f"Will backfill {len(processors_to_run)} signal types")

        total_signals_created = 0

        # Run each processor
        for signal_type, processor in processors_to_run:
            try:
                logger.info(f"\n▶ Processing {signal_type}...")

                # Fetch historical data
                raw_data = await processor.fetch(company, start_date, end_date)

                if not raw_data or not raw_data.get("company_id"):
                    logger.warning(f"  No data returned for {signal_type}")
                    continue

                # Process into signals
                signals = processor.process(company, raw_data)

                if not signals:
                    logger.warning(f"  No signals generated for {signal_type}")
                    continue

                logger.info(f"  Generated {len(signals)} signal(s)")

                # Save to database
                if not self.dry_run:
                    saved_count = self._save_signals(signals)
                    total_signals_created += saved_count
                    logger.info(f"  ✓ Saved {saved_count} signals to database")
                else:
                    for sig in signals:
                        logger.info(f"    - {sig.signal_type}: {sig.score}/100 @ {sig.timestamp}")
                    total_signals_created += len(signals)

            except Exception as e:
                logger.error(f"  ✗ Error processing {signal_type}: {e}")
                continue

        logger.info(f"\n=== Backfill complete for {company.ticker} ===")
        logger.info(f"Total signals created: {total_signals_created}")

        return total_signals_created

    def _save_signals(self, signals: List) -> int:
        """
        Save signals to database.

        Returns:
            Number of signals saved
        """
        if self.dry_run:
            return 0

        with Session(self.engine) as session:
            saved_count = 0

            for signal in signals:
                try:
                    # Convert Signal dataclass to SQLAlchemy model
                    signal_model = SignalModel(
                        company_id=signal.company_id,
                        signal_type=signal.signal_type,
                        category=signal.category.value,
                        timestamp=signal.timestamp,
                        score=signal.score,
                        confidence=signal.confidence,
                        description=signal.description,
                        raw_value=signal.raw_value,
                        normalized_value=signal.normalized_value,
                        source_name=signal.metadata.source_name if signal.metadata else None,
                        source_url=signal.metadata.source_url if signal.metadata else None,
                    )

                    session.add(signal_model)
                    saved_count += 1

                except Exception as e:
                    logger.warning(f"Error saving signal: {e}")
                    continue

            session.commit()
            return saved_count

    async def backfill_all_companies(
        self,
        signal_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        Backfill all companies in the system.
        """
        # For POC, we have one company (Uber)
        # In production, this would query the database for all companies
        companies = [
            Company(
                id="UBER",
                name="Uber Technologies Inc.",
                ticker="UBER",
                cik="0001543151",
                has_sec_filings=True,
                has_app=True,
            )
        ]

        total_signals = 0

        for company in companies:
            signals_created = await self.backfill_company(
                company=company,
                signal_types=signal_types,
                start_date=start_date,
                end_date=end_date,
            )
            total_signals += signals_created

        logger.info(f"\n=== BACKFILL COMPLETE ===")
        logger.info(f"Total companies processed: {len(companies)}")
        logger.info(f"Total signals created: {total_signals}")

        return total_signals


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Backfill historical signal data")

    parser.add_argument(
        "--company",
        type=str,
        help="Specific company ticker to backfill (e.g., UBER)"
    )

    parser.add_argument(
        "--signals",
        type=str,
        help="Comma-separated list of signal types to backfill (e.g., sec_financials,google_trends)"
    )

    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD). Default: 2 years ago"
    )

    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD). Default: today"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save to database, just show what would be done"
    )

    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/cousin_eddie"),
        help="Database connection URL"
    )

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.start:
        start_date = datetime.fromisoformat(args.start)

    if args.end:
        end_date = datetime.fromisoformat(args.end)

    # Parse signal types
    signal_types = None
    if args.signals:
        signal_types = [s.strip() for s in args.signals.split(",")]

    # Initialize backfill manager
    manager = BackfillManager(
        database_url=args.database_url,
        dry_run=args.dry_run,
    )

    # Initialize database (if not dry run)
    if not args.dry_run:
        logger.info("Initializing database...")
        init_db(args.database_url)

    # Run backfill
    if args.company:
        # Single company
        company = Company(
            id=args.company,
            name=f"{args.company} Inc.",
            ticker=args.company,
            cik="0001543151" if args.company == "UBER" else None,
            has_sec_filings=True,
            has_app=True,
        )

        await manager.backfill_company(
            company=company,
            signal_types=signal_types,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        # All companies
        await manager.backfill_all_companies(
            signal_types=signal_types,
            start_date=start_date,
            end_date=end_date,
        )


if __name__ == "__main__":
    asyncio.run(main())

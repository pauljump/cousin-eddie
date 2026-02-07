"""
Incremental Signal Update Orchestrator

Continuously updates signals by fetching only new data since last update.

This script:
1. Tracks last update timestamp for each (company, signal_type) pair
2. Fetches only new data since last update
3. Processes and stores new signals
4. Updates last_updated tracking
5. Can run as a daemon (continuous updates) or one-time
6. Respects update frequency (hourly, daily, weekly, etc.)

Usage:
    # One-time update (all signals that are due for update)
    python scripts/update_signals.py

    # Continuous daemon mode (runs forever, updating on schedule)
    python scripts/update_signals.py --daemon

    # Update specific company
    python scripts/update_signals.py --company UBER

    # Update specific signal types
    python scripts/update_signals.py --signals twitter_sentiment,job_postings

    # Force update (ignore last_updated, fetch new data anyway)
    python scripts/update_signals.py --force

    # Dry run
    python scripts/update_signals.py --dry-run
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session

from src.core.company import Company
from src.core.registry import get_processor_registry
from src.core.signal_processor import UpdateFrequency
from src.models.signal import Signal as SignalModel
from src.models.company import Company as CompanyModel
from src.database import init_db


class UpdateTracker:
    """Tracks last update timestamp for each signal type"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)

    def get_last_update(self, company_id: str, signal_type: str) -> Optional[datetime]:
        """Get timestamp of last update for a signal type"""
        with Session(self.engine) as session:
            stmt = (
                select(SignalModel.timestamp)
                .where(
                    and_(
                        SignalModel.company_id == company_id,
                        SignalModel.signal_type == signal_type
                    )
                )
                .order_by(SignalModel.timestamp.desc())
                .limit(1)
            )

            result = session.execute(stmt).first()

            if result:
                return result[0]
            else:
                return None

    def save_signals(self, signals: List) -> int:
        """Save new signals to database"""
        with Session(self.engine) as session:
            saved_count = 0

            for signal in signals:
                try:
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


class SignalUpdateOrchestrator:
    """Orchestrates incremental signal updates"""

    # Map update frequency to timedelta
    FREQUENCY_INTERVALS = {
        UpdateFrequency.REALTIME: timedelta(minutes=5),
        UpdateFrequency.HOURLY: timedelta(hours=1),
        UpdateFrequency.DAILY: timedelta(days=1),
        UpdateFrequency.WEEKLY: timedelta(days=7),
        UpdateFrequency.MONTHLY: timedelta(days=30),
        UpdateFrequency.QUARTERLY: timedelta(days=90),
    }

    def __init__(
        self,
        database_url: str,
        dry_run: bool = False,
        force: bool = False,
    ):
        self.database_url = database_url
        self.dry_run = dry_run
        self.force = force
        self.registry = get_processor_registry()
        self.tracker = UpdateTracker(database_url) if not dry_run else None

        if dry_run:
            logger.info("DRY RUN MODE - no data will be saved")

    def should_update(
        self,
        signal_type: str,
        update_frequency: UpdateFrequency,
        last_update: Optional[datetime],
    ) -> bool:
        """
        Determine if a signal type should be updated.

        Returns:
            True if update is due, False otherwise
        """
        if self.force:
            return True

        if last_update is None:
            # Never updated before
            return True

        # Check if enough time has passed
        interval = self.FREQUENCY_INTERVALS.get(update_frequency, timedelta(days=1))
        time_since_last_update = datetime.utcnow() - last_update

        return time_since_last_update >= interval

    async def update_company(
        self,
        company: Company,
        signal_types: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """
        Update all applicable signals for a company.

        Returns:
            Dict mapping signal_type to number of new signals created
        """
        logger.info(f"=== Updating {company.ticker} ===")

        results = {}
        total_signals_created = 0

        # Get all applicable processors
        for signal_type, processor in self.registry._processors.items():
            # Skip if not applicable
            if not processor.is_applicable(company):
                continue

            # Skip if specific signal types requested
            if signal_types and signal_type not in signal_types:
                continue

            try:
                # Check if update is needed
                last_update = None
                if not self.dry_run and self.tracker:
                    last_update = self.tracker.get_last_update(company.id, signal_type)

                update_frequency = processor.metadata.update_frequency

                if not self.should_update(signal_type, update_frequency, last_update):
                    logger.debug(f"⏭ Skipping {signal_type} (not due for update)")
                    continue

                logger.info(f"\n▶ Updating {signal_type}...")

                if last_update:
                    logger.info(f"  Last update: {last_update.strftime('%Y-%m-%d %H:%M')}")
                    start_date = last_update
                else:
                    logger.info(f"  First update (no historical data)")
                    # For first update, fetch last 30 days
                    start_date = datetime.utcnow() - timedelta(days=30)

                end_date = datetime.utcnow()

                # Fetch new data
                raw_data = await processor.fetch(company, start_date, end_date)

                if not raw_data or not raw_data.get("company_id"):
                    logger.warning(f"  No new data for {signal_type}")
                    results[signal_type] = 0
                    continue

                # Process into signals
                signals = processor.process(company, raw_data)

                if not signals:
                    logger.warning(f"  No new signals generated")
                    results[signal_type] = 0
                    continue

                logger.info(f"  Generated {len(signals)} new signal(s)")

                # Save to database
                if not self.dry_run and self.tracker:
                    saved_count = self.tracker.save_signals(signals)
                    logger.info(f"  ✓ Saved {saved_count} signals")
                    results[signal_type] = saved_count
                    total_signals_created += saved_count
                else:
                    for sig in signals:
                        logger.info(f"    - {sig.signal_type}: {sig.score}/100 @ {sig.timestamp}")
                    results[signal_type] = len(signals)
                    total_signals_created += len(signals)

            except Exception as e:
                logger.error(f"  ✗ Error updating {signal_type}: {e}")
                results[signal_type] = 0
                continue

        logger.info(f"\n=== Update complete for {company.ticker} ===")
        logger.info(f"Signal types updated: {len([k for k, v in results.items() if v > 0])}/{len(results)}")
        logger.info(f"Total new signals: {total_signals_created}")

        return results

    async def update_all_companies(
        self,
        signal_types: Optional[List[str]] = None,
    ):
        """Update all companies"""
        # For POC, one company
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
            results = await self.update_company(
                company=company,
                signal_types=signal_types,
            )
            total_signals += sum(results.values())

        logger.info(f"\n=== ALL UPDATES COMPLETE ===")
        logger.info(f"Companies updated: {len(companies)}")
        logger.info(f"Total new signals: {total_signals}")

        return total_signals

    async def run_daemon(
        self,
        signal_types: Optional[List[str]] = None,
        check_interval_seconds: int = 300,  # 5 minutes
    ):
        """
        Run as daemon, continuously checking for updates.

        Args:
            signal_types: Optional signal types to update
            check_interval_seconds: How often to check for updates
        """
        logger.info("=== STARTING DAEMON MODE ===")
        logger.info(f"Check interval: {check_interval_seconds} seconds")

        while True:
            try:
                logger.info(f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Running update cycle...")

                await self.update_all_companies(signal_types=signal_types)

                logger.info(f"Update cycle complete. Sleeping for {check_interval_seconds} seconds...")
                time.sleep(check_interval_seconds)

            except KeyboardInterrupt:
                logger.info("\nDaemon stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                logger.info(f"Retrying in {check_interval_seconds} seconds...")
                time.sleep(check_interval_seconds)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Update signals incrementally")

    parser.add_argument(
        "--company",
        type=str,
        help="Specific company ticker to update (e.g., UBER)"
    )

    parser.add_argument(
        "--signals",
        type=str,
        help="Comma-separated list of signal types to update"
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (continuous updates)"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds for daemon mode (default: 300)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update (ignore last_updated timestamps)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save to database"
    )

    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/cousin_eddie"),
        help="Database connection URL"
    )

    args = parser.parse_args()

    # Parse signal types
    signal_types = None
    if args.signals:
        signal_types = [s.strip() for s in args.signals.split(",")]

    # Initialize orchestrator
    orchestrator = SignalUpdateOrchestrator(
        database_url=args.database_url,
        dry_run=args.dry_run,
        force=args.force,
    )

    # Initialize database (if not dry run)
    if not args.dry_run:
        logger.info("Initializing database...")
        init_db(args.database_url)

    # Run updates
    if args.daemon:
        # Daemon mode
        await orchestrator.run_daemon(
            signal_types=signal_types,
            check_interval_seconds=args.interval,
        )
    elif args.company:
        # Single company
        company = Company(
            id=args.company,
            name=f"{args.company} Inc.",
            ticker=args.company,
            cik="0001543151" if args.company == "UBER" else None,
            has_sec_filings=True,
            has_app=True,
        )

        await orchestrator.update_company(
            company=company,
            signal_types=signal_types,
        )
    else:
        # All companies
        await orchestrator.update_all_companies(
            signal_types=signal_types,
        )


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Ingest signals for a company.

Usage:
    python scripts/ingest_signals.py --company UBER --days 30
    python scripts/ingest_signals.py --all --days 7
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Import registry to auto-register processors
import src.core.registry  # noqa: F401

from src.core.company import get_registry
from src.core.orchestrator import SignalOrchestrator
from src.core.signal_processor import get_processor_registry
from datetime import datetime, timedelta


async def main():
    parser = argparse.ArgumentParser(description="Ingest alternative data signals")
    parser.add_argument(
        "--company",
        type=str,
        help="Company ID to ingest (e.g., UBER)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all registered companies"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of historical data to fetch (default: 30)"
    )
    parser.add_argument(
        "--processors",
        type=str,
        nargs="+",
        help="Specific processors to run (e.g., sec_form_4 job_postings)"
    )
    parser.add_argument(
        "--list-processors",
        action="store_true",
        help="List all available processors and exit"
    )
    parser.add_argument(
        "--list-companies",
        action="store_true",
        help="List all registered companies and exit"
    )

    args = parser.parse_args()

    # List processors
    if args.list_processors:
        registry = get_processor_registry()
        processors = registry.list_all()
        logger.info(f"\nAvailable signal processors ({len(processors)}):\n")
        for p in processors:
            logger.info(f"  {p.metadata.signal_type}")
            logger.info(f"    Category: {p.metadata.category.value}")
            logger.info(f"    Description: {p.metadata.description}")
            logger.info(f"    Source: {p.metadata.data_source}")
            logger.info(f"    Cost: {p.metadata.cost.value}")
            logger.info(f"    Update Frequency: {p.metadata.update_frequency.value}")
            logger.info("")
        return

    # List companies
    if args.list_companies:
        company_registry = get_registry()
        companies = company_registry.list_all()
        logger.info(f"\nRegistered companies ({len(companies)}):\n")
        for c in companies:
            logger.info(f"  {c.id} - {c.name} ({c.ticker})")
            logger.info(f"    Sector: {c.sector}")
            logger.info(f"    Has app: {c.has_app}")
            logger.info(f"    Has SEC filings: {c.has_sec_filings}")
            logger.info("")
        return

    # Validate input
    if not args.company and not args.all:
        parser.error("Must specify either --company or --all")

    # Setup orchestrator
    orchestrator = SignalOrchestrator()
    end = datetime.utcnow()
    start = end - timedelta(days=args.days)

    logger.info("=" * 60)
    logger.info("cousin-eddie Signal Ingestion")
    logger.info("=" * 60)
    logger.info(f"Time range: {start.date()} to {end.date()} ({args.days} days)")

    if args.processors:
        logger.info(f"Processors: {', '.join(args.processors)}")
    else:
        logger.info("Processors: All applicable")

    logger.info("=" * 60)
    logger.info("")

    # Ingest
    if args.all:
        logger.info("Ingesting all companies...")
        results = await orchestrator.ingest_all_companies(
            days_back=args.days,
            processor_types=args.processors
        )

        logger.info("\nResults:")
        for company_id, count in results.items():
            logger.info(f"  {company_id}: {count} signals stored")

    else:
        company_registry = get_registry()
        company = company_registry.get(args.company)

        if not company:
            logger.error(f"Company {args.company} not found in registry")
            logger.info("Available companies:")
            for c in company_registry.list_all():
                logger.info(f"  - {c.id}")
            return

        logger.info(f"Ingesting {company.name} ({company.ticker})...")

        count = await orchestrator.ingest_and_store(
            company,
            start,
            end,
            processor_types=args.processors
        )

        logger.info(f"\n✓ Complete: {count} signals stored for {company.ticker}")

    logger.info("\n" + "=" * 60)
    logger.info("Ingestion complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

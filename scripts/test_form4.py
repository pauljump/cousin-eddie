#!/usr/bin/env python3
"""
Test SEC Form 4 processor on Uber

Usage:
    python scripts/test_form4.py
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.company import UBER
from src.signal_types.regulatory.sec_form4 import SECForm4Processor
from loguru import logger


async def test_form4():
    """Test Form 4 processor"""

    logger.info("Testing SEC Form 4 processor on Uber...")

    # Create processor
    processor = SECForm4Processor()

    # Check if applicable
    is_applicable = processor.is_applicable(UBER)
    logger.info(f"Is applicable to Uber: {is_applicable}")

    if not is_applicable:
        logger.error("Form 4 processor not applicable to Uber")
        return

    # Fetch last 90 days of filings
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    logger.info(f"Fetching Form 4 filings from {start_date.date()} to {end_date.date()}")

    # Run the full pipeline
    signals = await processor.run(UBER, start_date, end_date)

    logger.info(f"Generated {len(signals)} signals")

    # Display signals
    for i, signal in enumerate(signals, 1):
        logger.info(f"\nSignal {i}:")
        logger.info(f"  Type: {signal.signal_type}")
        logger.info(f"  Timestamp: {signal.timestamp}")
        logger.info(f"  Score: {signal.score}")
        logger.info(f"  Confidence: {signal.confidence}")
        logger.info(f"  Description: {signal.description}")
        logger.info(f"  Raw data: {signal.raw_value}")

    logger.info("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(test_form4())

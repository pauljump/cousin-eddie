"""
Test the updated job postings processor with manual count for Uber
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.company import UBER
from src.signal_types.workforce.job_postings import JobPostingsProcessor

async def test_uber_jobs():
    """Test Uber job postings with manual count"""

    processor = JobPostingsProcessor()

    print(f"\n=== Testing Job Postings Processor for {UBER.ticker} ===\n")

    # Fetch data
    print("Fetching job data...")
    start = datetime.utcnow() - timedelta(days=7)
    end = datetime.utcnow()

    raw_data = await processor.fetch(UBER, start, end)

    print(f"\nRaw Data Sources:")
    for source_name, source_data in raw_data.get("sources", {}).items():
        print(f"  {source_name}: {source_data.get('status', 'unknown')}")
        if source_data.get("status") == "success":
            if source_name == "manual":
                print(f"    Job count: {source_data.get('job_count')}")
                print(f"    Last updated: {source_data.get('last_updated')}")
                print(f"    Notes: {source_data.get('notes')}")
            elif source_name == "greenhouse":
                print(f"    Total jobs: {source_data.get('total_jobs')}")

    # Process into signals
    print("\nProcessing signals...")
    signals = processor.process(UBER, raw_data)

    if signals:
        signal = signals[0]
        print(f"\n=== Generated Signal ===")
        print(f"Company: {signal.company_id}")
        print(f"Type: {signal.signal_type}")
        print(f"Score: {signal.score}")
        print(f"Confidence: {signal.confidence:.2f}")
        print(f"Description: {signal.description}")
        print(f"Source: {signal.metadata.source_name}")
        print(f"Processing notes: {signal.metadata.processing_notes}")
        print("\n✓ Signal generated successfully!")
    else:
        print("\nNo signals generated (all sources failed)")

if __name__ == "__main__":
    asyncio.run(test_uber_jobs())

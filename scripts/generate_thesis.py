#!/usr/bin/env python
"""
Generate Investment Thesis for a Company

This script synthesizes all available signals into an actionable investment thesis
using Claude AI.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

# Import after path is set
from src.synthesis.thesis_generator import ThesisGenerator
from src.core.company import get_registry


async def main():
    """Generate investment thesis"""

    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_thesis.py <TICKER>")
        print("\nExample:")
        print("  python scripts/generate_thesis.py UBER")
        print("  python scripts/generate_thesis.py LYFT")
        sys.exit(1)

    ticker = sys.argv[1].upper()

    # Get company from registry
    registry = get_registry()
    company = registry.get(ticker)

    if not company:
        logger.error(f"Company {ticker} not found in registry")
        logger.info("Available companies:")
        for comp in registry.list_all():
            logger.info(f"  - {comp.ticker}: {comp.name}")
        sys.exit(1)

    logger.info(f"Generating investment thesis for {company.name} ({company.ticker})")
    logger.info("=" * 80)

    # Check for Anthropic API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        logger.info("Set it with: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    # Generate thesis
    generator = ThesisGenerator(anthropic_api_key=api_key)

    try:
        thesis = await generator.generate_thesis(company, lookback_days=90)

        if thesis:
            print(thesis)

            # Optionally save to file
            output_dir = project_root / "output" / "theses"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = thesis.generated_at.strftime('%Y%m%d_%H%M%S')
            filename = f"{ticker}_{timestamp}.txt"
            output_path = output_dir / filename

            with open(output_path, 'w') as f:
                f.write(str(thesis))

            logger.success(f"Thesis saved to: {output_path}")

        else:
            logger.error(f"Could not generate thesis for {ticker}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error generating thesis: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

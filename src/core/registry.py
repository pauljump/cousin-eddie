"""
Registry initialization - register all signal processors.

Import this module to register all available signal processors.
"""

from loguru import logger

from .signal_processor import get_processor_registry

# Import all signal processors
from ..signal_types.regulatory.sec_form4 import SECForm4Processor
from ..signal_types.workforce.job_postings import JobPostingsProcessor
from ..signal_types.web_digital.app_store_ratings import AppStoreRatingsProcessor
from ..signal_types.web_digital.google_trends import GoogleTrendsProcessor
from ..signal_types.alternative.reddit_sentiment import RedditSentimentProcessor


def register_all_processors():
    """Register all available signal processors"""

    registry = get_processor_registry()

    processors = [
        SECForm4Processor(),
        JobPostingsProcessor(),
        AppStoreRatingsProcessor(),
        GoogleTrendsProcessor(),
        RedditSentimentProcessor(),
    ]

    for processor in processors:
        registry.register(processor)
        logger.info(f"Registered processor: {processor.metadata.signal_type}")

    logger.info(f"✓ Registered {len(processors)} signal processors")


# Auto-register on import
register_all_processors()

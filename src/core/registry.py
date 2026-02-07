"""
Registry initialization - register all signal processors.

Import this module to register all available signal processors.
"""

from loguru import logger

from .signal_processor import get_processor_registry

# Import all signal processors
from ..signal_types.regulatory.sec_form4 import SECForm4Processor
from ..signal_types.regulatory.sec_financials import SECFinancialsProcessor
from ..signal_types.regulatory.sec_mda import SECMDAProcessor
from ..signal_types.regulatory.sec_8k import SEC8KProcessor
from ..signal_types.regulatory.sec_risk_factors import SECRiskFactorsProcessor
from ..signal_types.regulatory.sec_13f import SEC13FProcessor
from ..signal_types.workforce.job_postings import JobPostingsProcessor
from ..signal_types.workforce.glassdoor_reviews import GlassdoorReviewsProcessor
from ..signal_types.workforce.linkedin_employee_growth import LinkedInEmployeeGrowthProcessor
from ..signal_types.web_digital.app_store_ratings import AppStoreRatingsProcessor
from ..signal_types.web_digital.google_trends import GoogleTrendsProcessor
from ..signal_types.web_digital.play_store_ratings import PlayStoreRatingsProcessor
from ..signal_types.web_digital.website_traffic import WebsiteTrafficProcessor
from ..signal_types.alternative.reddit_sentiment import RedditSentimentProcessor
from ..signal_types.alternative.news_sentiment import NewsSentimentProcessor
from ..signal_types.alternative.earnings_call_transcripts import EarningsCallTranscriptProcessor
from ..signal_types.alternative.patent_filings import PatentFilingsProcessor
from ..signal_types.alternative.twitter_sentiment import TwitterSentimentProcessor
from ..signal_types.alternative.github_activity import GitHubActivityProcessor
from ..signal_types.alternative.customer_reviews import CustomerReviewsProcessor


def register_all_processors():
    """Register all available signal processors"""

    registry = get_processor_registry()

    processors = [
        SECForm4Processor(),
        SECFinancialsProcessor(),
        SECMDAProcessor(),
        SEC8KProcessor(),
        SECRiskFactorsProcessor(),
        SEC13FProcessor(),
        JobPostingsProcessor(),
        GlassdoorReviewsProcessor(),
        LinkedInEmployeeGrowthProcessor(),
        AppStoreRatingsProcessor(),
        PlayStoreRatingsProcessor(),
        GoogleTrendsProcessor(),
        WebsiteTrafficProcessor(),
        NewsSentimentProcessor(),
        EarningsCallTranscriptProcessor(),
        PatentFilingsProcessor(),
        TwitterSentimentProcessor(),
        GitHubActivityProcessor(),
        CustomerReviewsProcessor(),
        RedditSentimentProcessor(),
    ]

    for processor in processors:
        registry.register(processor)
        logger.info(f"Registered processor: {processor.metadata.signal_type}")

    logger.info(f"✓ Registered {len(processors)} signal processors")


# Auto-register on import
register_all_processors()

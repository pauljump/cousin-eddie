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
from ..signal_types.regulatory.sec_comment_letters import SECCommentLettersProcessor
from ..signal_types.regulatory.sec_footnote_analysis import SECFootnoteAnalysisProcessor
from ..signal_types.workforce.job_postings import JobPostingsProcessor
from ..signal_types.workforce.glassdoor_reviews import GlassdoorReviewsProcessor
from ..signal_types.workforce.linkedin_employee_growth import LinkedInEmployeeGrowthProcessor
from ..signal_types.web_digital.app_store_ratings import AppStoreRatingsProcessor
from ..signal_types.web_digital.google_trends import GoogleTrendsProcessor
from ..signal_types.web_digital.play_store_ratings import PlayStoreRatingsProcessor
from ..signal_types.web_digital.website_traffic import WebsiteTrafficProcessor
from ..signal_types.web_digital.app_download_rankings import AppDownloadRankingsProcessor
from ..signal_types.alternative.reddit_sentiment import RedditSentimentProcessor
from ..signal_types.alternative.news_sentiment import NewsSentimentProcessor
from ..signal_types.alternative.earnings_call_transcripts import EarningsCallTranscriptProcessor
from ..signal_types.alternative.earnings_call_qa_tone import EarningsCallQAToneProcessor
from ..signal_types.alternative.patent_filings import PatentFilingsProcessor
from ..signal_types.alternative.twitter_sentiment import TwitterSentimentProcessor
from ..signal_types.alternative.github_activity import GitHubActivityProcessor
from ..signal_types.alternative.customer_reviews import CustomerReviewsProcessor
from ..signal_types.alternative.social_media_followers import SocialMediaFollowersProcessor
from ..signal_types.alternative.wikipedia_pageviews import WikipediaPageviewsProcessor
from ..signal_types.alternative.youtube_metrics import YouTubeMetricsProcessor
from ..signal_types.alternative.pricing_intelligence import PricingIntelligenceProcessor
from ..signal_types.alternative.credit_card_transactions import CreditCardTransactionsProcessor
from ..signal_types.alternative.stackoverflow_activity import StackOverflowActivityProcessor
from ..signal_types.alternative.niche_community_sentiment import NicheCommunitySentimentProcessor
from ..signal_types.alternative.domain_registrations import DomainRegistrationProcessor
from ..signal_types.alternative.website_changes import WebsiteChangeProcessor
from ..signal_types.alternative.clinical_trials import ClinicalTrialsProcessor
from ..signal_types.alternative.marketplace_activity import MarketplaceActivityProcessor
from ..signal_types.alternative.academic_research import AcademicResearchProcessor
from ..signal_types.alternative.government_permits import GovernmentPermitsProcessor
from ..signal_types.alternative.import_export_data import ImportExportProcessor
from ..signal_types.alternative.foot_traffic import FootTrafficProcessor
from ..signal_types.alternative.satellite_imagery import SatelliteImageryProcessor


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
        SECCommentLettersProcessor(),
        SECFootnoteAnalysisProcessor(),
        JobPostingsProcessor(),
        GlassdoorReviewsProcessor(),
        LinkedInEmployeeGrowthProcessor(),
        AppStoreRatingsProcessor(),
        PlayStoreRatingsProcessor(),
        GoogleTrendsProcessor(),
        WebsiteTrafficProcessor(),
        AppDownloadRankingsProcessor(),
        NewsSentimentProcessor(),
        EarningsCallTranscriptProcessor(),
        EarningsCallQAToneProcessor(),
        PatentFilingsProcessor(),
        TwitterSentimentProcessor(),
        GitHubActivityProcessor(),
        CustomerReviewsProcessor(),
        SocialMediaFollowersProcessor(),
        WikipediaPageviewsProcessor(),
        YouTubeMetricsProcessor(),
        PricingIntelligenceProcessor(),
        CreditCardTransactionsProcessor(),
        StackOverflowActivityProcessor(),
        RedditSentimentProcessor(),
        NicheCommunitySentimentProcessor(),
        DomainRegistrationProcessor(),
        WebsiteChangeProcessor(),
        ClinicalTrialsProcessor(),
        MarketplaceActivityProcessor(),
        AcademicResearchProcessor(),
        GovernmentPermitsProcessor(),
        ImportExportProcessor(),
        FootTrafficProcessor(),
        SatelliteImageryProcessor(),
    ]

    for processor in processors:
        registry.register(processor)
        logger.info(f"Registered processor: {processor.metadata.signal_type}")

    logger.info(f"✓ Registered {len(processors)} signal processors")


# Auto-register on import
register_all_processors()

"""
Website Traffic Signal Processor

Tracks website visitor metrics as a proxy for business momentum.

Why website traffic matters:
- Traffic growth = brand interest and demand
- Traffic decline = losing relevance
- Traffic spikes = viral moments, news events
- E-commerce: traffic → revenue
- SaaS: traffic → signups → revenue

Key Metrics:
- Monthly visits
- Unique visitors
- Bounce rate (engagement)
- Time on site (engagement quality)
- Pages per visit
- Traffic sources (direct, search, social, referral)
- Geographic breakdown
- Mobile vs desktop ratio

Signals:
- Traffic growing >10% MoM = bullish
- Traffic flat or declining = bearish
- High bounce rate = poor product-market fit
- Increasing direct traffic = strong brand
- Rising mobile traffic = mobile-first success

Data Sources:
1. SimilarWeb API (paid, but has free tier)
2. Alexa (deprecated, RIP)
3. Google Analytics (requires access)
4. Third-party estimates (SEMrush, Ahrefs)

Update Frequency: Monthly (data lags ~1 month)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json

from loguru import logger

from ...core.signal_processor import (
    SignalProcessor,
    SignalProcessorMetadata,
    UpdateFrequency,
    DataCost,
    Difficulty,
)
from ...core.signal import Signal, SignalCategory, SignalMetadata
from ...core.company import Company


class WebsiteTrafficProcessor(SignalProcessor):
    """Track website traffic metrics"""

    def __init__(self, similarweb_api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            similarweb_api_key: SimilarWeb API key
                               Get from: https://account.similarweb.com/
        """
        self.api_key = similarweb_api_key

        # Map company IDs to their primary websites
        self.website_mappings = {
            "UBER": "uber.com",
            "LYFT": "lyft.com",
            "ABNB": "airbnb.com",
            "GOOGL": "google.com",
            "AMZN": "amazon.com",
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="website_traffic",
            category=SignalCategory.WEB_DIGITAL,
            description="Website traffic and engagement metrics - demand proxy",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="SimilarWeb",
            cost=DataCost.PAID,
            difficulty=Difficulty.MEDIUM,
            tags=["website", "traffic", "engagement", "web_analytics"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with significant web presence"""
        return company.id in self.website_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch website traffic data.

        Uses SimilarWeb API or falls back to sample data.
        """
        if company.id not in self.website_mappings:
            return {}

        if not self.api_key:
            logger.warning("No SimilarWeb API key - using sample data")
            return self._get_sample_data(company)

        # In production, call SimilarWeb API here
        # For now, use sample data
        logger.warning("SimilarWeb API not implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process website traffic data into signals.

        Analyzes:
        1. Traffic growth (MoM change)
        2. Engagement metrics (bounce rate, time on site)
        3. Traffic quality (sources, geographic)
        """
        traffic_data = raw_data.get("traffic", {})

        if not traffic_data:
            return []

        monthly_visits = traffic_data.get("monthly_visits", 0)
        previous_visits = traffic_data.get("previous_month_visits", 0)
        bounce_rate = traffic_data.get("bounce_rate_pct", 50)
        avg_visit_duration = traffic_data.get("avg_visit_duration_seconds", 0)
        pages_per_visit = traffic_data.get("pages_per_visit", 0)

        # Calculate MoM growth
        if previous_visits > 0:
            growth_rate = ((monthly_visits - previous_visits) / previous_visits) * 100
        else:
            growth_rate = 0

        # Calculate score based on growth and engagement
        # Growth component
        if growth_rate > 10:
            growth_score = min(60, 40 + growth_rate * 2)
        elif growth_rate > 0:
            growth_score = growth_rate * 4
        elif growth_rate > -5:
            growth_score = growth_rate * 4
        else:
            growth_score = max(-60, -40 + growth_rate * 2)

        # Engagement component
        # Good engagement: bounce rate <40%, >3 min visit, >3 pages
        engagement_score = 0

        if bounce_rate < 40:
            engagement_score += 15
        elif bounce_rate > 60:
            engagement_score -= 15

        if avg_visit_duration > 180:  # >3 minutes
            engagement_score += 15
        elif avg_visit_duration < 60:  # <1 minute
            engagement_score -= 15

        if pages_per_visit > 3:
            engagement_score += 10

        # Total score
        score = int(growth_score + engagement_score)
        score = max(-100, min(100, score))

        # Confidence based on data recency
        confidence = 0.70  # Medium confidence (estimates)

        # Build description
        description = f"Website: {monthly_visits:,} monthly visits ({growth_rate:+.1f}% MoM)"
        description += f" | Bounce: {bounce_rate:.0f}%"
        description += f" | Avg visit: {avg_visit_duration//60:.0f}m{avg_visit_duration%60:.0f}s"

        if pages_per_visit > 0:
            description += f" | {pages_per_visit:.1f} pages/visit"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value=traffic_data,
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://www.similarweb.com/website/{self.website_mappings.get(company.id)}",
                source_name="SimilarWeb",
                processing_notes=f"{growth_rate:+.1f}% MoM growth",
                raw_data_hash=hashlib.md5(
                    json.dumps(traffic_data, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["website", "traffic", "engagement"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """
        Return sample website traffic data.
        """
        if company.ticker == "UBER":
            sample_traffic = {
                "monthly_visits": 145000000,  # 145M visits/month
                "previous_month_visits": 138000000,
                "bounce_rate_pct": 42.5,
                "avg_visit_duration_seconds": 245,  # ~4 minutes
                "pages_per_visit": 4.2,
                "traffic_sources": {
                    "direct": 35.2,
                    "search": 28.5,
                    "social": 15.3,
                    "referrals": 12.8,
                    "other": 8.2,
                },
                "top_countries": [
                    {"country": "United States", "share": 28.5},
                    {"country": "India", "share": 12.3},
                    {"country": "Brazil", "share": 8.7},
                ],
                "mobile_vs_desktop": {
                    "mobile": 72.5,
                    "desktop": 27.5,
                },
            }
        else:
            sample_traffic = {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "traffic": sample_traffic,
            "timestamp": datetime.utcnow(),
        }

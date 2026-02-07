"""
Customer Reviews Signal Processor

Aggregates customer review data from multiple platforms (Yelp, Trustpilot, BBB, Google).

Why customer reviews matter:
- Direct feedback on product/service quality
- Leading indicator of customer satisfaction → retention → revenue
- Negative review spikes = product issues, service problems
- Rising ratings = improving product-market fit
- Review volume = brand awareness and engagement

Key Metrics:
- Average rating (1-5 stars across platforms)
- Review volume (new reviews per month)
- Sentiment trend (improving vs declining)
- Response rate (company engagement)
- Common complaints (product issues)
- Platform-specific ratings

Signals:
- Rating improving = product getting better (bullish)
- Rating declining = quality issues (bearish)
- Volume spike + negative reviews = crisis
- High ratings + high volume = strong brand
- Low response rate = poor customer service

Platforms:
- Yelp (restaurants, local services)
- Trustpilot (e-commerce, SaaS)
- Better Business Bureau (overall reputation)
- Google Reviews (all businesses)
- App Store / Play Store (mobile apps - covered separately)

Data Sources:
1. Yelp Fusion API (free, 5000 calls/day)
2. Trustpilot API (requires partnership)
3. Google Places API (paid)
4. Web scraping (rate limited)

Update Frequency: Weekly
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


class CustomerReviewsProcessor(SignalProcessor):
    """Aggregate customer reviews from multiple platforms"""

    def __init__(self, yelp_api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            yelp_api_key: Yelp Fusion API key
                         Get from: https://www.yelp.com/developers
        """
        self.yelp_api_key = yelp_api_key

        # Map company IDs to review platform identifiers
        self.review_mappings = {
            "UBER": {
                "yelp_alias": "uber-san-francisco",
                "trustpilot_domain": "uber.com",
                "google_place_id": "ChIJxZZwR28VkFQRFHnXMyj-XRE",
            },
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="customer_reviews",
            category=SignalCategory.ALTERNATIVE,
            description="Customer review aggregation - product/service quality tracking",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="Yelp, Trustpilot, Google Reviews",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["reviews", "customer_sentiment", "quality", "reputation"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to B2C companies with customer reviews"""
        return company.id in self.review_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch customer reviews from multiple platforms.

        Aggregates data from:
        1. Yelp (if applicable)
        2. Trustpilot (if applicable)
        3. Google Reviews (if applicable)

        For POC, uses sample data.
        """
        if company.id not in self.review_mappings:
            return {}

        # In production, fetch from each platform's API
        logger.warning("Review APIs not configured - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process customer review data into signals.

        Generates:
        1. Overall customer satisfaction signal
        2. Platform-specific signals (if applicable)
        3. Trend signal (improving vs declining)
        """
        platforms = raw_data.get("platforms", {})

        if not platforms:
            return []

        signals = []

        # Calculate weighted average across platforms
        total_rating_sum = 0
        total_reviews = 0
        platform_scores = []

        for platform_name, data in platforms.items():
            rating = data.get("average_rating", 0)
            review_count = data.get("review_count", 0)

            if rating > 0 and review_count > 0:
                # Weight by review count (more reviews = more weight)
                total_rating_sum += rating * review_count
                total_reviews += review_count

                # Convert platform rating to score
                platform_score = int((rating - 3.0) * 40)
                platform_score = max(-100, min(100, platform_score))

                platform_scores.append({
                    "platform": platform_name,
                    "rating": rating,
                    "score": platform_score,
                    "review_count": review_count,
                })

        if total_reviews == 0:
            return []

        # Weighted average rating
        avg_rating = total_rating_sum / total_reviews

        # Convert to -100 to +100 score
        # 5.0 = +100, 4.0 = +60, 3.0 = +20, 2.0 = -20, 1.0 = -60
        overall_score = int((avg_rating - 3.0) * 40)
        overall_score = max(-100, min(100, overall_score))

        # Check for trend (if historical data available)
        previous_rating = raw_data.get("previous_period_rating", 0)
        trend = "stable"
        trend_score_adjustment = 0

        if previous_rating > 0:
            rating_change = avg_rating - previous_rating

            if rating_change > 0.1:
                trend = "improving"
                trend_score_adjustment = 10
            elif rating_change < -0.1:
                trend = "declining"
                trend_score_adjustment = -10

        overall_score += trend_score_adjustment
        overall_score = max(-100, min(100, overall_score))

        # Confidence based on review volume
        if total_reviews > 10000:
            confidence = 0.85
        elif total_reviews > 1000:
            confidence = 0.75
        elif total_reviews > 100:
            confidence = 0.65
        else:
            confidence = 0.55

        # Build description
        description = f"Customer reviews: {avg_rating:.2f}/5.0 stars from {total_reviews:,} reviews"

        if trend == "improving":
            description += " | 📈 Rating improving"
        elif trend == "declining":
            description += " | 📉 Rating declining"

        # Add platform breakdown
        platform_names = [p["platform"] for p in platform_scores]
        if len(platform_names) > 1:
            description += f" (across {', '.join(platform_names)})"

        # Overall signal
        overall_signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "average_rating": avg_rating,
                "total_reviews": total_reviews,
                "platforms": platform_scores,
                "trend": trend,
            },
            normalized_value=overall_score / 100.0,
            score=overall_score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://www.yelp.com",  # Primary source
                source_name="Customer Reviews (Aggregated)",
                processing_notes=f"{avg_rating:.2f}/5.0 from {total_reviews:,} reviews ({trend})",
                raw_data_hash=hashlib.md5(
                    json.dumps(platforms, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["reviews", "customer_satisfaction", trend],
        )

        signals.append(overall_signal)

        return signals

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """
        Return sample customer review data.
        """
        if company.ticker == "UBER":
            sample_platforms = {
                "yelp": {
                    "average_rating": 3.5,
                    "review_count": 8500,
                    "recent_reviews": 250,  # Last 30 days
                },
                "trustpilot": {
                    "average_rating": 3.8,
                    "review_count": 15200,
                    "recent_reviews": 420,
                },
                "google": {
                    "average_rating": 4.1,
                    "review_count": 45000,
                    "recent_reviews": 1200,
                },
            }
        else:
            sample_platforms = {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "platforms": sample_platforms,
            "previous_period_rating": 3.7,  # Improving trend
            "timestamp": datetime.utcnow(),
        }

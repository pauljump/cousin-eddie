"""
Glassdoor Employee Reviews Signal Processor

Tracks employee sentiment as a leading indicator of company health.

Employee reviews are a valuable alternative data source because:
- Unhappy employees = operational issues, culture problems
- Declining ratings = red flag (turnover, morale issues)
- Low CEO approval = leadership crisis
- High ratings = talent retention, strong culture

Key Metrics:
- Overall company rating (1-5 stars)
- CEO approval % (0-100%)
- Would recommend to friend % (0-100%)
- Work-life balance rating
- Culture & values rating
- Career opportunities rating
- Compensation & benefits rating
- Senior management rating

Scoring:
- 4.5-5.0 stars = very positive (+80 to +100)
- 4.0-4.5 stars = positive (+40 to +80)
- 3.5-4.0 stars = neutral (+0 to +40)
- 3.0-3.5 stars = concerning (-20 to 0)
- <3.0 stars = negative (-60 to -20)

Rating drops >0.2 stars = major red flag
CEO approval <50% = leadership crisis

Data Source: Glassdoor (scraped - no public API)
Update Frequency: Weekly (reviews are constantly added)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json
import re

import httpx
from bs4 import BeautifulSoup
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


class GlassdoorReviewsProcessor(SignalProcessor):
    """Process Glassdoor employee reviews and ratings"""

    def __init__(self):
        """
        Initialize processor.

        Note: Glassdoor doesn't have a public API.
        This processor uses web scraping or sample data.
        """
        # Map company IDs to Glassdoor company IDs
        # Format: {company_id: glassdoor_company_name}
        self.glassdoor_mappings = {
            "UBER": "uber",
            "LYFT": "lyft",
            "ABNB": "airbnb",
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="glassdoor_reviews",
            category=SignalCategory.WORKFORCE,
            description="Employee sentiment and company ratings from Glassdoor",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="Glassdoor",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["glassdoor", "employee_sentiment", "culture", "workforce"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with Glassdoor presence"""
        return company.id in self.glassdoor_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Glassdoor ratings and reviews.

        Note: Glassdoor actively blocks scrapers. For POC, we use sample data.
        Production implementation would use:
        - Paid Glassdoor API (if available)
        - Third-party data provider
        - Manual data entry
        """
        if company.id not in self.glassdoor_mappings:
            return {}

        # For POC, use sample data
        # Production: implement scraping with proxy rotation or use paid API
        logger.warning("Glassdoor scraping not implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process Glassdoor data into signals.

        Generates multiple signals:
        1. Overall company rating
        2. CEO approval rating
        3. Sentiment trend (if historical data available)
        """
        ratings = raw_data.get("ratings", {})

        if not ratings:
            return []

        signals = []

        # Overall company rating signal
        overall_rating = ratings.get("overall_rating", 0)  # 1-5 scale
        ceo_approval = ratings.get("ceo_approval_pct", 0)  # 0-100
        recommend_pct = ratings.get("recommend_to_friend_pct", 0)  # 0-100
        review_count = ratings.get("review_count", 0)

        # Convert 5-star rating to -100 to +100 score
        # 5.0 = +100, 4.0 = +60, 3.0 = +20, 2.0 = -20, 1.0 = -60
        overall_score = int((overall_rating - 3.0) * 40)
        overall_score = max(-100, min(100, overall_score))

        # Confidence based on review volume
        if review_count > 10000:
            confidence = 0.85
        elif review_count > 1000:
            confidence = 0.75
        elif review_count > 100:
            confidence = 0.65
        else:
            confidence = 0.50

        # Build description
        description = f"Glassdoor: {overall_rating:.1f}/5 stars from {review_count:,} reviews"

        # Add CEO approval if available
        if ceo_approval > 0:
            description += f" | CEO approval: {ceo_approval:.0f}%"

        # Add recommendation rate
        if recommend_pct > 0:
            description += f" | Would recommend: {recommend_pct:.0f}%"

        # Flag concerning metrics
        if ceo_approval < 50:
            description += " ⚠ Low CEO approval"
        if overall_rating < 3.0:
            description += " ⚠ Poor ratings"

        overall_signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value=ratings,
            normalized_value=overall_score / 100.0,
            score=overall_score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://www.glassdoor.com/Overview/Working-at-{self.glassdoor_mappings[company.id]}.htm",
                source_name="Glassdoor",
                processing_notes=f"{review_count:,} employee reviews",
                raw_data_hash=hashlib.md5(
                    json.dumps(ratings, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["glassdoor", "employee_sentiment"],
        )

        signals.append(overall_signal)

        # CEO approval signal (if available and significant)
        if ceo_approval > 0:
            # Convert CEO approval (0-100%) to -100 to +100 score
            # 90%+ = +80 to +100
            # 70-90% = +40 to +80
            # 50-70% = 0 to +40
            # 30-50% = -40 to 0
            # <30% = -60 to -40
            ceo_score = int((ceo_approval - 50) * 2)
            ceo_score = max(-100, min(100, ceo_score))

            ceo_signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_ceo",
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={"ceo_approval_pct": ceo_approval},
                normalized_value=ceo_score / 100.0,
                score=ceo_score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"https://www.glassdoor.com/Overview/Working-at-{self.glassdoor_mappings[company.id]}.htm",
                    source_name="Glassdoor (CEO Approval)",
                    processing_notes="CEO approval rating from employee reviews",
                    raw_data_hash=hashlib.md5(
                        json.dumps({"ceo_approval": ceo_approval}, sort_keys=True).encode()
                    ).hexdigest(),
                ),
                description=f"CEO approval: {ceo_approval:.0f}% ({review_count:,} reviews)",
                tags=["glassdoor", "ceo_approval", "leadership"],
            )

            signals.append(ceo_signal)

        # Work-life balance signal (sub-rating)
        wlb_rating = ratings.get("work_life_balance", 0)
        if wlb_rating > 0:
            wlb_score = int((wlb_rating - 3.0) * 40)
            wlb_score = max(-100, min(100, wlb_score))

            wlb_signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_work_life_balance",
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={"work_life_balance": wlb_rating},
                normalized_value=wlb_score / 100.0,
                score=wlb_score,
                confidence=confidence * 0.9,  # Slightly lower confidence for sub-ratings
                metadata=SignalMetadata(
                    source_url=f"https://www.glassdoor.com/Overview/Working-at-{self.glassdoor_mappings[company.id]}.htm",
                    source_name="Glassdoor (Work-Life Balance)",
                    processing_notes="Work-life balance rating from employee reviews",
                    raw_data_hash=hashlib.md5(
                        json.dumps({"wlb": wlb_rating}, sort_keys=True).encode()
                    ).hexdigest(),
                ),
                description=f"Work-life balance: {wlb_rating:.1f}/5 stars",
                tags=["glassdoor", "work_life_balance"],
            )

            signals.append(wlb_signal)

        return signals

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """
        Return sample Glassdoor data.

        In production, this would be replaced with actual scraping or API calls.
        """
        if company.ticker == "UBER":
            # Sample data based on actual Glassdoor trends
            sample_ratings = {
                "overall_rating": 3.7,
                "ceo_approval_pct": 71,
                "recommend_to_friend_pct": 58,
                "work_life_balance": 3.4,
                "culture_values": 3.6,
                "career_opportunities": 3.8,
                "compensation_benefits": 3.9,
                "senior_management": 3.3,
                "review_count": 12500,
                "last_updated": datetime.utcnow().isoformat(),
            }
        else:
            sample_ratings = {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "ratings": sample_ratings,
            "timestamp": datetime.utcnow(),
        }

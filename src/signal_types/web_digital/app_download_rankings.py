"""
Mobile App Download Rankings Signal Processor

Tracks app store ranking positions and download velocity estimates.

Why download rankings matter:
- Rank position = download velocity (higher rank = more downloads)
- Rank improvements = growing user acquisition
- Category rankings reveal competitive positioning
- Download velocity → revenue (especially for mobile-first companies)
- Leading indicator of user growth before quarterly reports

Key Metrics:
- Overall app ranking (1-1000+)
- Category ranking (Top Charts position)
- Download velocity estimate
- Rank changes (day-over-day, week-over-week)
- Competitor positioning
- Geographic rankings (US, international)

Signals:
- Rank improving = download growth (bullish)
- Rank declining = losing traction (bearish)
- Breaking into Top 10/Top 100 = major milestone
- Falling out of Top Charts = red flag
- Competitor rank changes = market share shifts

Rankings:
- #1-10: Millions of downloads/week
- #11-50: Hundreds of thousands/week
- #51-100: Tens of thousands/week
- #101-500: Thousands/week
- #501+: Declining relevance

Data Sources:
1. App Annie (paid, most comprehensive)
2. Sensor Tower (paid)
3. Data.ai (paid)
4. App Figures (paid, cheaper)
5. Public app store scraping (free, rate limited)

Update Frequency: Daily (rankings change daily)
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


class AppDownloadRankingsProcessor(SignalProcessor):
    """Track app store download rankings"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            api_key: App Annie / Sensor Tower API key
        """
        self.api_key = api_key

        # Map companies to their app store IDs
        self.app_mappings = {
            "UBER": {
                "ios_apps": [
                    {"name": "Uber", "id": "368677368", "category": "Travel"},
                    {"name": "Uber Eats", "id": "1058959277", "category": "Food & Drink"},
                ],
                "android_apps": [
                    {"name": "Uber", "package": "com.ubercab", "category": "maps_and_navigation"},
                    {"name": "Uber Eats", "package": "com.ubercab.eats", "category": "food_and_drink"},
                ],
            },
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="app_download_rankings",
            category=SignalCategory.WEB_DIGITAL,
            description="App store download rankings - user acquisition velocity tracking",
            update_frequency=UpdateFrequency.DAILY,
            data_source="App Annie / Sensor Tower",
            cost=DataCost.PAID,
            difficulty=Difficulty.MEDIUM,
            tags=["app_store", "downloads", "rankings", "user_acquisition"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with mobile apps"""
        return company.has_app and company.id in self.app_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch app store ranking data.

        For POC, uses sample data.
        Production would call App Annie/Sensor Tower API.
        """
        if company.id not in self.app_mappings:
            return {}

        # In production, call API here
        logger.warning("App ranking API not configured - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process app ranking data into signals.

        Generates:
        1. Per-app ranking signals (iOS + Android)
        2. Aggregate ranking signal
        3. Rank change signals (trending)
        """
        apps = raw_data.get("apps", [])

        if not apps:
            return []

        signals = []

        for app_data in apps:
            app_name = app_data.get("app_name")
            platform = app_data.get("platform")
            current_rank = app_data.get("current_overall_rank", 0)
            previous_rank = app_data.get("previous_overall_rank", 0)
            category_rank = app_data.get("category_rank", 0)
            category = app_data.get("category", "")

            if current_rank == 0:
                continue

            # Calculate rank change
            if previous_rank > 0:
                rank_change = previous_rank - current_rank  # Positive = improving
            else:
                rank_change = 0

            # Convert rank to score
            # #1-10 = +90 to +100 (top tier)
            # #11-50 = +70 to +90 (strong)
            # #51-100 = +50 to +70 (good)
            # #101-200 = +30 to +50 (moderate)
            # #201-500 = +10 to +30 (weak)
            # #501+ = -20 to +10 (poor)

            if current_rank <= 10:
                score = 100 - current_rank
            elif current_rank <= 50:
                score = 90 - ((current_rank - 10) / 40) * 20
            elif current_rank <= 100:
                score = 70 - ((current_rank - 50) / 50) * 20
            elif current_rank <= 200:
                score = 50 - ((current_rank - 100) / 100) * 20
            elif current_rank <= 500:
                score = 30 - ((current_rank - 200) / 300) * 20
            else:
                score = max(-20, 10 - ((current_rank - 500) / 500) * 30)

            # Bonus for rank improvement
            if rank_change > 0:
                improvement_bonus = min(20, rank_change / 5)
                score += improvement_bonus
            elif rank_change < 0:
                decline_penalty = max(-20, rank_change / 5)
                score += decline_penalty

            score = int(max(-100, min(100, score)))

            # Confidence based on data recency
            confidence = 0.80  # Rankings are reliable data

            # Build description
            description = f"{app_name} ({platform}): #{current_rank} overall"

            if category_rank > 0:
                description += f", #{category_rank} in {category}"

            if rank_change > 0:
                description += f" | ↑ Up {rank_change} places"
            elif rank_change < 0:
                description += f" | ↓ Down {abs(rank_change)} places"

            # Milestone flags
            if current_rank <= 10 and previous_rank > 10:
                description += " 🏆 Entered Top 10!"
            elif current_rank <= 100 and previous_rank > 100:
                description += " ⭐ Entered Top 100!"

            signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_{platform}",
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value=app_data,
                normalized_value=score / 100.0,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"https://www.appannie.com",
                    source_name=f"App Annie ({platform})",
                    processing_notes=f"Rank #{current_rank}, change: {rank_change:+d}",
                    raw_data_hash=hashlib.md5(
                        json.dumps(app_data, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["app_rankings", platform, app_name.lower().replace(" ", "_")],
            )

            signals.append(signal)

        return signals

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample app ranking data"""
        if company.ticker == "UBER":
            sample_apps = [
                {
                    "app_name": "Uber",
                    "platform": "ios",
                    "current_overall_rank": 42,
                    "previous_overall_rank": 48,
                    "category_rank": 3,
                    "category": "Travel",
                    "estimated_daily_downloads": 125000,
                },
                {
                    "app_name": "Uber Eats",
                    "platform": "ios",
                    "current_overall_rank": 78,
                    "previous_overall_rank": 72,
                    "category_rank": 5,
                    "category": "Food & Drink",
                    "estimated_daily_downloads": 85000,
                },
                {
                    "app_name": "Uber",
                    "platform": "android",
                    "current_overall_rank": 35,
                    "previous_overall_rank": 40,
                    "category_rank": 2,
                    "category": "Maps & Navigation",
                    "estimated_daily_downloads": 180000,
                },
                {
                    "app_name": "Uber Eats",
                    "platform": "android",
                    "current_overall_rank": 65,
                    "previous_overall_rank": 68,
                    "category_rank": 4,
                    "category": "Food & Drink",
                    "estimated_daily_downloads": 110000,
                },
            ]
        else:
            sample_apps = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "apps": sample_apps,
            "timestamp": datetime.utcnow(),
        }

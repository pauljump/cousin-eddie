"""
Google Play Store Ratings Signal Processor

Tracks Android app ratings to complement iOS App Store data.

For companies with mobile apps, app ratings are a leading indicator of:
- Product quality
- User satisfaction
- Brand sentiment
- Version release issues

Scoring:
- 4.5-5.0 stars = very positive (+80 to +100)
- 4.0-4.5 stars = positive (+40 to +80)
- 3.5-4.0 stars = neutral (+0 to +40)
- 3.0-3.5 stars = concerning (-20 to 0)
- <3.0 stars = negative (-60 to -20)

Rating drops of >0.1 stars = red flag (app issues, bad update)

Data Source: Google Play Store (scraped via google-play-scraper package)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime
import hashlib
import json

try:
    from google_play_scraper import app as play_app
    PLAY_SCRAPER_AVAILABLE = True
except ImportError:
    PLAY_SCRAPER_AVAILABLE = False

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


class PlayStoreRatingsProcessor(SignalProcessor):
    """Process Google Play Store app ratings"""

    def __init__(self):
        """
        Initialize processor.

        Requires: google-play-scraper package
        Install: pip install google-play-scraper
        """
        # Map company IDs to their Play Store app IDs
        self.app_mappings = {
            "UBER": [
                {"name": "uber", "app_id": "com.ubercab"},
                {"name": "uber_eats", "app_id": "com.ubercab.eats"},
            ],
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="play_store_ratings",
            category=SignalCategory.WEB_DIGITAL,
            description="Google Play Store ratings - Android app quality tracking",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Google Play Store",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["play_store", "android", "mobile", "ratings", "product"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Only applicable to companies with Android apps"""
        return company.has_app and company.id in self.app_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Play Store ratings for company's apps.

        Uses google-play-scraper to get app metadata.
        """
        if not PLAY_SCRAPER_AVAILABLE:
            logger.warning("google-play-scraper not installed - using sample data")
            return self._get_sample_data(company)

        if company.id not in self.app_mappings:
            return {}

        apps = self.app_mappings[company.id]
        results = []

        for app_info in apps:
            try:
                logger.info(f"Fetching Play Store data for {app_info['name']} (ID: {app_info['app_id']})")

                # Fetch app details
                app_data = play_app(
                    app_info["app_id"],
                    lang="en",
                    country="us",
                )

                results.append({
                    "app_name": app_info["name"],
                    "app_id": app_info["app_id"],
                    "title": app_data.get("title"),
                    "score": app_data.get("score"),  # 0-5 rating
                    "ratings": app_data.get("ratings"),  # Total ratings count
                    "reviews": app_data.get("reviews"),  # Total reviews count
                    "installs": app_data.get("installs"),  # Install count (e.g., "10,000,000+")
                    "version": app_data.get("version"),
                    "updated": app_data.get("updated"),
                })

                logger.info(f"{app_info['name']}: {app_data.get('score')}/5 stars ({app_data.get('ratings')} ratings)")

            except Exception as e:
                logger.error(f"Error fetching Play Store data for {app_info['name']}: {e}")
                continue

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "apps": results,
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process Play Store ratings into signals.

        Generates one signal per app.
        """
        apps = raw_data.get("apps", [])

        if not apps:
            return []

        signals = []

        for app in apps:
            score_5 = app.get("score", 0)  # 0-5 rating
            ratings_count = app.get("ratings", 0)

            # Convert 5-star rating to -100 to +100 score
            # 5.0 = +100, 4.0 = +60, 3.0 = +20, 2.0 = -20, 1.0 = -60
            score_100 = int((score_5 - 3.0) * 40)
            score_100 = max(-100, min(100, score_100))

            # Confidence based on rating volume
            # More ratings = higher confidence
            if ratings_count > 1000000:
                confidence = 0.85
            elif ratings_count > 100000:
                confidence = 0.75
            elif ratings_count > 10000:
                confidence = 0.65
            else:
                confidence = 0.50

            # Build description
            installs = app.get("installs", "Unknown")
            description = f"{app['app_name']}: {score_5:.2f}/5 stars ({ratings_count:,} ratings, {installs} installs)"

            signal = Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value=app,
                normalized_value=score_100 / 100.0,
                score=score_100,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"https://play.google.com/store/apps/details?id={app['app_id']}",
                    source_name="Google Play Store",
                    processing_notes=f"App: {app['app_name']}",
                    raw_data_hash=hashlib.md5(
                        json.dumps(app, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["play_store", "android", app["app_name"]],
            )

            signals.append(signal)

        # Generate aggregate signal if multiple apps
        if len(signals) > 1:
            avg_score = sum(s.score for s in signals) / len(signals)
            avg_confidence = sum(s.confidence for s in signals) / len(signals)

            total_ratings = sum(app.get("ratings", 0) for app in apps)

            aggregate_signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_aggregate",
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={"apps": apps},
                normalized_value=avg_score / 100.0,
                score=int(avg_score),
                confidence=avg_confidence,
                metadata=SignalMetadata(
                    source_url="https://play.google.com/store",
                    source_name="Google Play Store (Aggregate)",
                    processing_notes=f"Aggregated from {len(apps)} apps",
                    raw_data_hash=hashlib.md5(
                        json.dumps(apps, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=f"Play Store aggregate: {avg_score:+.0f}/100 across {len(apps)} apps ({total_ratings:,} total ratings)",
                tags=["play_store", "android", "aggregate"],
            )

            signals.append(aggregate_signal)

        return signals

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """
        Return sample data when google-play-scraper not available.
        """
        if company.ticker == "UBER":
            sample_apps = [
                {
                    "app_name": "uber",
                    "app_id": "com.ubercab",
                    "title": "Uber - Request a ride",
                    "score": 4.2,
                    "ratings": 5200000,
                    "reviews": 450000,
                    "installs": "500,000,000+",
                    "version": "4.450.10001",
                    "updated": "2026-01-20",
                },
                {
                    "app_name": "uber_eats",
                    "app_id": "com.ubercab.eats",
                    "title": "Uber Eats: Food Delivery",
                    "score": 4.4,
                    "ratings": 3100000,
                    "reviews": 280000,
                    "installs": "100,000,000+",
                    "version": "6.182.10000",
                    "updated": "2026-01-25",
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

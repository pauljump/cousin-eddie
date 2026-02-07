"""
App Store Ratings Signal Processor

Tracks app ratings and review velocity for companies with mobile apps.
Declining ratings or review sentiment can predict user churn.

Data Source: iTunes/App Store RSS feeds (free)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime
import asyncio
import hashlib
import json
import re

import httpx
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


class AppStoreRatingsProcessor(SignalProcessor):
    """Process App Store ratings and reviews"""

    def __init__(self):
        # App Store IDs for known apps
        self.app_ids = {
            "UBER": {
                "uber": "368677368",  # Uber ride-hailing
                "uber_eats": "1058959277",  # Uber Eats
            }
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="app_store_ratings",
            category=SignalCategory.WEB_DIGITAL,
            description="App ratings and review sentiment from iOS App Store",
            update_frequency=UpdateFrequency.DAILY,
            data_source="iTunes RSS API",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["app", "mobile", "ratings", "reviews", "consumer"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Only applicable to companies with apps"""
        return company.has_app

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch app ratings from iTunes API.

        iTunes Lookup API: https://itunes.apple.com/lookup?id={app_id}
        Returns ratings, review count, version info.
        """

        if company.id not in self.app_ids:
            logger.warning(f"No app IDs configured for {company.id}")
            return {"apps": []}

        apps_data = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for app_name, app_id in self.app_ids[company.id].items():
                try:
                    url = f"https://itunes.apple.com/lookup?id={app_id}&country=us"
                    logger.info(f"Fetching App Store data for {app_name} (ID: {app_id})")

                    response = await client.get(url)
                    response.raise_for_status()

                    data = response.json()

                    if data.get("resultCount", 0) > 0:
                        app_info = data["results"][0]

                        apps_data.append({
                            "app_name": app_name,
                            "app_id": app_id,
                            "name": app_info.get("trackName"),
                            "version": app_info.get("version"),
                            "rating": app_info.get("averageUserRating", 0),
                            "rating_count": app_info.get("userRatingCount", 0),
                            "rating_current_version": app_info.get("averageUserRatingForCurrentVersion", 0),
                            "rating_count_current_version": app_info.get("userRatingCountForCurrentVersion", 0),
                            "price": app_info.get("price", 0),
                            "bundle_id": app_info.get("bundleId"),
                            "seller_name": app_info.get("sellerName"),
                            "primary_genre": app_info.get("primaryGenreName"),
                        })

                        logger.info(f"{app_name}: {app_info.get('averageUserRating', 0)}/5 stars ({app_info.get('userRatingCount', 0)} ratings)")
                    else:
                        logger.warning(f"No results for app ID {app_id}")

                except Exception as e:
                    logger.error(f"Error fetching app {app_name}: {e}")

        return {
            "company_id": company.id,
            "timestamp": datetime.utcnow(),
            "apps": apps_data
        }

    def process(
        self,
        company: Company,
        raw_data: Dict[str, Any]
    ) -> List[Signal]:
        """
        Process app ratings into signals.

        Scoring logic:
        - Average rating across all apps
        - High ratings (4.5+) = positive signal
        - Declining ratings = negative signal (requires historical tracking)
        - Review velocity (high review count = high engagement)
        """

        timestamp = raw_data.get("timestamp", datetime.utcnow())
        apps = raw_data.get("apps", [])

        if not apps:
            return []

        signals = []

        # Create signal for each app
        for app in apps:
            rating = app.get("rating", 0)
            rating_count = app.get("rating_count", 0)
            app_name = app.get("app_name", "unknown")

            # Score based on rating
            if rating >= 4.5:
                score = 80
                confidence = 0.8
                description = f"{app_name}: Excellent rating {rating}/5 ({rating_count:,} reviews)"
            elif rating >= 4.0:
                score = 50
                confidence = 0.7
                description = f"{app_name}: Good rating {rating}/5 ({rating_count:,} reviews)"
            elif rating >= 3.5:
                score = 20
                confidence = 0.6
                description = f"{app_name}: Average rating {rating}/5 ({rating_count:,} reviews)"
            elif rating >= 3.0:
                score = -20
                confidence = 0.6
                description = f"{app_name}: Below average rating {rating}/5 ({rating_count:,} reviews)"
            else:
                score = -60
                confidence = 0.7
                description = f"{app_name}: Poor rating {rating}/5 ({rating_count:,} reviews)"

            # Adjust for review count (more reviews = higher confidence)
            if rating_count > 1_000_000:
                confidence = min(confidence + 0.15, 1.0)
            elif rating_count > 100_000:
                confidence = min(confidence + 0.1, 1.0)
            elif rating_count < 1_000:
                confidence *= 0.7

            normalized_value = score / 100.0

            signal = Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value=app,
                normalized_value=normalized_value,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"https://apps.apple.com/us/app/id{app.get('app_id')}",
                    source_name="iTunes App Store",
                    processing_notes=f"App: {app_name}",
                    raw_data_hash=hashlib.md5(
                        json.dumps(app, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["app_store", "ratings", "mobile", app_name],
            )

            signals.append(signal)

        # Also create an aggregate signal across all apps
        if len(apps) > 1:
            avg_rating = sum(a.get("rating", 0) for a in apps) / len(apps)
            total_reviews = sum(a.get("rating_count", 0) for a in apps)

            if avg_rating >= 4.0:
                agg_score = 70
                agg_conf = 0.8
            elif avg_rating >= 3.5:
                agg_score = 30
                agg_conf = 0.7
            else:
                agg_score = -30
                agg_conf = 0.7

            aggregate_signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_aggregate",
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value={"apps": apps, "avg_rating": avg_rating},
                normalized_value=agg_score / 100.0,
                score=agg_score,
                confidence=agg_conf,
                metadata=SignalMetadata(
                    source_url="https://apps.apple.com",
                    source_name="iTunes App Store (Aggregate)",
                    processing_notes=f"Aggregated {len(apps)} apps",
                ),
                description=f"Portfolio average: {avg_rating:.2f}/5 across {len(apps)} apps ({total_reviews:,} total reviews)",
                tags=["app_store", "ratings", "aggregate"],
            )

            signals.append(aggregate_signal)

        return signals

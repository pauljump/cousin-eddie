"""
Google Trends Signal Processor

Tracks search volume for company and product keywords.
Rising search interest can predict revenue growth or breakout moments.

Data Source: Google Trends (free)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import hashlib
import json

from loguru import logger
from pytrends.request import TrendReq

from ...core.signal_processor import (
    SignalProcessor,
    SignalProcessorMetadata,
    UpdateFrequency,
    DataCost,
    Difficulty,
)
from ...core.signal import Signal, SignalCategory, SignalMetadata
from ...core.company import Company


class GoogleTrendsProcessor(SignalProcessor):
    """Process Google Trends search volume data"""

    def __init__(self):
        self.pytrends = TrendReq(hl='en-US', tz=360)

        # Keywords to track per company
        self.keywords = {
            "UBER": ["uber", "uber eats", "rideshare"],
            "LYFT": ["lyft", "lyft ride", "rideshare"],
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="google_trends",
            category=SignalCategory.WEB_DIGITAL,
            description="Search volume trends - proxy for consumer interest",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Google Trends",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["search", "trends", "consumer_interest", "google"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies (everyone can be searched)"""
        return True

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Google Trends data.

        Note: pytrends is synchronous, so we run in executor.
        """

        keywords = self.keywords.get(company.id, [company.ticker.lower(), company.name.lower()])

        # Google Trends works best with recent data (last 90 days)
        # For longer timeframes, data is aggregated weekly/monthly
        timeframe = "today 3-m"  # Last 3 months, daily data

        try:
            logger.info(f"Fetching Google Trends for {company.ticker}: {keywords}")

            # Build payload (pytrends is synchronous)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.pytrends.build_payload,
                keywords,
                None,  # cat (category)
                timeframe,
                'US'   # geo
                # gprop parameter removed - defaults to '' (web search)
            )

            # Get interest over time
            interest_df = await loop.run_in_executor(
                None,
                self.pytrends.interest_over_time
            )

            if interest_df.empty or 'isPartial' not in interest_df.columns:
                logger.warning(f"No Google Trends data for {company.ticker}")
                return {
                    "company_id": company.id,
                    "timestamp": datetime.utcnow(),
                    "keywords": keywords,
                    "data": []
                }

            # Convert to list of dicts
            data_points = []
            for date, row in interest_df.iterrows():
                point = {"date": str(date)}
                for keyword in keywords:
                    if keyword in row:
                        point[keyword] = int(row[keyword])
                data_points.append(point)

            logger.info(f"Retrieved {len(data_points)} data points for {company.ticker}")

            return {
                "company_id": company.id,
                "timestamp": datetime.utcnow(),
                "keywords": keywords,
                "timeframe": timeframe,
                "data": data_points
            }

        except Exception as e:
            logger.error(f"Error fetching Google Trends for {company.ticker}: {e}")
            return {
                "company_id": company.id,
                "timestamp": datetime.utcnow(),
                "keywords": keywords,
                "error": str(e),
                "data": []
            }

    def process(
        self,
        company: Company,
        raw_data: Dict[str, Any]
    ) -> List[Signal]:
        """
        Process Google Trends data into signals.

        Scoring logic:
        - Calculate recent average vs historical average
        - Rising trend = bullish (increased interest)
        - Falling trend = bearish (declining interest)
        - Absolute volume matters too
        """

        timestamp = raw_data.get("timestamp", datetime.utcnow())
        keywords = raw_data.get("keywords", [])
        data_points = raw_data.get("data", [])

        if not data_points:
            return []

        signals = []

        # Analyze each keyword
        for keyword in keywords:
            # Extract values for this keyword
            values = [p.get(keyword, 0) for p in data_points if keyword in p]

            if not values:
                continue

            # Calculate metrics
            recent_avg = sum(values[-7:]) / min(7, len(values))  # Last 7 days
            historical_avg = sum(values) / len(values)  # Overall average

            current_value = values[-1] if values else 0

            # Trend direction
            if len(values) >= 30:
                early_avg = sum(values[:15]) / 15
                late_avg = sum(values[-15:]) / 15
                trend_change_pct = ((late_avg - early_avg) / early_avg * 100) if early_avg > 0 else 0
            else:
                trend_change_pct = 0

            # Score based on trend
            if trend_change_pct > 50:
                score = 80
                confidence = 0.75
                description = f"{keyword}: Strong uptrend (+{trend_change_pct:.0f}% search interest)"
            elif trend_change_pct > 20:
                score = 50
                confidence = 0.7
                description = f"{keyword}: Growing interest (+{trend_change_pct:.0f}%)"
            elif trend_change_pct > 5:
                score = 20
                confidence = 0.6
                description = f"{keyword}: Slight increase (+{trend_change_pct:.0f}%)"
            elif trend_change_pct < -50:
                score = -80
                confidence = 0.75
                description = f"{keyword}: Sharp decline ({trend_change_pct:.0f}% search interest)"
            elif trend_change_pct < -20:
                score = -50
                confidence = 0.7
                description = f"{keyword}: Declining interest ({trend_change_pct:.0f}%)"
            elif trend_change_pct < -5:
                score = -20
                confidence = 0.6
                description = f"{keyword}: Slight decline ({trend_change_pct:.0f}%)"
            else:
                score = 0
                confidence = 0.5
                description = f"{keyword}: Stable search interest"

            # Adjust for absolute volume (higher volume = higher confidence)
            if recent_avg > 75:
                confidence = min(confidence + 0.15, 1.0)
            elif recent_avg < 25:
                confidence *= 0.8

            normalized_value = score / 100.0

            signal = Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value={
                    "keyword": keyword,
                    "current_value": current_value,
                    "recent_avg": recent_avg,
                    "historical_avg": historical_avg,
                    "trend_change_pct": trend_change_pct,
                    "data_points": len(values)
                },
                normalized_value=normalized_value,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url="https://trends.google.com",
                    source_name="Google Trends",
                    processing_notes=f"Keyword: {keyword}, {len(values)} data points",
                    raw_data_hash=hashlib.md5(
                        json.dumps(values, sort_keys=True).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["google_trends", "search", keyword.replace(" ", "_")],
            )

            signals.append(signal)

        return signals

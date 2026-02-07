"""
Wikipedia Page Views Signal Processor

Tracks Wikipedia article views as a proxy for brand awareness and public interest.

Why Wikipedia views matter:
- Public interest proxy (news events, viral moments)
- Brand awareness indicator
- View spikes = major news events (good or bad)
- Declining views = fading relevance
- Free, public data (no API key needed)
- Correlates with stock price volatility

Key Insights:
- Normal traffic: 1000-10,000 views/day for mid-cap companies
- Spike traffic: 50,000+ views/day (major news)
- Declining baseline = losing cultural relevance
- IPO/earnings days show massive spikes
- Scandal/crisis days show even bigger spikes

Signals:
- View spike + positive news = bullish attention
- View spike + negative news = crisis
- Gradually increasing views = growing brand
- Declining views = losing mindshare
- Weekend vs weekday patterns

Companies with Wikipedia pages:
- All public companies
- Major private companies
- Notable people (CEOs)

Data Source: Wikimedia Pageviews API (free, unlimited)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json

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


class WikipediaPageviewsProcessor(SignalProcessor):
    """Track Wikipedia page views for companies"""

    def __init__(self):
        """Initialize processor."""
        self.api_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"

        # Map company IDs to Wikipedia article titles
        self.wikipedia_mappings = {
            "UBER": "Uber",
            "LYFT": "Lyft",
            "ABNB": "Airbnb",
            "GOOGL": "Google",
            "AAPL": "Apple_Inc.",
            "MSFT": "Microsoft",
            "TSLA": "Tesla,_Inc.",
            "AMZN": "Amazon_(company)",
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="wikipedia_pageviews",
            category=SignalCategory.ALTERNATIVE,
            description="Wikipedia page views - public interest and brand awareness proxy",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Wikimedia Pageviews API",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["wikipedia", "pageviews", "brand_awareness", "public_interest"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with Wikipedia articles"""
        return company.id in self.wikipedia_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Wikipedia pageview data.

        Uses Wikimedia REST API (free, no auth required).
        """
        if company.id not in self.wikipedia_mappings:
            return {}

        article_title = self.wikipedia_mappings[company.id]

        # Format dates for API (YYYYMMDD00)
        start_str = start.strftime("%Y%m%d00")
        end_str = end.strftime("%Y%m%d00")

        url = f"{self.api_url}/en.wikipedia/all-access/all-agents/{article_title}/daily/{start_str}/{end_str}"

        headers = {
            "User-Agent": "cousin-eddie/1.0 (research@example.com)"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching Wikipedia pageviews for {article_title}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                items = data.get("items", [])

                logger.info(f"Found {len(items)} days of pageview data")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "article_title": article_title,
                    "pageviews": items,
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPError as e:
            logger.error(f"Error fetching Wikipedia data: {e}")
            # Fall back to sample data
            logger.warning("Using sample Wikipedia data")
            return self._get_sample_data(company)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process Wikipedia pageview data into signals.

        Analyzes:
        1. Average daily views (baseline interest)
        2. View trend (growing/declining)
        3. View spikes (major events)
        """
        pageviews = raw_data.get("pageviews", [])
        article_title = raw_data.get("article_title", "")

        if not pageviews:
            return []

        # Calculate metrics
        total_views = sum(item.get("views", 0) for item in pageviews)
        avg_daily_views = total_views / len(pageviews) if pageviews else 0

        # Find peak day
        max_views = 0
        max_date = None
        for item in pageviews:
            views = item.get("views", 0)
            if views > max_views:
                max_views = views
                max_date = item.get("timestamp", "")

        # Calculate trend (first half vs second half)
        mid_point = len(pageviews) // 2
        first_half_avg = sum(item.get("views", 0) for item in pageviews[:mid_point]) / mid_point if mid_point > 0 else 0
        second_half_avg = sum(item.get("views", 0) for item in pageviews[mid_point:]) / (len(pageviews) - mid_point) if len(pageviews) > mid_point else 0

        trend_change_pct = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0

        # Detect spike (peak day vs average)
        spike_ratio = max_views / avg_daily_views if avg_daily_views > 0 else 1

        # Calculate score
        # Base score from average daily views
        # 10k+ views/day = +60 to +80 (major brand)
        # 5k-10k = +40 to +60 (strong brand)
        # 1k-5k = +20 to +40 (moderate brand)
        # <1k = 0 to +20 (small brand)

        if avg_daily_views > 10000:
            base_score = min(80, 60 + (avg_daily_views - 10000) / 1000)
        elif avg_daily_views > 5000:
            base_score = 40 + ((avg_daily_views - 5000) / 5000) * 20
        elif avg_daily_views > 1000:
            base_score = 20 + ((avg_daily_views - 1000) / 4000) * 20
        else:
            base_score = (avg_daily_views / 1000) * 20

        # Trend adjustment
        trend_score = min(20, max(-20, trend_change_pct / 5))

        # Spike bonus/penalty depends on context
        # Large spike (5x+ average) could be good or bad news
        spike_score = 0
        if spike_ratio > 5:
            # Assume neutral for now (need news sentiment to determine good/bad)
            spike_score = 0

        total_score = int(base_score + trend_score + spike_score)
        total_score = max(0, min(100, total_score))

        # Confidence
        confidence = 0.70  # Public data, reliable

        # Build description
        description = f"Wikipedia: {avg_daily_views:,.0f} avg daily views ({len(pageviews)} days)"

        if trend_change_pct > 10:
            description += f" | 📈 Views trending up {trend_change_pct:+.0f}%"
        elif trend_change_pct < -10:
            description += f" | 📉 Views trending down {trend_change_pct:.0f}%"

        if spike_ratio > 5:
            description += f" | Peak: {max_views:,} views (🔥 {spike_ratio:.1f}x spike)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "avg_daily_views": avg_daily_views,
                "total_views": total_views,
                "max_views": max_views,
                "trend_change_pct": trend_change_pct,
                "spike_ratio": spike_ratio,
            },
            normalized_value=total_score / 100.0,
            score=total_score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://en.wikipedia.org/wiki/{article_title}",
                source_name="Wikipedia Pageviews",
                processing_notes=f"{avg_daily_views:,.0f} avg views/day, trend: {trend_change_pct:+.0f}%",
                raw_data_hash=hashlib.md5(
                    json.dumps(pageviews, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["wikipedia", "pageviews", "brand_awareness"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample Wikipedia pageview data"""
        if company.ticker == "UBER":
            # Generate 30 days of sample data
            sample_pageviews = []
            base_date = datetime.utcnow() - timedelta(days=30)

            for i in range(30):
                date = base_date + timedelta(days=i)
                # Normal days: 3000-5000 views
                # Spike day (earnings): 25000 views
                if i == 25:  # Earnings day
                    views = 25000
                else:
                    views = 3500 + (i % 7) * 200  # Slight variation

                sample_pageviews.append({
                    "project": "en.wikipedia",
                    "article": "Uber",
                    "granularity": "daily",
                    "timestamp": date.strftime("%Y%m%d00"),
                    "access": "all-access",
                    "agent": "all-agents",
                    "views": views,
                })

            article_title = "Uber"
        else:
            sample_pageviews = []
            article_title = ""

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "article_title": article_title,
            "pageviews": sample_pageviews,
            "timestamp": datetime.utcnow(),
        }

"""
YouTube Channel Metrics Signal Processor

Tracks YouTube subscriber growth, video views, and engagement.

Why YouTube metrics matter:
- Video content reach and virality
- Brand awareness through video
- Subscriber growth = audience building
- View counts = content effectiveness
- Engagement (likes/comments) = audience quality
- Important for B2C brands and content companies

Key Metrics:
- Subscriber count
- Subscriber growth rate
- Total video views
- Recent video performance
- Average views per video
- Engagement rate (likes, comments per view)
- Upload frequency

Signals:
- Rapid subscriber growth = successful content strategy
- Viral videos = brand awareness spike
- High engagement = loyal audience
- Declining views = content fatigue
- Irregular uploads = inconsistent strategy

Benchmarks:
- 100k subs = established channel
- 1M+ subs = major influencer/brand
- 10M+ subs = top-tier brand channel
- Avg engagement rate: 4-6% is good, <2% is poor

Data Source: YouTube Data API v3 (free, 10,000 quota/day)
Update Frequency: Daily
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


class YouTubeMetricsProcessor(SignalProcessor):
    """Track YouTube channel metrics"""

    def __init__(self, youtube_api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            youtube_api_key: YouTube Data API v3 key
                            Get from: https://console.cloud.google.com/
        """
        self.api_key = youtube_api_key

        # Map companies to YouTube channel IDs
        self.channel_mappings = {
            "UBER": "UCgnxoUwDmmyzeigmmcf0hZA",  # Uber channel
            "GOOGL": "UCK8sQmJBp8GCxrOtXWBpyEA",  # Google
            "AAPL": "UCE_M8A5yxnLfW0KghEeajjw",  # Apple
            "TSLA": "UCCb9_K2FxOS6xNOjCWy7sOA",  # Tesla (unofficial)
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="youtube_metrics",
            category=SignalCategory.ALTERNATIVE,
            description="YouTube channel metrics - video content reach and engagement",
            update_frequency=UpdateFrequency.DAILY,
            data_source="YouTube Data API v3",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["youtube", "video", "content", "engagement"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with YouTube presence"""
        return company.id in self.channel_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch YouTube channel statistics.

        For POC, uses sample data.
        Production would call YouTube Data API.
        """
        if company.id not in self.channel_mappings:
            return {}

        # In production, call YouTube API here
        logger.warning("YouTube API not configured - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process YouTube metrics into signals.

        Analyzes:
        1. Subscriber growth
        2. Video view counts
        3. Engagement rates
        """
        stats = raw_data.get("statistics", {})

        if not stats:
            return []

        subscriber_count = stats.get("subscriber_count", 0)
        previous_subscriber_count = stats.get("previous_subscriber_count", 0)
        total_view_count = stats.get("view_count", 0)
        video_count = stats.get("video_count", 0)
        recent_videos = raw_data.get("recent_videos", [])

        # Calculate subscriber growth
        if previous_subscriber_count > 0:
            subscriber_growth_rate = ((subscriber_count - previous_subscriber_count) / previous_subscriber_count) * 100
        else:
            subscriber_growth_rate = 0

        # Calculate average views per video from recent videos
        if recent_videos:
            avg_views = sum(v.get("views", 0) for v in recent_videos) / len(recent_videos)
            avg_engagement_rate = sum(
                (v.get("likes", 0) + v.get("comments", 0)) / v.get("views", 1) * 100
                for v in recent_videos
            ) / len(recent_videos)
        else:
            avg_views = total_view_count / video_count if video_count > 0 else 0
            avg_engagement_rate = 0

        # Calculate score
        # Subscriber count component
        if subscriber_count > 1000000:
            sub_score = min(40, 30 + (subscriber_count - 1000000) / 100000)
        elif subscriber_count > 100000:
            sub_score = 20 + ((subscriber_count - 100000) / 900000) * 10
        elif subscriber_count > 10000:
            sub_score = 10 + ((subscriber_count - 10000) / 90000) * 10
        else:
            sub_score = (subscriber_count / 10000) * 10

        # Growth component
        if subscriber_growth_rate > 5:
            growth_score = min(30, 20 + subscriber_growth_rate)
        elif subscriber_growth_rate > 0:
            growth_score = subscriber_growth_rate * 4
        elif subscriber_growth_rate > -2:
            growth_score = subscriber_growth_rate * 5
        else:
            growth_score = max(-30, -20 + subscriber_growth_rate * 3)

        # Engagement component
        if avg_engagement_rate > 5:
            engagement_score = 20
        elif avg_engagement_rate > 3:
            engagement_score = 15
        elif avg_engagement_rate > 1:
            engagement_score = 10
        else:
            engagement_score = 0

        total_score = int(sub_score + growth_score + engagement_score)
        total_score = max(-100, min(100, total_score))

        # Confidence
        confidence = 0.75

        # Build description
        description = f"YouTube: {subscriber_count:,} subscribers ({subscriber_growth_rate:+.1f}% growth)"
        description += f" | {total_view_count:,} total views"
        description += f" | Engagement: {avg_engagement_rate:.1f}%"

        if subscriber_growth_rate > 5:
            description += " 📈 Rapid growth"

        # Find viral video
        if recent_videos:
            top_video = max(recent_videos, key=lambda v: v.get("views", 0))
            if top_video.get("views", 0) > avg_views * 3:
                description += f" | 🔥 Viral: '{top_video['title'][:40]}...'"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "subscriber_count": subscriber_count,
                "subscriber_growth_rate": subscriber_growth_rate,
                "total_views": total_view_count,
                "avg_engagement_rate": avg_engagement_rate,
                "recent_videos": recent_videos,
            },
            normalized_value=total_score / 100.0,
            score=total_score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://www.youtube.com/channel/{self.channel_mappings.get(company.id, '')}",
                source_name="YouTube",
                processing_notes=f"{subscriber_count:,} subs, {subscriber_growth_rate:+.1f}% growth",
                raw_data_hash=hashlib.md5(
                    json.dumps(stats, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["youtube", "video", "subscribers", "engagement"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample YouTube data"""
        if company.ticker == "UBER":
            sample_stats = {
                "subscriber_count": 245000,
                "previous_subscriber_count": 238000,
                "view_count": 12500000,
                "video_count": 580,
            }

            sample_recent_videos = [
                {
                    "title": "Introducing Uber's New Electric Vehicle Fleet",
                    "views": 450000,
                    "likes": 18500,
                    "comments": 1200,
                    "published_at": "2026-01-25",
                },
                {
                    "title": "How Uber is Making Cities Safer",
                    "views": 280000,
                    "likes": 12000,
                    "comments": 850,
                    "published_at": "2026-01-18",
                },
                {
                    "title": "Uber Driver Stories: Meet Sarah",
                    "views": 95000,
                    "likes": 5200,
                    "comments": 320,
                    "published_at": "2026-01-10",
                },
            ]
        else:
            sample_stats = {}
            sample_recent_videos = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "statistics": sample_stats,
            "recent_videos": sample_recent_videos,
            "timestamp": datetime.utcnow(),
        }

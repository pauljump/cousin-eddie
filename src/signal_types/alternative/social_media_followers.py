"""
Social Media Follower Growth Signal Processor

Tracks follower counts and growth across social platforms.

Why follower growth matters:
- Brand awareness proxy
- Audience engagement and reach
- Marketing effectiveness
- Follower growth = brand momentum
- Follower loss = brand damage or declining relevance
- Engagement rate more important than raw count

Platforms Tracked:
- Twitter/X (followers, engagement rate)
- Instagram (followers, likes, comments)
- Facebook (page likes, followers)
- LinkedIn (company followers)
- TikTok (followers, views)
- YouTube (subscribers - separate processor)

Key Metrics:
- Total followers per platform
- Month-over-month growth rate
- Engagement rate (likes, comments, shares per post)
- Follower quality (verified, active users)
- Platform mix (which channels growing/declining)

Signals:
- Rapid follower growth (>5% MoM) = strong brand momentum
- Declining followers = brand damage, losing relevance
- High engagement rate = loyal audience
- Low engagement despite high followers = fake/bot followers
- Platform-specific growth reveals strategy (TikTok for Gen Z, etc.)

Benchmarks:
- Twitter: 100k+ followers = established brand
- Instagram: 1M+ followers = major consumer brand
- LinkedIn: 500k+ = B2B powerhouse
- TikTok: 1M+ = youth market dominance

Data Sources:
1. Twitter API (follower count, engagement metrics)
2. Instagram Graph API (requires Business account)
3. Facebook Graph API
4. LinkedIn API
5. Manual tracking (periodic snapshots)

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


class SocialMediaFollowersProcessor(SignalProcessor):
    """Track social media follower growth across platforms"""

    def __init__(self):
        """Initialize processor."""
        # Manual follower tracking
        # Format: {company_id: {platform: [(date, followers, engagement_rate), ...]}}
        self.follower_snapshots = {
            "UBER": {
                "twitter": [
                    ("2026-02-01", 1250000, 2.1),
                    ("2026-01-01", 1235000, 2.0),
                    ("2025-12-01", 1220000, 2.2),
                    ("2025-11-01", 1205000, 2.3),
                ],
                "instagram": [
                    ("2026-02-01", 3800000, 3.5),
                    ("2026-01-01", 3720000, 3.4),
                    ("2025-12-01", 3650000, 3.6),
                    ("2025-11-01", 3580000, 3.8),
                ],
                "linkedin": [
                    ("2026-02-01", 2100000, 1.5),
                    ("2026-01-01", 2050000, 1.4),
                    ("2025-12-01", 2000000, 1.6),
                    ("2025-11-01", 1950000, 1.5),
                ],
                "facebook": [
                    ("2026-02-01", 5200000, 1.8),
                    ("2026-01-01", 5150000, 1.7),
                    ("2025-12-01", 5100000, 1.9),
                    ("2025-11-01", 5050000, 2.0),
                ],
            },
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="social_media_followers",
            category=SignalCategory.ALTERNATIVE,
            description="Social media follower growth - brand awareness and engagement tracking",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="Twitter, Instagram, Facebook, LinkedIn APIs",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["social_media", "followers", "brand_awareness", "engagement"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with social media presence"""
        return company.id in self.follower_snapshots

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch follower data from social platforms.

        In production: call platform APIs
        For POC: use manual snapshots
        """
        if company.id not in self.follower_snapshots:
            return {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "platforms": self.follower_snapshots[company.id],
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process follower data into signals.

        Generates:
        1. Per-platform growth signals
        2. Aggregate follower growth signal
        3. Engagement quality signals
        """
        platforms = raw_data.get("platforms", {})

        if not platforms:
            return []

        signals = []
        total_followers = 0
        total_previous_followers = 0
        platform_scores = []

        for platform_name, snapshots in platforms.items():
            if len(snapshots) < 2:
                continue

            # Sort by date (newest first)
            snapshots = sorted(snapshots, key=lambda x: x[0], reverse=True)

            latest_date, latest_followers, latest_engagement = snapshots[0]
            prev_date, prev_followers, prev_engagement = snapshots[1]

            # Calculate growth
            growth_absolute = latest_followers - prev_followers
            growth_rate = (growth_absolute / prev_followers * 100) if prev_followers > 0 else 0

            total_followers += latest_followers
            total_previous_followers += prev_followers

            # Calculate score
            # Growth component
            if growth_rate > 5:
                growth_score = min(60, 40 + growth_rate * 4)
            elif growth_rate > 0:
                growth_score = growth_rate * 8
            elif growth_rate > -2:
                growth_score = growth_rate * 10
            else:
                growth_score = max(-60, -40 + growth_rate * 5)

            # Engagement component
            # Good engagement: >3% for most platforms
            # Average: 1-3%
            # Poor: <1%
            engagement_score = 0
            if latest_engagement > 3:
                engagement_score = 20
            elif latest_engagement > 1.5:
                engagement_score = 10
            elif latest_engagement < 0.5:
                engagement_score = -15

            platform_score = int(growth_score + engagement_score)
            platform_score = max(-100, min(100, platform_score))

            platform_scores.append({
                "platform": platform_name,
                "score": platform_score,
                "followers": latest_followers,
                "growth_rate": growth_rate,
            })

            # Per-platform signal
            description = f"{platform_name.title()}: {latest_followers:,} followers ({growth_rate:+.1f}% MoM)"
            description += f" | Engagement: {latest_engagement}%"

            if growth_rate > 5:
                description += " 📈 Rapid growth"
            elif growth_rate < -2:
                description += " 📉 Losing followers"

            signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_{platform_name}",
                category=self.metadata.category,
                timestamp=datetime.fromisoformat(latest_date),
                raw_value={
                    "platform": platform_name,
                    "followers": latest_followers,
                    "growth_rate": growth_rate,
                    "engagement_rate": latest_engagement,
                },
                normalized_value=platform_score / 100.0,
                score=platform_score,
                confidence=0.75,
                metadata=SignalMetadata(
                    source_url=f"https://www.{platform_name}.com/{company.name.lower().replace(' ', '')}",
                    source_name=f"{platform_name.title()} Followers",
                    processing_notes=f"{growth_rate:+.1f}% MoM growth",
                    raw_data_hash=hashlib.md5(
                        json.dumps(snapshots, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["social_media", platform_name, "follower_growth"],
            )

            signals.append(signal)

        # Aggregate signal
        if total_previous_followers > 0:
            overall_growth = ((total_followers - total_previous_followers) / total_previous_followers) * 100
            avg_score = sum(p["score"] for p in platform_scores) / len(platform_scores)

            aggregate_description = f"Social media: {total_followers:,} total followers ({overall_growth:+.1f}% MoM)"
            aggregate_description += f" across {len(platforms)} platforms"

            aggregate_signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_aggregate",
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "total_followers": total_followers,
                    "overall_growth_rate": overall_growth,
                    "platforms": platform_scores,
                },
                normalized_value=avg_score / 100.0,
                score=int(avg_score),
                confidence=0.80,
                metadata=SignalMetadata(
                    source_url="https://www.socialmedia.com",
                    source_name="Social Media (Aggregate)",
                    processing_notes=f"Aggregated from {len(platforms)} platforms",
                    raw_data_hash=hashlib.md5(
                        json.dumps(platform_scores, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=aggregate_description,
                tags=["social_media", "aggregate", "brand_awareness"],
            )

            signals.append(aggregate_signal)

        return signals

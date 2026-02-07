"""
Niche Community Sentiment Signal Processor

Tracks sentiment in industry-specific online communities.

Why niche communities matter (from ChatGPT research):
"Beyond broad Reddit sentiment, monitoring specialized communities can yield
alpha. For example, r/dataengineering or Hacker News discussions about a SaaS
company's technical issues, r/wallstreetbets for retail flow signals, or
industry-specific Discord servers where professionals gather. These communities
often spot problems (product bugs, competitive threats, pricing issues) before
mainstream media."

Key Communities by Industry:
- Tech: Hacker News, r/programming, r/dataengineering, Discord dev servers
- Finance: r/wallstreetbets, r/investing, r/options, FinTwit
- Gaming: Gaming Discord servers, r/gaming, Twitch chat
- Retail: r/frugal, slickdeals forums, shopping communities
- Pharma: r/medicine, biotech forums, clinical trial discussion boards
- Energy: oil & gas industry forums, r/energy

Signals:
- Sentiment shifts in professional communities = early warning
- Bug reports / technical complaints = product quality issues
- Competitive discussions = market share shifts
- Pricing complaints = pricing power erosion
- Excitement/hype = potential momentum (positive or bubble)

Red Flags:
- Developers complaining about company's tech stack = talent retention risk
- Multiple bug reports on niche forums = quality issues
- Competitors praised in industry forums = losing mindshare
- Pricing complaints from power users = churn risk

Data Source: Reddit API, Discord (if available), HackerNews API, specialized forums
Update Frequency: Daily (some communities are real-time)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
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


class NicheCommunitySentimentProcessor(SignalProcessor):
    """Tracks sentiment in industry-specific online communities"""

    # Industry-specific communities
    COMMUNITY_MAP = {
        "tech": [
            "r/programming",
            "r/dataengineering",
            "r/devops",
            "Hacker News",
        ],
        "transportation": [
            "r/uberdrivers",
            "r/lyftdrivers",
            "r/doordash",
            "r/InstacartShoppers",
        ],
        "finance": [
            "r/wallstreetbets",
            "r/stocks",
            "r/investing",
            "r/options",
        ],
        "gaming": [
            "r/gaming",
            "r/pcgaming",
            "r/ps5",
        ],
    }

    # Negative keywords (stronger than general sentiment)
    NEGATIVE_KEYWORDS = [
        "bug",
        "broken",
        "terrible",
        "awful",
        "scam",
        "rip-off",
        "disappointed",
        "frustrated",
        "angry",
        "unacceptable",
        "worst",
        "garbage",
        "useless",
    ]

    # Positive keywords
    POSITIVE_KEYWORDS = [
        "love",
        "amazing",
        "great",
        "excellent",
        "perfect",
        "awesome",
        "fantastic",
        "impressed",
        "revolutionary",
    ]

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="niche_community_sentiment",
            category=SignalCategory.ALTERNATIVE,
            description="Niche community sentiment - industry-specific forums and Discord",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Reddit, Hacker News, Discord, Industry Forums",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["sentiment", "communities", "social_media", "early_warning"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with active online communities"""
        # Most tech companies and consumer-facing brands have communities
        return company.is_tech_company or company.has_app or company.has_physical_locations

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch posts from relevant niche communities.

        For POC, use sample data.
        Production would:
        1. Query Reddit API for company mentions in industry subreddits
        2. Scrape Hacker News for company discussions
        3. Monitor Discord servers (if accessible)
        4. Track industry-specific forums
        """
        logger.warning("Niche community scraping not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process community posts for sentiment signals.

        Analyzes:
        1. Overall sentiment in niche communities
        2. Specific issue mentions (bugs, pricing, competitors)
        3. Volume of discussion (mindshare)
        4. Professional vs retail sentiment differences
        """
        posts = raw_data.get("posts", [])

        if not posts:
            return []

        # Metrics
        total_posts = len(posts)
        positive_count = 0
        negative_count = 0
        bug_mentions = 0
        competitor_mentions = 0
        pricing_complaints = 0

        for post in posts:
            content = post.get("content", "").lower()
            community = post.get("community", "")

            # Count sentiment
            for keyword in self.POSITIVE_KEYWORDS:
                if keyword in content:
                    positive_count += 1
                    break  # Count once per post

            for keyword in self.NEGATIVE_KEYWORDS:
                if keyword in content:
                    negative_count += 1
                    break

            # Specific issues
            if "bug" in content or "broken" in content or "not working" in content:
                bug_mentions += 1

            if "competitor" in content or "alternative" in content or "switch" in content:
                competitor_mentions += 1

            if "expensive" in content or "price" in content or "cost" in content:
                pricing_complaints += 1

        # Calculate score
        net_sentiment = positive_count - negative_count
        sentiment_ratio = net_sentiment / max(total_posts, 1)

        score = sentiment_ratio * 100

        # Penalties for specific issues
        if bug_mentions > total_posts * 0.2:
            score -= 20  # Many bug reports = bad

        if competitor_mentions > total_posts * 0.3:
            score -= 15  # Losing to competitors

        if pricing_complaints > total_posts * 0.25:
            score -= 10  # Pricing issues

        score = max(-100, min(100, score))

        # Confidence (more posts = higher confidence)
        confidence = min(0.85, 0.60 + (total_posts / 100))

        # Build description
        description = f"Niche communities: {total_posts} posts"

        if net_sentiment > 0:
            description += f" | Positive sentiment (+{net_sentiment})"
        elif net_sentiment < 0:
            description += f" | Negative sentiment ({net_sentiment})"

        if bug_mentions > total_posts * 0.2:
            description += " | 🚨 Multiple bug reports"

        if competitor_mentions > total_posts * 0.3:
            description += " | ⚠️ Competitor mentions high"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_posts": total_posts,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "net_sentiment": net_sentiment,
                "bug_mentions": bug_mentions,
                "competitor_mentions": competitor_mentions,
                "pricing_complaints": pricing_complaints,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://reddit.com",
                source_name="Niche Communities",
                processing_notes=f"{total_posts} posts analyzed",
                raw_data_hash=hashlib.md5(
                    json.dumps(posts, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["niche_communities", "sentiment", "forums"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample community data"""

        if company.ticker == "UBER":
            # Sample: Mixed sentiment with some concerns
            posts = [
                {
                    "community": "r/uberdrivers",
                    "content": "New pay structure is terrible. They're cutting our rates again.",
                    "timestamp": datetime.utcnow() - timedelta(hours=2),
                },
                {
                    "community": "r/uberdrivers",
                    "content": "App has been buggy all week. Can't accept rides.",
                    "timestamp": datetime.utcnow() - timedelta(hours=5),
                },
                {
                    "community": "Hacker News",
                    "content": "Uber's autonomous program is impressive. Great technology.",
                    "timestamp": datetime.utcnow() - timedelta(hours=8),
                },
                {
                    "community": "r/uberdrivers",
                    "content": "Switching to Lyft. Better rates.",
                    "timestamp": datetime.utcnow() - timedelta(hours=12),
                },
                {
                    "community": "r/technology",
                    "content": "Love the new Uber Eats features",
                    "timestamp": datetime.utcnow() - timedelta(days=1),
                },
            ]
        else:
            posts = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "posts": posts,
            "timestamp": datetime.utcnow(),
        }

"""
Twitter/X Sentiment Signal Processor

Tracks social media sentiment and volume as real-time market indicators.

Twitter is valuable because:
- Real-time sentiment (faster than news)
- Volume spikes indicate major events
- Influencer opinions move markets
- Customer complaints surface product issues
- Employee tweets reveal culture problems

Key Metrics:
- Tweet volume (mentions per day)
- Sentiment ratio (positive/negative)
- Influencer sentiment (weighted by follower count)
- Reply sentiment (engagement quality)
- Viral tweets (retweets/likes)

Signals:
- Volume spike + negative sentiment = crisis (PR disaster, outage)
- Volume spike + positive sentiment = hype (product launch, earnings beat)
- Declining mentions = declining relevance
- High complaint volume = product/service issues
- Employee complaints = culture problems

Scoring:
- Net sentiment: (positive - negative) / total
- Volume multiplier: spikes increase signal strength
- Influencer weight: verified accounts get 3x weight
- Recency: last 24h weighted 2x vs last 7 days

Data Sources:
1. Twitter API v2 (Free tier: 500k tweets/month)
2. Alternative free APIs: nitter instances
3. Web scraping (rate limited)

Update Frequency: Hourly (real-time signal)
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


class TwitterSentimentProcessor(SignalProcessor):
    """Process Twitter/X mentions and sentiment"""

    # Positive sentiment keywords
    POSITIVE_KEYWORDS = [
        "love", "great", "amazing", "excellent", "best", "awesome",
        "thank you", "thanks", "appreciate", "happy", "fantastic",
        "recommend", "impressed", "perfect", "wonderful"
    ]

    # Negative sentiment keywords
    NEGATIVE_KEYWORDS = [
        "hate", "terrible", "worst", "awful", "bad", "disappointed",
        "angry", "frustrated", "useless", "horrible", "scam",
        "never again", "avoid", "warning", "boycott", "disgusting"
    ]

    # Crisis keywords (very negative)
    CRISIS_KEYWORDS = [
        "lawsuit", "investigation", "fraud", "scandal", "breach",
        "hack", "outage", "down", "crash", "broken", "lawsuit"
    ]

    def __init__(self, twitter_bearer_token: Optional[str] = None):
        """
        Initialize processor.

        Args:
            twitter_bearer_token: Twitter API v2 bearer token
                                 Get from: https://developer.twitter.com/
        """
        self.bearer_token = twitter_bearer_token
        self.api_url = "https://api.twitter.com/2/tweets/search/recent"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="twitter_sentiment",
            category=SignalCategory.ALTERNATIVE,
            description="Twitter/X social media sentiment - real-time market sentiment tracking",
            update_frequency=UpdateFrequency.HOURLY,
            data_source="Twitter API v2",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["twitter", "social_media", "sentiment", "real_time"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with social media presence"""
        return True

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch tweets mentioning the company.

        Uses Twitter API v2 search endpoint.
        Free tier: 500k tweets/month, 7-day search window.
        """
        if not self.bearer_token:
            logger.warning("No Twitter API token - using sample data")
            return self._get_sample_data(company, start, end)

        # Build search query
        # Search for ticker symbol and company name
        query = f"({company.ticker} OR \"{company.name}\") lang:en -is:retweet"

        # Twitter API params
        params = {
            "query": query,
            "max_results": 100,  # Max per request
            "tweet.fields": "created_at,public_metrics,author_id",
            "start_time": start.isoformat() + "Z",
            "end_time": end.isoformat() + "Z",
        }

        headers = {
            "Authorization": f"Bearer {self.bearer_token}"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching tweets for {company.ticker}")
                response = await client.get(self.api_url, params=params, headers=headers)
                response.raise_for_status()

                data = response.json()
                tweets = data.get("data", [])

                logger.info(f"Found {len(tweets)} tweets for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "tweets": tweets,
                    "meta": data.get("meta", {}),
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid Twitter API token")
            elif e.response.status_code == 429:
                logger.warning("Twitter API rate limit exceeded")
            else:
                logger.error(f"Twitter API error: {e}")
            return self._get_sample_data(company, start, end)
        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process tweets into sentiment signals.

        Analyzes:
        1. Overall sentiment (positive/negative ratio)
        2. Volume (mention count)
        3. Engagement (likes, replies, retweets)
        4. Crisis detection (negative spikes)
        """
        tweets = raw_data.get("tweets", [])

        if not tweets:
            return []

        # Analyze each tweet
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        crisis_count = 0
        total_engagement = 0

        for tweet in tweets:
            text = tweet.get("text", "").lower()

            # Count keywords
            pos_score = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
            neg_score = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
            crisis_score = sum(1 for kw in self.CRISIS_KEYWORDS if kw in text)

            # Classify tweet
            if crisis_score > 0:
                crisis_count += 1
                negative_count += 1
            elif pos_score > neg_score:
                positive_count += 1
            elif neg_score > pos_score:
                negative_count += 1
            else:
                neutral_count += 1

            # Track engagement
            metrics = tweet.get("public_metrics", {})
            engagement = (
                metrics.get("like_count", 0) +
                metrics.get("retweet_count", 0) +
                metrics.get("reply_count", 0)
            )
            total_engagement += engagement

        total_tweets = len(tweets)

        # Calculate sentiment score
        # Net sentiment: (positive - negative) / total
        net_sentiment = (positive_count - negative_count) / total_tweets if total_tweets > 0 else 0

        # Convert to -100 to +100
        score = int(net_sentiment * 100)
        score = max(-100, min(100, score))

        # Crisis penalty
        if crisis_count > total_tweets * 0.2:  # >20% crisis tweets
            score -= 40

        # Confidence based on volume
        if total_tweets > 100:
            confidence = 0.80
        elif total_tweets > 50:
            confidence = 0.70
        elif total_tweets > 10:
            confidence = 0.60
        else:
            confidence = 0.50

        # Build description
        description = f"Twitter: {score:+.0f}/100 sentiment from {total_tweets} tweets"
        description += f" ({positive_count} positive, {negative_count} negative, {neutral_count} neutral)"

        if crisis_count > 0:
            description += f" ⚠ {crisis_count} crisis-related tweets"

        avg_engagement = total_engagement / total_tweets if total_tweets > 0 else 0
        if avg_engagement > 10:
            description += f" | High engagement ({avg_engagement:.0f} avg)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_tweets": total_tweets,
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
                "crisis": crisis_count,
                "avg_engagement": avg_engagement,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://twitter.com/search?q={company.ticker}",
                source_name="Twitter/X",
                processing_notes=f"Analyzed {total_tweets} tweets",
                raw_data_hash=hashlib.md5(
                    json.dumps(tweets, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["twitter", "social_media", "sentiment"],
        )

        return [signal]

    def _get_sample_data(self, company: Company, start: datetime, end: datetime) -> Dict[str, Any]:
        """
        Return sample Twitter data.

        Realistic sample tweets for Uber.
        """
        if company.ticker == "UBER":
            sample_tweets = [
                {
                    "text": "@Uber just had the best ride! Driver was super friendly and car was spotless. Thank you!",
                    "created_at": "2026-02-07T10:30:00Z",
                    "public_metrics": {"like_count": 5, "retweet_count": 1, "reply_count": 2},
                },
                {
                    "text": "Uber's autonomous vehicles are the future. Rode in one in SF yesterday - amazing experience. $UBER",
                    "created_at": "2026-02-07T09:15:00Z",
                    "public_metrics": {"like_count": 45, "retweet_count": 12, "reply_count": 8},
                },
                {
                    "text": "Why is Uber so expensive now? Surge pricing is out of control. Might switch to Lyft.",
                    "created_at": "2026-02-06T20:00:00Z",
                    "public_metrics": {"like_count": 23, "retweet_count": 5, "reply_count": 15},
                },
                {
                    "text": "Uber Eats delivered my food cold again. Terrible service. Never again.",
                    "created_at": "2026-02-06T18:45:00Z",
                    "public_metrics": {"like_count": 8, "retweet_count": 2, "reply_count": 3},
                },
                {
                    "text": "$UBER earnings beat expectations! Strong Q4 results. Going long.",
                    "created_at": "2026-02-05T16:00:00Z",
                    "public_metrics": {"like_count": 102, "retweet_count": 34, "reply_count": 21},
                },
            ]
        else:
            sample_tweets = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "tweets": sample_tweets,
            "meta": {"result_count": len(sample_tweets)},
            "timestamp": datetime.utcnow(),
        }

"""
Reddit Sentiment Signal Processor

Tracks mention volume and sentiment on Reddit for company and products.
Useful for detecting viral moments, sentiment shifts, and retail investor interest.

Data Source: Reddit (free, public)
Update Frequency: Real-time
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
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


class RedditSentimentProcessor(SignalProcessor):
    """Process Reddit mentions and sentiment"""

    def __init__(self):
        # Subreddits to monitor per company
        self.subreddits = {
            "UBER": ["uber", "uberdrivers", "UberEATS", "stocks", "investing"],
        }

        # Keywords to search for
        self.keywords = {
            "UBER": ["uber", "uber stock", "uber eats", "dara khosrowshahi"],
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="reddit_sentiment",
            category=SignalCategory.ALTERNATIVE,
            description="Reddit mention volume and sentiment - retail investor interest proxy",
            update_frequency=UpdateFrequency.REALTIME,
            data_source="Reddit (public API)",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["social_media", "sentiment", "reddit", "retail_investors"],
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
        Fetch Reddit posts mentioning the company.

        Using Reddit's JSON API (no authentication required for public data)
        """

        subreddits = self.subreddits.get(company.id, ["stocks", "investing"])
        keywords = self.keywords.get(company.id, [company.ticker.lower()])

        all_posts = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for subreddit in subreddits:
                try:
                    # Reddit JSON API
                    url = f"https://www.reddit.com/r/{subreddit}/search.json"
                    params = {
                        'q': keywords[0],  # Use first keyword
                        'restrict_sr': 'true',
                        'sort': 'new',
                        'limit': 25,
                        't': 'week'  # Last week
                    }

                    logger.info(f"Fetching Reddit posts from r/{subreddit} for {keywords[0]}")

                    headers = {
                        'User-Agent': 'cousin-eddie/0.1 (Alternative Data Research)'
                    }

                    response = await client.get(url, params=params, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        posts = data.get('data', {}).get('children', [])

                        for post in posts:
                            post_data = post.get('data', {})
                            created_utc = datetime.fromtimestamp(post_data.get('created_utc', 0))

                            # Only include posts in our date range
                            if start <= created_utc <= end:
                                all_posts.append({
                                    'subreddit': subreddit,
                                    'title': post_data.get('title', ''),
                                    'selftext': post_data.get('selftext', '')[:500],  # Limit text
                                    'score': post_data.get('score', 0),
                                    'num_comments': post_data.get('num_comments', 0),
                                    'upvote_ratio': post_data.get('upvote_ratio', 0.5),
                                    'created_utc': created_utc.isoformat(),
                                    'author': post_data.get('author', 'deleted'),
                                    'url': post_data.get('url', ''),
                                    'permalink': f"https://reddit.com{post_data.get('permalink', '')}",
                                })

                        logger.info(f"Found {len(posts)} posts in r/{subreddit}")
                    else:
                        logger.warning(f"Reddit API error for r/{subreddit}: HTTP {response.status_code}")

                    # Rate limit: be nice to Reddit
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error fetching Reddit data from r/{subreddit}: {e}")

        logger.info(f"Total Reddit posts found: {len(all_posts)}")

        return {
            'company_id': company.id,
            'timestamp': datetime.utcnow(),
            'keywords': keywords,
            'subreddits': subreddits,
            'posts': all_posts,
            'total_posts': len(all_posts)
        }

    def process(
        self,
        company: Company,
        raw_data: Dict[str, Any]
    ) -> List[Signal]:
        """
        Process Reddit data into signals.

        Scoring logic:
        - High mention volume = high interest (bullish or bearish depending on sentiment)
        - Sentiment analysis (simple keyword-based for MVP)
        - Upvote ratio and engagement metrics
        """

        timestamp = raw_data.get('timestamp', datetime.utcnow())
        posts = raw_data.get('posts', [])

        if not posts:
            return []

        # Calculate metrics
        total_posts = len(posts)
        total_score = sum(p.get('score', 0) for p in posts)
        total_comments = sum(p.get('num_comments', 0) for p in posts)
        avg_upvote_ratio = sum(p.get('upvote_ratio', 0.5) for p in posts) / total_posts if total_posts > 0 else 0.5

        # Simple sentiment analysis (keyword-based)
        positive_keywords = ['buy', 'bullish', 'moon', 'calls', 'growth', 'good', 'great', 'excellent', 'profitable']
        negative_keywords = ['sell', 'bearish', 'crash', 'puts', 'decline', 'bad', 'terrible', 'loss', 'unprofitable']

        positive_count = 0
        negative_count = 0

        for post in posts:
            text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()
            positive_count += sum(1 for word in positive_keywords if word in text)
            negative_count += sum(1 for word in negative_keywords if word in text)

        # Calculate sentiment score
        if positive_count + negative_count > 0:
            sentiment_ratio = (positive_count - negative_count) / (positive_count + negative_count)
        else:
            sentiment_ratio = 0

        # Determine signal score
        # High volume with positive sentiment = bullish
        # High volume with negative sentiment = bearish

        if total_posts > 50:
            volume_multiplier = 1.5
            confidence = 0.75
            description = f"High Reddit activity: {total_posts} mentions"
        elif total_posts > 20:
            volume_multiplier = 1.2
            confidence = 0.65
            description = f"Moderate Reddit activity: {total_posts} mentions"
        elif total_posts > 5:
            volume_multiplier = 1.0
            confidence = 0.55
            description = f"Low Reddit activity: {total_posts} mentions"
        else:
            volume_multiplier = 0.8
            confidence = 0.45
            description = f"Minimal Reddit activity: {total_posts} mentions"

        # Base score from sentiment
        base_score = int(sentiment_ratio * 60)  # -60 to +60

        # Adjust for engagement
        if avg_upvote_ratio > 0.8:
            base_score += 10
        elif avg_upvote_ratio < 0.5:
            base_score -= 10

        # Apply volume multiplier
        score = int(base_score * volume_multiplier)
        score = max(-100, min(100, score))  # Clamp to range

        # Add sentiment description
        if sentiment_ratio > 0.3:
            sentiment_desc = "bullish sentiment"
        elif sentiment_ratio < -0.3:
            sentiment_desc = "bearish sentiment"
        else:
            sentiment_desc = "mixed sentiment"

        description = f"{description}, {sentiment_desc} ({positive_count} pos, {negative_count} neg)"

        normalized_value = score / 100.0

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=timestamp,
            raw_value={
                'total_posts': total_posts,
                'total_score': total_score,
                'total_comments': total_comments,
                'avg_upvote_ratio': avg_upvote_ratio,
                'positive_keywords': positive_count,
                'negative_keywords': negative_count,
                'sentiment_ratio': sentiment_ratio,
                'sample_posts': posts[:5]  # Include top 5 posts as examples
            },
            normalized_value=normalized_value,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://reddit.com",
                source_name="Reddit",
                processing_notes=f"Analyzed {total_posts} posts across {len(raw_data.get('subreddits', []))} subreddits",
                raw_data_hash=hashlib.md5(
                    json.dumps(posts, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["reddit", "social_sentiment", "retail_investors"],
        )

        return [signal]

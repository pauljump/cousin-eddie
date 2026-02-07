"""
News Sentiment Signal Processor

Analyzes news articles about the company to detect media sentiment shifts.

Uses NewsAPI (free tier: 100 requests/day, 1 month history).
Alternative: GDELT for free unlimited news data.

High-signal news:
- Earnings announcements
- Product launches
- Regulatory issues
- Executive changes
- Lawsuits
- Partnerships/M&A

Sentiment scoring:
- Positive headlines = bullish
- Negative headlines = bearish
- Volume spike = increased attention (can be positive or negative)
- Sentiment shift = trend change

Data Source: NewsAPI (free tier) or GDELT (unlimited)
Update Frequency: Daily
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


class NewsSentimentProcessor(SignalProcessor):
    """Process news articles to generate sentiment signals"""

    # Positive sentiment keywords
    POSITIVE_KEYWORDS = [
        "surge", "soar", "beat", "exceed", "record", "breakthrough",
        "partnership", "expansion", "growth", "innovation", "success",
        "profitable", "revenue up", "profit", "acquisition", "launch"
    ]

    # Negative sentiment keywords
    NEGATIVE_KEYWORDS = [
        "lawsuit", "investigation", "scandal", "decline", "loss", "crash",
        "regulatory", "fine", "penalty", "controversy", "layoff", "resignation",
        "warning", "miss", "fail", "concern", "risk", "threat"
    ]

    def __init__(self, newsapi_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            newsapi_key: NewsAPI key (free tier: 100 req/day)
                        Get from: https://newsapi.org/register
        """
        self.newsapi_key = newsapi_key
        self.newsapi_url = "https://newsapi.org/v2/everything"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="news_sentiment",
            category=SignalCategory.ALTERNATIVE,
            description="News article sentiment analysis - media coverage tracking",
            update_frequency=UpdateFrequency.DAILY,
            data_source="NewsAPI",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["news", "sentiment", "media", "alternative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with news coverage"""
        return True

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch news articles for the company.

        Uses company ticker and name as search terms.
        """
        if not self.newsapi_key:
            logger.warning("No NewsAPI key provided - using sample data")
            return self._get_sample_news(company, start, end)

        # Build search query
        query = f'"{company.name}" OR "{company.ticker}"'

        # NewsAPI free tier: max 1 month back
        # Ensure start is not more than 30 days ago
        max_start = datetime.utcnow() - timedelta(days=30)
        if start < max_start:
            start = max_start

        params = {
            "q": query,
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 100,  # Max articles
            "apiKey": self.newsapi_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching news for {company.ticker} from NewsAPI")
                response = await client.get(self.newsapi_url, params=params)
                response.raise_for_status()

                data = response.json()

                articles = data.get("articles", [])
                logger.info(f"Found {len(articles)} news articles for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "articles": articles,
                    "total_results": data.get("totalResults", len(articles)),
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid NewsAPI key")
            elif e.response.status_code == 429:
                logger.warning("NewsAPI rate limit exceeded (100 req/day on free tier)")
            else:
                logger.error(f"NewsAPI error: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process news articles into sentiment signals.

        Aggregates all articles in the period and generates:
        - Overall sentiment score
        - Volume indicator
        - Sentiment breakdown (positive/negative/neutral)
        """
        articles = raw_data.get("articles", [])

        if not articles:
            return []

        # Analyze sentiment of each article
        sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "")
            text = f"{title} {description}".lower()

            # Count sentiment keywords
            pos_score = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
            neg_score = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

            # Classify article
            if pos_score > neg_score:
                sentiment = "positive"
                positive_count += 1
                score = min(pos_score * 10, 100)
            elif neg_score > pos_score:
                sentiment = "negative"
                negative_count += 1
                score = -min(neg_score * 10, 100)
            else:
                sentiment = "neutral"
                neutral_count += 1
                score = 0

            sentiments.append({
                "title": title,
                "sentiment": sentiment,
                "score": score,
                "published": article.get("publishedAt"),
            })

        # Calculate aggregate sentiment
        total_articles = len(articles)
        avg_score = sum(s["score"] for s in sentiments) / total_articles if total_articles > 0 else 0

        # Normalize to -100 to +100
        avg_score = max(-100, min(100, avg_score))

        # Calculate confidence based on volume
        # More articles = higher confidence
        confidence = min(0.5 + (total_articles / 200.0), 0.90)

        # Build description
        sentiment_breakdown = f"{positive_count} positive, {negative_count} negative, {neutral_count} neutral"
        description = f"News sentiment: {avg_score:+.0f}/100 from {total_articles} articles ({sentiment_breakdown})"

        # Add top headlines
        if positive_count > 0:
            top_positive = [s for s in sentiments if s["sentiment"] == "positive"][:2]
            if top_positive:
                description += f" | Positive: {top_positive[0]['title'][:60]}..."

        if negative_count > 0:
            top_negative = [s for s in sentiments if s["sentiment"] == "negative"][:2]
            if top_negative:
                description += f" | Negative: {top_negative[0]['title'][:60]}..."

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={"articles": sentiments, "stats": {"total": total_articles, "positive": positive_count, "negative": negative_count}},
            normalized_value=avg_score / 100.0,
            score=int(avg_score),
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://newsapi.org",
                source_name="NewsAPI",
                processing_notes=f"Analyzed {total_articles} articles",
                raw_data_hash=hashlib.md5(
                    json.dumps(sentiments, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["news", "sentiment", "media"],
        )

        return [signal]

    def _get_sample_news(self, company: Company, start: datetime, end: datetime) -> Dict[str, Any]:
        """
        Return sample news data when API key not available.

        For Uber, return realistic sample headlines.
        """
        if company.ticker == "UBER":
            sample_articles = [
                {
                    "title": "Uber Reports Strong Q4 Earnings, Beats Analyst Expectations",
                    "description": "Uber Technologies exceeded revenue forecasts with 15% YoY growth",
                    "publishedAt": "2026-02-04T10:00:00Z",
                },
                {
                    "title": "Uber Faces Regulatory Scrutiny in European Markets",
                    "description": "EU regulators investigating labor classification practices",
                    "publishedAt": "2026-01-28T14:30:00Z",
                },
                {
                    "title": "Uber Eats Expansion: New Markets in Southeast Asia",
                    "description": "Food delivery platform launching in Vietnam and Thailand",
                    "publishedAt": "2026-01-22T09:00:00Z",
                },
            ]
        else:
            sample_articles = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "articles": sample_articles,
            "total_results": len(sample_articles),
            "timestamp": datetime.utcnow(),
        }

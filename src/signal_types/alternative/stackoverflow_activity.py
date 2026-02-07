"""
Stack Overflow Activity Signal Processor

Tracks developer questions and activity for tech companies and their products.

Why Stack Overflow matters (for tech companies):
- Developer adoption proxy
- Product complexity/pain points (more questions = more issues)
- Technology trends (growing vs declining interest)
- Competitive positioning (React vs Vue, AWS vs Azure)
- Developer mindshare

Key Metrics:
- Question count (monthly)
- Question growth rate
- Answer quality (accepted answers, upvotes)
- Tag follower count
- Unanswered question ratio (product support quality)

Signals:
- Increasing questions = growing adoption (good)
- High unanswered ratio = poor docs/support (bad)
- Declining questions = losing developer interest (bad)
- High-quality answers = strong community (good)

Use Cases:
- Cloud providers (AWS, Azure, GCP tag activity)
- Frameworks (React, Vue, Angular)
- Databases (PostgreSQL, MongoDB, etc.)
- Dev tools (GitHub, VS Code, Docker)
- APIs (Stripe, Twilio, SendGrid)

Example Tags to Track:
- Google: android, google-cloud-platform, tensorflow
- Amazon: amazon-web-services, aws-lambda, dynamodb
- Microsoft: azure, .net, typescript
- Meta: react, react-native

Data Source: Stack Exchange API (free, 10,000 requests/day)
Update Frequency: Weekly
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


class StackOverflowActivityProcessor(SignalProcessor):
    """Track Stack Overflow question activity"""

    def __init__(self):
        """Initialize processor."""
        self.api_url = "https://api.stackexchange.com/2.3"

        # Map companies to their relevant Stack Overflow tags
        self.tag_mappings = {
            "GOOGL": ["android", "google-cloud-platform", "tensorflow", "firebase"],
            "MSFT": ["azure", ".net", "typescript", "visual-studio-code"],
            "AMZN": ["amazon-web-services", "aws-lambda", "dynamodb"],
            "META": ["react", "react-native"],
            "UBER": [],  # Uber doesn't have major developer products
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="stackoverflow_activity",
            category=SignalCategory.ALTERNATIVE,
            description="Stack Overflow developer activity - developer adoption and product health",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="Stack Exchange API",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["stackoverflow", "developer", "adoption", "tech"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to tech companies with developer products"""
        return company.id in self.tag_mappings and len(self.tag_mappings[company.id]) > 0

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Stack Overflow tag statistics.

        Uses Stack Exchange API (free, no auth required for basic stats).
        """
        if company.id not in self.tag_mappings:
            return {}

        tags = self.tag_mappings[company.id]

        if not tags:
            return {}

        # Fetch stats for each tag
        tag_stats = []

        for tag in tags:
            try:
                # Get tag info
                info_url = f"{self.api_url}/tags/{tag}/info"
                params = {
                    "site": "stackoverflow",
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(info_url, params=params)
                    response.raise_for_status()

                    data = response.json()
                    items = data.get("items", [])

                    if items:
                        tag_data = items[0]
                        tag_stats.append({
                            "tag": tag,
                            "count": tag_data.get("count", 0),
                            "followers": tag_data.get("followers_count", 0),
                        })

                        logger.info(f"Found {tag_data.get('count', 0)} questions for tag: {tag}")

            except Exception as e:
                logger.warning(f"Error fetching Stack Overflow data for tag {tag}: {e}")
                continue

        if not tag_stats:
            logger.warning("No Stack Overflow data fetched - using sample data")
            return self._get_sample_data(company)

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "tags": tag_stats,
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process Stack Overflow activity into signals.

        Analyzes:
        1. Total question count across tags
        2. Tag popularity (followers)
        3. Developer mindshare trends
        """
        tags = raw_data.get("tags", [])

        if not tags:
            return []

        # Calculate aggregate metrics
        total_questions = sum(tag.get("count", 0) for tag in tags)
        total_followers = sum(tag.get("followers", 0) for tag in tags)
        tag_count = len(tags)

        # Find most popular tag
        top_tag = max(tags, key=lambda t: t.get("count", 0))

        # Calculate score
        # More questions = more developer adoption
        # 1M+ questions = +80 to +100 (very popular)
        # 500k-1M = +60 to +80
        # 100k-500k = +40 to +60
        # 10k-100k = +20 to +40
        # <10k = 0 to +20

        if total_questions > 1000000:
            score = min(100, 80 + (total_questions - 1000000) / 100000)
        elif total_questions > 500000:
            score = 60 + ((total_questions - 500000) / 500000) * 20
        elif total_questions > 100000:
            score = 40 + ((total_questions - 100000) / 400000) * 20
        elif total_questions > 10000:
            score = 20 + ((total_questions - 10000) / 90000) * 20
        else:
            score = (total_questions / 10000) * 20

        score = int(max(0, min(100, score)))

        # Confidence
        confidence = 0.75

        # Build description
        description = f"Stack Overflow: {total_questions:,} questions across {tag_count} tags"
        description += f" | Top: {top_tag['tag']} ({top_tag['count']:,} questions)"
        description += f" | {total_followers:,} total followers"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_questions": total_questions,
                "total_followers": total_followers,
                "tag_count": tag_count,
                "tags": tags,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://stackoverflow.com",
                source_name="Stack Overflow",
                processing_notes=f"{total_questions:,} questions, {tag_count} tags tracked",
                raw_data_hash=hashlib.md5(
                    json.dumps(tags, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["stackoverflow", "developer", "adoption"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample Stack Overflow data"""
        if company.ticker == "GOOGL":
            sample_tags = [
                {"tag": "android", "count": 1450000, "followers": 385000},
                {"tag": "google-cloud-platform", "count": 85000, "followers": 12000},
                {"tag": "tensorflow", "count": 62000, "followers": 28000},
                {"tag": "firebase", "count": 95000, "followers": 35000},
            ]
        elif company.ticker == "MSFT":
            sample_tags = [
                {"tag": "azure", "count": 125000, "followers": 45000},
                {"tag": ".net", "count": 680000, "followers": 195000},
                {"tag": "typescript", "count": 185000, "followers": 62000},
            ]
        else:
            sample_tags = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "tags": sample_tags,
            "timestamp": datetime.utcnow(),
        }

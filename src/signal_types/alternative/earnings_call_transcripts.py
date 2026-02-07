"""
Earnings Call Transcript Signal Processor

Analyzes earnings call transcripts for sentiment, confidence, and keyword signals.

Earnings calls reveal critical information beyond the numbers:
- Management tone and confidence
- Forward guidance language (optimistic vs cautious)
- Question topics from analysts (concerns, opportunities)
- Management evasiveness (dodging questions)
- Key initiatives and strategic shifts
- Risk mentions and challenges

High-signal keywords:
Positive:
- "accelerating", "momentum", "outperform", "exceeded", "record"
- "investing", "expansion", "opportunity", "confident"

Negative:
- "headwinds", "challenges", "difficult", "uncertainty", "pressure"
- "weakness", "decline", "slower", "concerned", "cautious"

Scoring:
- Positive sentiment + strong guidance = bullish
- Negative sentiment + weak guidance = bearish
- Evasive answers = bearish (hiding problems)
- Mentions of "restructuring", "layoffs", "cost cuts" = bearish

Data Sources:
1. SEC 8-K exhibits (official transcripts)
2. AlphaVantage (free tier: 25 calls/day)
3. Seeking Alpha (scraping)
4. Company investor relations sites

Update Frequency: Quarterly (after earnings releases)
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


class EarningsCallTranscriptProcessor(SignalProcessor):
    """Analyze earnings call transcripts for sentiment signals"""

    # Positive sentiment keywords
    POSITIVE_KEYWORDS = [
        "accelerating", "momentum", "outperform", "exceeded", "record",
        "strong", "growth", "investing", "expansion", "opportunity",
        "confident", "optimistic", "excited", "pleased", "robust",
        "beating expectations", "ahead of schedule", "market share gains"
    ]

    # Negative sentiment keywords
    NEGATIVE_KEYWORDS = [
        "headwinds", "challenges", "difficult", "uncertainty", "pressure",
        "weakness", "decline", "slower", "concerned", "cautious",
        "disappointed", "miss", "shortfall", "struggling", "competitive pressure",
        "restructuring", "layoffs", "cost cuts", "margin compression"
    ]

    # Evasive/hedging language (suggests hiding problems)
    EVASIVE_KEYWORDS = [
        "we'll get back to you", "can't comment", "difficult to say",
        "uncertain environment", "hard to predict", "wait and see",
        "too early to tell", "monitoring closely"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            api_key: API key for transcript provider (e.g., AlphaVantage)
        """
        self.api_key = api_key

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="earnings_call_transcripts",
            category=SignalCategory.ALTERNATIVE,
            description="Earnings call sentiment analysis - management tone and guidance",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC 8-K / AlphaVantage",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["earnings_call", "sentiment", "management", "alternative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all public companies that hold earnings calls"""
        return company.has_sec_filings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch earnings call transcripts.

        Sources:
        1. SEC 8-K filings (Item 2.02 often includes transcript as exhibit)
        2. AlphaVantage API (if key provided)
        3. Sample data (for POC)

        For POC, we use sample data.
        """
        logger.warning("Earnings call API not configured - using sample data")
        return self._get_sample_data(company, start, end)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process earnings call transcript into signals.

        Analyzes:
        1. Overall sentiment (positive vs negative keywords)
        2. Management confidence (tone, hedging language)
        3. Guidance strength (forward-looking statements)
        4. Key themes and concerns
        """
        transcript = raw_data.get("transcript", "")
        call_date = raw_data.get("call_date")
        quarter = raw_data.get("quarter", "")

        if not transcript:
            return []

        # Analyze transcript
        analysis = self._analyze_transcript(transcript)

        # Calculate overall sentiment score
        pos_count = analysis["positive_keyword_count"]
        neg_count = analysis["negative_keyword_count"]
        evasive_count = analysis["evasive_keyword_count"]

        # Base score from sentiment keywords
        # Positive words = +5 each, negative words = -5 each, evasive = -3 each
        score = (pos_count * 5) - (neg_count * 5) - (evasive_count * 3)

        # Normalize to -100 to +100
        score = max(-100, min(100, score))

        # Confidence based on transcript length (more words = better sample)
        word_count = len(transcript.split())
        if word_count > 10000:
            confidence = 0.80
        elif word_count > 5000:
            confidence = 0.70
        elif word_count > 2000:
            confidence = 0.60
        else:
            confidence = 0.50

        # Build description
        description = f"Earnings call {quarter}: {score:+.0f}/100 sentiment"
        if pos_count > neg_count:
            description += f" (Positive: {', '.join(analysis['top_positive'][:3])})"
        elif neg_count > pos_count:
            description += f" (Negative: {', '.join(analysis['top_negative'][:3])})"

        if evasive_count > 3:
            description += " ⚠ Evasive language detected"

        # Parse call date
        if isinstance(call_date, str):
            timestamp = datetime.fromisoformat(call_date.replace("Z", "+00:00"))
        else:
            timestamp = call_date or datetime.utcnow()

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=timestamp,
            raw_value=analysis,
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=8-K",
                source_name="Earnings Call Transcript",
                processing_notes=f"{word_count:,} words analyzed | {pos_count} positive, {neg_count} negative, {evasive_count} evasive",
                raw_data_hash=hashlib.md5(
                    json.dumps(analysis, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["earnings_call", "sentiment", quarter.lower().replace(" ", "_")],
        )

        return [signal]

    def _analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Analyze transcript for sentiment keywords.

        Returns:
        - positive_keyword_count
        - negative_keyword_count
        - evasive_keyword_count
        - top_positive: list of found positive keywords
        - top_negative: list of found negative keywords
        - key_themes: extracted topics/phrases
        """
        text = transcript.lower()

        # Find positive keywords
        positive_matches = []
        for keyword in self.POSITIVE_KEYWORDS:
            pattern = rf'\b{re.escape(keyword)}\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                positive_matches.append((keyword, len(matches)))

        # Find negative keywords
        negative_matches = []
        for keyword in self.NEGATIVE_KEYWORDS:
            pattern = rf'\b{re.escape(keyword)}\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                negative_matches.append((keyword, len(matches)))

        # Find evasive keywords
        evasive_matches = []
        for keyword in self.EVASIVE_KEYWORDS:
            if keyword in text:  # Some are phrases, not just words
                evasive_matches.append(keyword)

        return {
            "positive_keyword_count": sum(count for _, count in positive_matches),
            "negative_keyword_count": sum(count for _, count in negative_matches),
            "evasive_keyword_count": len(evasive_matches),
            "top_positive": [kw for kw, _ in sorted(positive_matches, key=lambda x: x[1], reverse=True)[:5]],
            "top_negative": [kw for kw, _ in sorted(negative_matches, key=lambda x: x[1], reverse=True)[:5]],
            "evasive_phrases": evasive_matches,
        }

    def _get_sample_data(self, company: Company, start: datetime, end: datetime) -> Dict[str, Any]:
        """
        Return sample earnings call transcript data.

        In production, this would fetch actual transcripts from SEC, AlphaVantage, or Seeking Alpha.
        """
        if company.ticker == "UBER":
            # Sample transcript snippet (realistic Q4 2025 call)
            sample_transcript = """
            Good afternoon, and welcome to Uber's Q4 2025 earnings call. I'm Dara Khosrowshahi, CEO of Uber.

            We're pleased to report another strong quarter with revenue growth of 15% year-over-year, exceeding
            analyst expectations. Our mobility business continues to show momentum with record trip volumes, and
            Uber Eats delivered robust performance across all markets.

            Key highlights:
            - Gross bookings grew 18% YoY to $37.6B
            - Adjusted EBITDA margin expanded 200 basis points
            - Free cash flow exceeded $1.5B for the quarter
            - Monthly active platform consumers reached 156M

            We're excited about our expansion into autonomous vehicles. Our partnership with Waymo is accelerating,
            with AV trips now representing 5% of rides in San Francisco and Phoenix. This is a clear competitive
            advantage as we invest in the future of mobility.

            Looking ahead to 2026, we're confident in our ability to maintain double-digit growth. We see significant
            opportunities in international markets, particularly in Southeast Asia and Latin America. Our freight
            business is also showing strong momentum with enterprise customer wins.

            However, we do face some headwinds. Regulatory challenges in Europe continue, with new labor classification
            rules creating uncertainty. We're also monitoring macroeconomic conditions closely, as consumer spending
            patterns could impact our business in a potential recession.

            That said, we remain optimistic about our long-term growth trajectory. We're investing heavily in technology,
            expanding our platform, and executing on our strategy to become the operating system for everyday life.

            Now I'll turn it over to our CFO Nelson Chai for the financial details...

            [Q&A Session]

            Analyst: Can you provide more color on the European regulatory situation?
            Dara: It's difficult to say exactly how this will play out. We're monitoring closely and working with
            regulators, but it's too early to tell what the full impact will be.

            Analyst: What's your outlook on autonomous vehicle economics?
            Dara: We're very pleased with the early results. The unit economics are improving rapidly, and we're
            excited about the potential. This positions us ahead of competitors in the AV race.
            """

            return {
                "company_id": company.id,
                "ticker": company.ticker,
                "transcript": sample_transcript,
                "call_date": "2026-02-05T16:30:00Z",
                "quarter": "Q4 2025",
                "timestamp": datetime.utcnow(),
            }
        else:
            return {
                "company_id": company.id,
                "ticker": company.ticker,
                "transcript": "",
                "timestamp": datetime.utcnow(),
            }

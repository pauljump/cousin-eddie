"""
SEC MD&A (Management Discussion & Analysis) Processor

Extracts and analyzes MD&A sections from 10-K and 10-Q filings.

MD&A is where management discusses:
- Business performance and results of operations
- Forward-looking statements and guidance
- Liquidity and capital resources
- Critical accounting policies
- Risk factors and uncertainties

We extract this rich narrative text and generate signals based on:
1. Sentiment (bullish/bearish tone)
2. Key topics and themes (revenue growth, margins, competition, etc.)
3. Forward guidance mentions
4. Changes from prior period MD&A
"""

import re
import json
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
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


class SECMDAProcessor(SignalProcessor):
    """Extract and analyze MD&A from 10-K/10-Q filings"""

    CATEGORY = "regulatory"
    DATA_URL = "https://data.sec.gov"  # For JSON APIs
    DOC_URL = "https://www.sec.gov"    # For document downloads

    # MD&A section headers to look for
    MDA_HEADERS = [
        "management's discussion and analysis",
        "management discussion and analysis",
        "md&a",
        "item 2. management's discussion",
        "item 7. management's discussion",
    ]

    # Sentiment keywords
    POSITIVE_KEYWORDS = [
        "growth", "strong", "increased", "improve", "expansion", "success",
        "profitable", "opportunity", "gain", "positive", "exceed", "outperform",
        "momentum", "acceleration", "robust", "favorable", "optimistic"
    ]

    NEGATIVE_KEYWORDS = [
        "decline", "decrease", "weak", "challenge", "difficult", "concern",
        "risk", "uncertainty", "loss", "negative", "pressure", "headwind",
        "contraction", "slow", "deteriorate", "adverse", "unfavorable"
    ]

    GUIDANCE_KEYWORDS = [
        "expect", "anticipate", "forecast", "guidance", "outlook",
        "project", "estimate", "believe", "intend", "plan", "target"
    ]

    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": "Alternative Data Platform research@example.com"},
            timeout=30.0,
            follow_redirects=True,
        )

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_mda",
            category=SignalCategory.REGULATORY,
            description="Management Discussion & Analysis from 10-K/10-Q filings",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC EDGAR Filings",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["mda", "sec", "10-k", "10-q", "sentiment", "narrative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all US public companies with SEC filings"""
        return hasattr(company, 'cik') and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        """Fetch MD&A data from recent 10-K/10-Q filings"""
        logger.info(f"Fetching MD&A for {company.ticker}")

        if not company.cik:
            logger.warning(f"No CIK for {company.ticker}, skipping MD&A")
            return {}

        # Get recent filings
        filings = self._get_recent_filings(company.cik, form_types=["10-K", "10-Q"])

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "cik": company.cik,
            "filings": filings[:4],  # Last 4 filings (1 year for quarterly)
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """Process MD&A raw data into signals"""
        logger.info(f"Processing MD&A for {company.ticker}")

        filings = raw_data.get("filings", [])
        if not filings:
            return []

        signals = []

        for filing in filings:
            try:
                signal = self._process_filing(company, filing)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error processing {filing['form']} from {filing['filing_date']}: {e}")
                continue

        return signals

    def _get_recent_filings(self, cik: str, form_types: List[str]) -> List[Dict]:
        """Get recent 10-K/10-Q filings for a company"""
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)

        url = f"{self.DATA_URL}/submissions/CIK{cik_padded}.json"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Error fetching submissions for CIK {cik}: {e}")
            return []

        # Extract recent filings
        recent_filings = data.get("filings", {}).get("recent", {})

        if not recent_filings:
            return []

        filings = []

        for i in range(len(recent_filings.get("form", []))):
            form = recent_filings["form"][i]

            if form in form_types:
                filings.append({
                    "form": form,
                    "filing_date": recent_filings["filingDate"][i],
                    "accession_number": recent_filings["accessionNumber"][i],
                    "primary_document": recent_filings["primaryDocument"][i],
                })

        return filings

    def _process_filing(self, company: Company, filing: Dict) -> Optional[Signal]:
        """Extract and analyze MD&A from a single filing"""
        logger.info(f"Processing {filing['form']} from {filing['filing_date']}")

        # Download filing HTML
        mda_text = self._extract_mda(company.cik, filing)

        if not mda_text or len(mda_text) < 500:  # Need substantial content
            logger.warning(f"MD&A too short or not found for {filing['form']}")
            return None

        # Analyze MD&A content
        analysis = self._analyze_mda(mda_text)

        # Generate signal score based on sentiment
        score = self._calculate_sentiment_score(analysis)

        # Create description
        description = self._create_description(filing, analysis)

        # Parse filing date
        filing_date = datetime.strptime(filing["filing_date"], "%Y-%m-%d")

        # Prepare raw_value
        raw_value = {
            "form": filing["form"],
            "filing_date": filing["filing_date"],
            "sentiment": analysis["sentiment"],
            "positive_count": analysis["positive_count"],
            "negative_count": analysis["negative_count"],
            "guidance_mentions": analysis["guidance_count"],
            "word_count": analysis["word_count"],
            "key_topics": analysis.get("topics", []),
        }

        # Calculate hash
        raw_hash = hashlib.md5(
            json.dumps(raw_value, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Normalize score from -100/+100 to -1.0/+1.0
        normalized_value = score / 100.0

        return Signal(
            company_id=company.id,
            signal_type=f"mda_{filing['form'].lower().replace('-', '')}",  # mda_10k or mda_10q
            category=SignalCategory.REGULATORY,
            timestamp=filing_date,
            raw_value=raw_value,
            normalized_value=normalized_value,
            score=score,
            confidence=0.75,  # Text analysis has medium-high confidence
            metadata=SignalMetadata(
                source_url=f"{self.DOC_URL}/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type={filing['form']}",
                source_name="SEC EDGAR",
                processing_notes=f"{filing['form']} MD&A sentiment analysis - {analysis['sentiment']}",
                raw_data_hash=raw_hash,
            ),
            description=description,
        )

    def _extract_mda(self, cik: str, filing: Dict) -> Optional[str]:
        """Extract MD&A text from filing HTML"""
        # Build URL to filing
        accession = filing["accession_number"].replace("-", "")
        doc = filing["primary_document"]

        # Remove leading zeros from CIK for URL
        cik_clean = str(int(cik))

        url = f"{self.DOC_URL}/Archives/edgar/data/{cik_clean}/{accession}/{doc}"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.error(f"Error fetching filing document: {e}")
            return None

        # Parse HTML
        soup = BeautifulSoup(html, "lxml")

        # Try to find MD&A section
        mda_text = self._find_mda_section(soup)

        return mda_text

    def _find_mda_section(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Find MD&A section in filing HTML.

        Strategy:
        1. Look for section headers matching MD&A patterns
        2. Extract text from that section until next major section
        3. Clean and normalize text
        """
        # Get all text
        text = soup.get_text()

        # Find MD&A section start
        mda_start = None

        for header in self.MDA_HEADERS:
            pattern = re.compile(header, re.IGNORECASE)
            match = pattern.search(text)

            if match:
                mda_start = match.start()
                break

        if not mda_start:
            logger.warning("Could not find MD&A section")
            return None

        # Find section end (next major Item or end of document)
        # Typical ending markers: "Item 3.", "Item 8.", etc.
        end_pattern = re.compile(r"item\s+\d+\.", re.IGNORECASE)
        end_matches = list(end_pattern.finditer(text[mda_start + 100:]))  # Skip first 100 chars

        if end_matches:
            mda_end = mda_start + 100 + end_matches[0].start()
        else:
            # Take next 50,000 characters (about 8,000-10,000 words)
            mda_end = min(mda_start + 50000, len(text))

        mda_text = text[mda_start:mda_end]

        # Clean text
        mda_text = self._clean_text(mda_text)

        return mda_text

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excess whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove common SEC filing artifacts
        text = re.sub(r'Table of Contents', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+', '', text)  # Remove numbers (can add noise to sentiment)

        return text.strip()

    def _analyze_mda(self, text: str) -> Dict[str, Any]:
        """Analyze MD&A text for sentiment and themes"""
        text_lower = text.lower()

        # Count positive/negative keywords
        positive_count = sum(text_lower.count(word) for word in self.POSITIVE_KEYWORDS)
        negative_count = sum(text_lower.count(word) for word in self.NEGATIVE_KEYWORDS)

        # Count forward guidance mentions
        guidance_count = sum(text_lower.count(word) for word in self.GUIDANCE_KEYWORDS)

        # Calculate sentiment ratio
        total_sentiment_words = positive_count + negative_count

        if total_sentiment_words > 0:
            sentiment_ratio = (positive_count - negative_count) / total_sentiment_words
        else:
            sentiment_ratio = 0.0

        # Determine sentiment category
        if sentiment_ratio > 0.2:
            sentiment = "bullish"
        elif sentiment_ratio < -0.2:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        # Word count
        word_count = len(text.split())

        # Extract key topics (simple frequency analysis)
        topics = self._extract_topics(text_lower)

        return {
            "sentiment": sentiment,
            "sentiment_ratio": sentiment_ratio,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "guidance_count": guidance_count,
            "word_count": word_count,
            "topics": topics,
        }

    def _extract_topics(self, text: str) -> List[str]:
        """Extract key topics from text (simple keyword frequency)"""
        # Business topics to track
        topic_keywords = {
            "revenue": ["revenue", "sales"],
            "profitability": ["profit", "margin", "earnings"],
            "cash_flow": ["cash flow", "liquidity"],
            "growth": ["growth", "expansion"],
            "competition": ["competition", "competitive", "competitor"],
            "regulation": ["regulation", "regulatory", "compliance"],
            "technology": ["technology", "innovation", "digital"],
            "customer": ["customer", "user", "rider", "driver"],  # Uber-specific
        }

        topics = []

        for topic, keywords in topic_keywords.items():
            count = sum(text.count(kw) for kw in keywords)
            if count > 5:  # Threshold for significance
                topics.append(topic)

        return topics[:5]  # Top 5 topics

    def _calculate_sentiment_score(self, analysis: Dict) -> int:
        """
        Calculate signal score (-100 to +100) from sentiment analysis.

        Scoring:
        - Bullish sentiment: +40 to +70
        - Neutral sentiment: -20 to +20
        - Bearish sentiment: -70 to -40
        """
        sentiment_ratio = analysis["sentiment_ratio"]

        # Scale ratio (-1 to +1) to score (-100 to +100)
        # Multiply by 60 to get range of -60 to +60, then add modifiers

        base_score = int(sentiment_ratio * 60)

        # Boost score if there's forward guidance (shows confidence)
        guidance_boost = min(analysis["guidance_count"] // 3, 15)  # Up to +15

        score = base_score + guidance_boost

        # Clamp to -100 to +100
        score = max(-100, min(100, score))

        return score

    def _create_description(self, filing: Dict, analysis: Dict) -> str:
        """Create human-readable description"""
        sentiment = analysis["sentiment"].upper()
        word_count = analysis["word_count"]
        guidance = analysis["guidance_count"]

        topics_str = ", ".join(analysis["topics"]) if analysis["topics"] else "general business"

        return (
            f"{filing['form']} MD&A: {sentiment} sentiment "
            f"({word_count:,} words, {guidance} guidance mentions). "
            f"Key topics: {topics_str}"
        )


if __name__ == "__main__":
    import asyncio
    from ...core.company import get_registry

    async def test():
        registry = get_registry()
        uber = registry.get("UBER")

        processor = SECMDAProcessor()
        signals = await processor.process(uber)

        for signal in signals:
            print(f"\n{signal.description}")
            print(f"Score: {signal.score:+d}")
            print(f"Raw: {signal.raw_value}")

    asyncio.run(test())

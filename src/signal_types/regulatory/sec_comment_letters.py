"""
SEC Comment Letters Signal Processor

Tracks SEC comment letters sent to companies about their filings.

Why comment letters matter:
- SEC questions revenue recognition = potential restatement risk
- Repeated queries = red flags about accounting practices
- Harsh tone = serious concerns (bearish)
- Quick resolution = minor issues (neutral)
- These are PUBLIC but rarely monitored by traders

From ChatGPT Research:
"After major filings, the SEC often issues comment letters to companies, which
become public. These letters may question revenue recognition, or request clarity
on an obscure issue. They're posted on SEC's site but seldom read by traders.
A spike in tough questions from the SEC (e.g. repeated queries on a company's
revenue booking) can foreshadow future restatements or slowing growth – an
opportunity to go short early."

Key Signals:
- Number of comment letters (frequency)
- Severity of questions (accounting vs routine)
- Response quality (evasive vs transparent)
- Time to resolution
- Topics: revenue recognition, off-balance sheet, goodwill

Red Flags:
- Revenue recognition questions = MAJOR WARNING
- Goodwill impairment questions = asset quality issues
- Related party transactions = governance concerns
- Multiple rounds of comments = serious problems
- Late responses = hiding issues

Data Source: SEC EDGAR Correspondence
Update Frequency: Monthly (letters posted periodically)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json
import re

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


class SECCommentLettersProcessor(SignalProcessor):
    """Track SEC comment letters and responses"""

    # High-severity topics
    HIGH_SEVERITY_TOPICS = [
        "revenue recognition",
        "restatement",
        "goodwill impairment",
        "off-balance sheet",
        "related party transaction",
        "going concern",
        "internal controls",
        "material weakness",
        "accounting policy",
        "reserves",
    ]

    MODERATE_SEVERITY_TOPICS = [
        "disclosure",
        "footnote",
        "segment reporting",
        "tax provision",
        "contingencies",
        "stock compensation",
    ]

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent
        """
        self.user_agent = user_agent
        self.base_url = "https://www.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_comment_letters",
            category=SignalCategory.REGULATORY,
            description="SEC comment letters - accounting quality and red flags",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="SEC EDGAR Correspondence",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["sec", "comment_letters", "accounting", "red_flags"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch SEC comment letters for company.

        SEC posts correspondence at:
        https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=XXXX&type=UPLOAD&dateb=&owner=exclude&count=100
        """
        if not company.cik:
            logger.warning(f"No CIK for {company.id}")
            return {}

        cik = company.cik.zfill(10)

        # Search for correspondence (UPLOAD type = comment letters)
        url = f"{self.base_url}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": cik,
            "type": "UPLOAD",
            "dateb": "",
            "owner": "exclude",
            "count": "100",
        }

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                logger.info(f"Fetching SEC comment letters for {company.ticker}")
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()

                # Parse HTML to find correspondence links
                soup = BeautifulSoup(response.text, "html.parser")

                # Find correspondence table
                # Note: This is a simplified scraper - production would need robust parsing
                correspondence = []

                # For POC, return sample data
                logger.warning("SEC correspondence scraping not fully implemented - using sample data")
                return self._get_sample_data(company)

        except Exception as e:
            logger.error(f"Error fetching comment letters: {e}")
            return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process comment letters into signals.

        Analyzes:
        1. Number of letters (frequency)
        2. Topics mentioned (severity)
        3. Response quality
        """
        letters = raw_data.get("letters", [])

        if not letters:
            return []

        # Count by severity
        high_severity_count = 0
        moderate_severity_count = 0
        total_questions = 0

        for letter in letters:
            content = letter.get("content", "").lower()

            # Count high-severity topics
            for topic in self.HIGH_SEVERITY_TOPICS:
                if topic in content:
                    high_severity_count += content.count(topic)

            # Count moderate-severity topics
            for topic in self.MODERATE_SEVERITY_TOPICS:
                if topic in content:
                    moderate_severity_count += content.count(topic)

            # Count total questions (rough proxy)
            total_questions += content.count("please")

        # Calculate score
        # High-severity questions = very negative
        # Multiple letters = negative
        # Revenue recognition questions = MAJOR RED FLAG

        score = 0

        # Base penalty for having letters at all
        if len(letters) > 0:
            score -= 10 * len(letters)

        # Severe penalty for high-severity topics
        score -= high_severity_count * 20

        # Moderate penalty for moderate topics
        score -= moderate_severity_count * 5

        # Normalize to -100 to +100
        score = max(-100, min(0, score))

        # Confidence
        confidence = 0.85  # Comment letters are strong signals

        # Build description
        description = f"SEC comment letters: {len(letters)} letter(s)"

        if high_severity_count > 0:
            description += f" | ⚠️ {high_severity_count} high-severity issues"

        if moderate_severity_count > 0:
            description += f" | {moderate_severity_count} moderate issues"

        # Flag specific red flags
        revenue_recognition = sum(1 for l in letters if "revenue recognition" in l.get("content", "").lower())
        if revenue_recognition > 0:
            description += " | 🚨 REVENUE RECOGNITION QUESTIONED"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "letter_count": len(letters),
                "high_severity_count": high_severity_count,
                "moderate_severity_count": moderate_severity_count,
                "total_questions": total_questions,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={raw_data.get('cik')}&type=UPLOAD",
                source_name="SEC Comment Letters",
                processing_notes=f"{len(letters)} letters, {high_severity_count} high-severity",
                raw_data_hash=hashlib.md5(
                    json.dumps(letters, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["sec", "comment_letters", "accounting"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample comment letter data"""

        if company.ticker == "UBER":
            # Sample: Clean company, no major issues
            sample_letters = []
        else:
            sample_letters = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "cik": company.cik,
            "letters": sample_letters,
            "timestamp": datetime.utcnow(),
        }

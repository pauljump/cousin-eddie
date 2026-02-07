"""
SEC Footnote Deep Analysis Signal Processor

Tracks changes in 10-K/10-Q footnotes year-over-year.

Why footnotes matter (from ChatGPT research):
"While MD&A gets some attention, the detailed footnotes in 10-K/10-Q often
harbor crucial info (off-balance sheet obligations, pension assumptions,
revenue recognition changes). Most investors gloss over them, yet research
finds footnote textual features can predict future returns – investors largely
ignore them. A tool that diff-checks footnotes year-over-year to spot 'hidden'
changes (like new legal risks or aggressive accounting) can give a solo trader
a unique warning signal."

Key Red Flags in Footnotes:
- Revenue recognition policy changes
- Off-balance sheet obligations appearing/growing
- Pension assumption changes (discount rate, return assumptions)
- Goodwill impairment testing changes
- Related party transactions
- Contingent liabilities
- Debt covenant violations or waivers
- Accounting estimate changes

Signals:
- New footnotes added = potential hidden risk
- Footnote length increasing = more disclosures needed (bad)
- Accounting policy changes = manipulation risk
- Legal footnote expansion = litigation exposure

Data Source: SEC EDGAR 10-K/10-Q
Update Frequency: Quarterly
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json
import re
from difflib import unified_diff

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


class SECFootnoteAnalysisProcessor(SignalProcessor):
    """Deep analysis of 10-K/10-Q footnotes"""

    # Red flag keywords in footnotes
    RED_FLAG_KEYWORDS = [
        "restatement",
        "change in accounting",
        "off-balance sheet",
        "related party",
        "contingent liability",
        "covenant violation",
        "covenant waiver",
        "going concern",
        "material uncertainty",
        "goodwill impairment",
        "pension assumption",
        "reserve release",
        "aggressive",
    ]

    # Key footnote sections to monitor
    CRITICAL_FOOTNOTES = [
        "revenue recognition",
        "significant accounting policies",
        "goodwill and intangible assets",
        "debt",
        "commitments and contingencies",
        "related party transactions",
        "income taxes",
        "pension",
        "stock-based compensation",
        "fair value measurements",
    ]

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """Initialize processor."""
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_footnote_analysis",
            category=SignalCategory.REGULATORY,
            description="Deep 10-K/10-Q footnote analysis - hidden accounting risks",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["sec", "footnotes", "accounting", "red_flags"],
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
        Fetch 10-K/10-Q filings and extract footnotes.

        For POC, use sample data.
        Production would parse full HTML/XBRL filings.
        """
        if not company.cik:
            return {}

        logger.warning("Footnote extraction not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process footnote changes into signals.

        Compares current vs previous period footnotes.
        """
        current_footnotes = raw_data.get("current_footnotes", {})
        previous_footnotes = raw_data.get("previous_footnotes", {})

        if not current_footnotes:
            return []

        # Analyze changes
        red_flag_count = 0
        new_footnotes = []
        expanded_footnotes = []

        for section, current_text in current_footnotes.items():
            # Check for red flag keywords
            current_lower = current_text.lower()
            for keyword in self.RED_FLAG_KEYWORDS:
                if keyword in current_lower:
                    red_flag_count += current_lower.count(keyword)

            # Compare to previous period
            if section in previous_footnotes:
                prev_text = previous_footnotes[section]
                current_len = len(current_text)
                prev_len = len(prev_text)

                # Footnote expanded significantly (>20%)
                if current_len > prev_len * 1.2:
                    expanded_footnotes.append(section)

            else:
                # New footnote added
                new_footnotes.append(section)

        # Calculate score
        score = 0

        # Penalty for red flags
        score -= red_flag_count * 15

        # Penalty for new footnotes (often bad news)
        score -= len(new_footnotes) * 10

        # Penalty for expanded footnotes
        score -= len(expanded_footnotes) * 5

        score = max(-100, min(0, score))

        # Confidence
        confidence = 0.75

        # Build description
        description = f"Footnote analysis: {red_flag_count} red flags"

        if new_footnotes:
            description += f" | {len(new_footnotes)} new footnote(s)"

        if expanded_footnotes:
            description += f" | {len(expanded_footnotes)} expanded"

        if red_flag_count > 5:
            description += " | 🚨 MULTIPLE ACCOUNTING CONCERNS"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "red_flag_count": red_flag_count,
                "new_footnotes": new_footnotes,
                "expanded_footnotes": expanded_footnotes,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://www.sec.gov/edgar",
                source_name="SEC Footnotes",
                processing_notes=f"{red_flag_count} red flags, {len(new_footnotes)} new",
                raw_data_hash=hashlib.md5(
                    json.dumps(current_footnotes, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["footnotes", "accounting", "red_flags"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample footnote data"""

        if company.ticker == "UBER":
            # Sample: Clean accounting
            current_footnotes = {
                "Revenue Recognition": "Standard ASC 606...",
                "Goodwill": "No impairment indicators...",
            }
            previous_footnotes = {
                "Revenue Recognition": "Standard ASC 606...",
                "Goodwill": "No impairment indicators...",
            }
        else:
            current_footnotes = {}
            previous_footnotes = {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "current_footnotes": current_footnotes,
            "previous_footnotes": previous_footnotes,
            "timestamp": datetime.utcnow(),
        }

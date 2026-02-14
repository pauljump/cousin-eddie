"""
SEC Form 144 Signal Processor

Monitors Form 144 filings - Notice of Proposed Sale of Securities.
Insiders MUST file Form 144 before selling restricted stock.

This is a LEADING indicator (filed before sale) vs Form 4 (filed after sale).
Large Form 144 filings can signal lack of confidence before the sale happens.

Data Source: SEC EDGAR API (free, real-time)
Update Frequency: Real-time (as filings occur)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
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
from .edgar_client import EdgarClient


class SECForm144Processor(SignalProcessor):
    """
    Process SEC Form 144 filings (Notice of Proposed Sale).

    Form 144 is filed BEFORE an insider sells restricted securities.
    It's required when selling > $50K or > 5,000 shares in a 3-month period.

    Key insight: Large 144 filings = insider wants to sell = potential bearish signal
    """

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent identifying you
        """
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"
        self._edgar_client = EdgarClient(user_agent=user_agent)

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_form_144",
            category=SignalCategory.REGULATORY,
            description="Proposed insider sales - LEADING indicator (filed before sale)",
            update_frequency=UpdateFrequency.REALTIME,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["insider_trading", "regulatory", "form_144", "sec", "leading_indicator"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Form 144 applies to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch Form 144 filings from SEC EDGAR.

        Uses EdgarClient to fetch ALL filings (recent + archived batches).
        Form 144 doesn't have structured XML like Form 4, so we extract
        metadata from the filing index.
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return []

        # Fetch all Form 144 filings (recent + archived)
        all_filings = await self._edgar_client.get_all_filings(
            cik=company.cik, form_type="144", start_date=start, end_date=end
        )

        if not all_filings:
            return []

        form144_filings = []
        for filing in all_filings:
            filing_info = {
                "accessionNumber": filing["accessionNumber"],
                "filingDate": filing["filingDate"],
                "acceptanceDateTime": filing.get("acceptanceDateTime"),
                "primaryDocument": filing["primaryDocument"],
            }
            form144_filings.append(filing_info)

        logger.info(f"Found {len(form144_filings)} Form 144 filings for {company.ticker}")
        return form144_filings

    def process(
        self,
        company: Company,
        raw_data: List[Dict[str, Any]]
    ) -> List[Signal]:
        """
        Process Form 144 filings into signals.

        Since Form 144 doesn't have structured data in the same way as Form 4,
        we score based on filing frequency and timing.

        Key insights:
        - Multiple 144 filings in short period = heavy insider selling planned
        - 144 filed right before earnings = potential red flag
        - Weekend/evening filings = trying to bury news
        """
        signals = []

        # Group filings by date to detect clusters
        filings_by_date = {}
        for filing in raw_data:
            date = filing["filingDate"]
            if date not in filings_by_date:
                filings_by_date[date] = []
            filings_by_date[date].append(filing)

        # Process each filing date
        for filing_date_str, date_filings in filings_by_date.items():
            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

            num_filings = len(date_filings)

            # Get filing time for first filing (to check for timing signals)
            acceptance_datetime = date_filings[0].get("acceptanceDateTime")
            filing_time = filing_date
            if acceptance_datetime:
                try:
                    filing_time = datetime.fromisoformat(acceptance_datetime.replace("Z", "+00:00"))
                except:
                    pass

            # Score the filing(s)
            score, confidence = self._score_form144_filing(
                num_filings=num_filings,
                filing_date=filing_date,
                filing_time=filing_time,
            )

            # Create description
            if num_filings == 1:
                description = f"Form 144 filed - insider plans to sell restricted securities"
            else:
                description = f"{num_filings} Form 144 filings in one day - multiple insiders plan to sell"

            # Create raw value
            raw_value = {
                "filing_date": filing_date_str,
                "num_filings": num_filings,
                "accession_numbers": [f["accessionNumber"] for f in date_filings],
                "acceptance_datetime": acceptance_datetime,
            }

            # Calculate hash for deduplication
            raw_hash = hashlib.md5(
                json.dumps(raw_value, sort_keys=True, default=str).encode()
            ).hexdigest()

            normalized_value = score / 100.0

            # Create signal
            signal = Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=filing_date,
                raw_value=raw_value,
                normalized_value=normalized_value,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=144",
                    source_name="SEC EDGAR",
                    processing_notes=f"Form 144 - proposed sale notice ({num_filings} filing(s))",
                    raw_data_hash=raw_hash,
                ),
                description=description,
                tags=["form_144", "insider_trading", "sec", "proposed_sale", "leading_indicator"],
            )

            signals.append(signal)

        return signals

    def _score_form144_filing(
        self,
        num_filings: int,
        filing_date: datetime,
        filing_time: datetime,
    ) -> tuple[int, float]:
        """
        Score a Form 144 filing.

        Returns:
            (score, confidence) tuple

        Scoring logic:
        - Form 144 = planned sale = mildly bearish (insiders want to sell)
        - Multiple filings same day = more bearish (coordinated selling)
        - Weekend/evening filings = more bearish (trying to hide)
        - Form 144 is inherently bearish (unlike Form 4 which can be buy or sell)
        """
        # Base score: Form 144 is mildly bearish (planned insider sale)
        score = -25
        confidence = 0.70

        # Adjust for number of filings (multiple insiders = worse)
        if num_filings >= 5:
            score = -60
            confidence = 0.85
        elif num_filings >= 3:
            score = -45
            confidence = 0.80
        elif num_filings >= 2:
            score = -35
            confidence = 0.75

        # Weekend filing red flag (Saturday = 5, Sunday = 6)
        if filing_time.weekday() >= 5:
            score = int(score * 1.3)  # Increase bearishness by 30%
            confidence *= 0.95

        # Friday evening filing red flag
        if filing_time.weekday() == 4 and filing_time.hour >= 17:
            score = int(score * 1.2)  # Increase bearishness by 20%
            confidence *= 0.95

        # Cap scores
        score = max(-100, min(0, score))  # Form 144 is never bullish

        return score, confidence

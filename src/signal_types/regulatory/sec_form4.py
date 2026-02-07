"""
SEC Form 4 Signal Processor

Monitors insider trading filings to detect buying/selling by company executives.
Large insider buys are often bullish signals, especially from CEO/CFO.

Data Source: SEC EDGAR API (free, real-time)
Update Frequency: Real-time (as filings occur)
"""

from typing import List, Any, Dict
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


class SECForm4Processor(SignalProcessor):
    """Process SEC Form 4 insider trading filings"""

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent identifying you
                       Format: "CompanyName email@example.com"
        """
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_form_4",
            category=SignalCategory.REGULATORY,
            description="Insider trading filings - detect executive buying/selling",
            update_frequency=UpdateFrequency.REALTIME,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["insider_trading", "regulatory", "executives", "sec"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Form 4 applies to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch Form 4 filings from SEC EDGAR.

        SEC API endpoint: https://data.sec.gov/submissions/CIK{cik}.json
        Returns all filings for a company, which we filter for Form 4.
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return []

        # Format CIK (must be 10 digits, zero-padded)
        cik = company.cik.zfill(10)

        url = f"{self.base_url}/submissions/CIK{cik}.json"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Fetching SEC submissions for {company.ticker} (CIK: {cik})")
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()

                data = response.json()

                # Extract recent filings
                filings = data.get("filings", {}).get("recent", {})

                if not filings:
                    logger.warning(f"No filings found for {company.ticker}")
                    return []

                # Filter for Form 4 within date range
                form4_filings = []
                for i in range(len(filings.get("form", []))):
                    form_type = filings["form"][i]
                    filing_date_str = filings["filingDate"][i]
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                    if form_type == "4" and start <= filing_date <= end:
                        form4_filings.append({
                            "accessionNumber": filings["accessionNumber"][i],
                            "filingDate": filing_date_str,
                            "reportDate": filings.get("reportDate", [])[i] if filings.get("reportDate") else None,
                            "acceptanceDateTime": filings.get("acceptanceDateTime", [])[i] if filings.get("acceptanceDateTime") else None,
                            "primaryDocument": filings["primaryDocument"][i],
                            "primaryDocDescription": filings.get("primaryDocDescription", [])[i] if filings.get("primaryDocDescription") else None,
                        })

                logger.info(f"Found {len(form4_filings)} Form 4 filings for {company.ticker}")
                return form4_filings

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Form 4 for {company.ticker}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Form 4 for {company.ticker}: {e}")
            return []

    def process(
        self,
        company: Company,
        raw_data: List[Dict[str, Any]]
    ) -> List[Signal]:
        """
        Process Form 4 filings into signals.

        Note: Full parsing of Form 4 XML requires complex logic.
        For MVP, we create signals for each filing with basic metadata.
        TODO: Parse XML to extract transaction details (buy/sell, shares, price)
        """
        signals = []

        for filing in raw_data:
            # Parse filing date
            filing_date_str = filing.get("filingDate")
            if not filing_date_str:
                continue

            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

            # For MVP: Create a neutral signal indicating filing exists
            # TODO: Parse XML to determine if it's a buy (bullish) or sell (bearish)
            #
            # Parsing logic would:
            # 1. Fetch XML from primaryDocument URL
            # 2. Parse <nonDerivativeTransaction> elements
            # 3. Extract transactionCode (P=purchase, S=sale)
            # 4. Extract shares, price, insider name, title
            # 5. Score based on:
            #    - Transaction type (buy vs sell)
            #    - Insider role (CEO > CFO > Director)
            #    - Transaction size
            #    - Timing (Friday night = suspicious)

            raw_value = {
                "accession_number": filing.get("accessionNumber"),
                "filing_date": filing_date_str,
                "acceptance_datetime": filing.get("acceptanceDateTime"),
                "primary_document": filing.get("primaryDocument"),
                # TODO: Add parsed transaction details
                "transaction_type": "unknown",  # Should be "buy" or "sell"
                "insider_name": "unknown",
                "insider_title": "unknown",
                "shares": 0,
                "price": 0.0,
                "total_value": 0.0,
            }

            # Calculate hash for deduplication
            raw_hash = hashlib.md5(
                json.dumps(raw_value, sort_keys=True).encode()
            ).hexdigest()

            # For MVP: Score as neutral since we don't parse XML yet
            # Once parsed:
            # - Large insider buy by CEO/CFO = +80 to +95
            # - Small insider buy = +30 to +50
            # - Insider sell = -20 to -50 (sells are less informative)
            score = 0
            normalized_value = 0.0
            confidence = 0.5  # Low confidence until we parse XML

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
                    source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=4",
                    source_name="SEC EDGAR",
                    processing_notes="Form 4 detected - XML parsing not implemented yet",
                    raw_data_hash=raw_hash,
                ),
                description=f"Form 4 filing on {filing_date_str}",
                tags=["form_4", "insider_trading", "sec"],
            )

            signals.append(signal)

        return signals


# Example of what a fully-parsed Form 4 scoring function would look like:
def _score_form4_transaction(
    transaction_type: str,  # "buy" or "sell"
    insider_title: str,  # "CEO", "CFO", "Director", etc.
    total_value: float,  # Dollar value of transaction
    filing_time: datetime,  # When filed
) -> tuple[int, float]:
    """
    Score a Form 4 transaction.

    Returns:
        (score, confidence) tuple

    Scoring logic based on research showing:
    - CEO/CFO large buys outperform market by 6-10%
    - Friday night filings often hide bad news
    - Transactions > $1M are more significant
    """
    score = 0
    confidence = 0.8

    # Base score from transaction type
    if transaction_type == "buy":
        score = 50  # Base bullish
    elif transaction_type == "sell":
        score = -20  # Mildly bearish (insiders sell for many reasons)
    else:
        score = 0
        confidence = 0.3
        return score, confidence

    # Adjust for insider role
    role_multipliers = {
        "CEO": 1.8,
        "CFO": 1.6,
        "President": 1.5,
        "COO": 1.4,
        "Director": 1.0,
        "Officer": 0.8,
    }

    for role, multiplier in role_multipliers.items():
        if role.lower() in insider_title.lower():
            score = int(score * multiplier)
            break

    # Adjust for transaction size
    if transaction_type == "buy":
        if total_value > 5_000_000:
            score = min(score + 30, 100)
            confidence = 0.95
        elif total_value > 1_000_000:
            score = min(score + 20, 100)
            confidence = 0.9
        elif total_value > 500_000:
            score = min(score + 10, 100)
        elif total_value < 50_000:
            score = max(score - 10, 0)
            confidence = 0.6

    # Friday night filing red flag
    if filing_time.weekday() == 4 and filing_time.hour >= 17:  # Friday after 5pm
        score = int(score * 0.7)  # Reduce bullishness (might be burying news)
        confidence *= 0.9

    # Cap scores
    score = max(-100, min(100, score))

    # Normalized value
    normalized_value = score / 100.0

    return score, confidence

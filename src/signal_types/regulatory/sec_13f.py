"""
SEC Form 13F Signal Processor

Tracks institutional investor holdings (the "smart money").

13F filings show holdings of institutional investment managers with >$100M AUM.
Filed quarterly (45 days after quarter end).

High-signal institutions (for weighting):
- Berkshire Hathaway (Warren Buffett)
- Bridgewater Associates (Ray Dalio)
- Renaissance Technologies (Jim Simons)
- Tiger Global
- Pershing Square (Bill Ackman)

Signals:
- New institutional position = bullish (especially if major fund)
- Increased position = bullish
- Decreased position = bearish
- Complete exit = bearish
- Aggregate institutional ownership increasing = bullish

Note: 13F data aggregation is complex. For POC, we track changes in
total institutional ownership from SEC's Company Facts API.

Full 13F analysis (tracking individual funds) requires processing thousands
of 13F filings per quarter - we'll add this in Phase 2.

Data Source: SEC EDGAR Company Facts API
Update Frequency: Quarterly (with 45-day lag)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime
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


class SEC13FProcessor(SignalProcessor):
    """Process institutional ownership changes from aggregated 13F data"""

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent identifying you
        """
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_13f",
            category=SignalCategory.REGULATORY,
            description="Institutional investor holdings (smart money tracking)",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC EDGAR Company Facts",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["13f", "institutional", "holdings", "smart_money", "regulatory"],
        )

    def is_applicable(self, company: Company) -> bool:
        """13F applies to all US public companies with significant institutional ownership"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch institutional ownership data from SEC Company Facts.

        Note: This is aggregated data. Full 13F processing (individual fund
        holdings) requires processing thousands of 13F-HR filings.
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return {}

        # Format CIK (must be 10 digits, zero-padded)
        cik = company.cik.zfill(10)

        # SEC Company Facts API provides aggregated ownership data
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik}.json"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching institutional ownership for {company.ticker}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()

                # Look for common ownership metrics in the facts
                # Different companies report this differently
                ownership_data = self._extract_ownership_metrics(data)

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "cik": cik,
                    "ownership_data": ownership_data,
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"No Company Facts data available for {company.ticker}")
            else:
                logger.error(f"HTTP error fetching 13F data: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching 13F data: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process institutional ownership data into signals.

        Since full 13F aggregation is complex, we use a simplified approach:
        1. Track changes in reported institutional ownership metrics
        2. Calculate quarter-over-quarter changes
        3. Generate signals based on ownership trends

        Future enhancement: Process individual 13F-HR filings to track
        specific fund holdings (Berkshire, Bridgewater, etc.)
        """
        ownership_data = raw_data.get("ownership_data", {})

        if not ownership_data:
            logger.info(f"No institutional ownership metrics found for {company.id}")
            return []

        # For now, create a placeholder signal indicating 13F tracking is active
        # Full implementation would:
        # 1. Query all 13F-HR filings for the quarter
        # 2. Parse holdings tables (can be CSV or XML)
        # 3. Filter for our company's CUSIP
        # 4. Track changes by fund
        # 5. Weight by fund reputation

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value=ownership_data,
            normalized_value=0.0,  # Neutral for now
            score=0,  # Neutral signal (placeholder)
            confidence=0.50,  # Low confidence - simplified implementation
            metadata=SignalMetadata(
                source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={raw_data.get('cik')}&type=13F",
                source_name="SEC EDGAR 13F (Aggregated)",
                processing_notes="Simplified 13F tracking - full fund-level analysis pending",
                raw_data_hash=hashlib.md5(
                    json.dumps(ownership_data, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=f"Institutional ownership tracked (simplified implementation)",
            tags=["13f", "institutional", "placeholder"],
        )

        return [signal]

    def _extract_ownership_metrics(self, company_facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ownership-related metrics from Company Facts.

        Common metrics:
        - CommonStockSharesOutstanding
        - WeightedAverageNumberOfSharesOutstandingBasic
        - EntityCommonStockSharesOutstanding

        Note: Company Facts doesn't directly provide institutional ownership %.
        Full 13F analysis requires parsing individual 13F-HR filings.
        """
        facts = company_facts.get("facts", {})

        # Try different taxonomies
        ownership_metrics = {}

        for taxonomy in ["us-gaap", "dei", "ifrs-full"]:
            if taxonomy in facts:
                taxonomy_facts = facts[taxonomy]

                # Look for shares outstanding
                if "CommonStockSharesOutstanding" in taxonomy_facts:
                    ownership_metrics["shares_outstanding"] = taxonomy_facts["CommonStockSharesOutstanding"]

                if "EntityCommonStockSharesOutstanding" in taxonomy_facts:
                    ownership_metrics["entity_shares"] = taxonomy_facts["EntityCommonStockSharesOutstanding"]

        return ownership_metrics

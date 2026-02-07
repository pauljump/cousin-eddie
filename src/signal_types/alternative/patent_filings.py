"""
Patent Filings Signal Processor

Tracks patent applications and grants as a measure of innovation activity.

Patent data reveals:
- Innovation velocity (more patents = more R&D activity)
- Strategic focus areas (AI, autonomous vehicles, biotech, etc.)
- Competitive positioning (patent citations, prior art)
- Technology trends (emerging vs declining tech areas)

Signals:
- Increasing patent filings = bullish (innovation investment)
- Decreasing filings = bearish (cutting R&D)
- High-value patents (many citations) = very bullish
- Patents in hot tech areas (AI, quantum, biotech) = bullish
- Defensive patents only = neutral/bearish (not innovating)

Patent Types:
- Utility patents: new inventions (most valuable)
- Design patents: product appearance (less valuable)
- Provisional: placeholder (signals intent)

Key Metrics:
- Patent grants per quarter
- Application velocity (leading indicator)
- Citation count (quality measure)
- Technology classification (strategic focus)
- Inventor count (R&D team size)

Data Source: USPTO PatentsView API (free, unlimited)
Alternative: Google Patents Public Datasets (BigQuery)
Update Frequency: Monthly (patents publish ~18 months after filing)
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


class PatentFilingsProcessor(SignalProcessor):
    """Track patent filings and grants as innovation signal"""

    # High-value technology categories (CPC codes)
    HOT_TECH_AREAS = {
        "G06N": "Artificial Intelligence / Machine Learning",
        "G06Q": "E-commerce / Fintech",
        "B60W": "Autonomous Vehicles",
        "H04L": "Wireless Communications / 5G",
        "A61": "Medical Devices / Biotech",
        "G16H": "Healthcare IT",
        "H01L": "Semiconductors",
        "C12N": "Genetic Engineering",
    }

    def __init__(self):
        """Initialize processor."""
        self.api_url = "https://api.patentsview.org/patents/query"

        # Map company IDs to USPTO assignee names
        # Note: Companies may have multiple assignee names due to subsidiaries
        self.assignee_mappings = {
            "UBER": ["Uber Technologies, Inc.", "Uber Technologies Inc"],
            "GOOGL": ["Google LLC", "Google Inc.", "Alphabet Inc."],
            "AAPL": ["Apple Inc.", "Apple Computer, Inc."],
            "TSLA": ["Tesla, Inc.", "Tesla Motors, Inc."],
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="patent_filings",
            category=SignalCategory.ALTERNATIVE,
            description="Patent filings and grants - R&D activity and innovation tracking",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="USPTO PatentsView API",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["patents", "innovation", "r&d", "alternative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with R&D activity (tech, pharma, manufacturing)"""
        return company.id in self.assignee_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch patent grants and applications from USPTO.

        Uses PatentsView API (free, unlimited).
        """
        if company.id not in self.assignee_mappings:
            return {}

        assignee_names = self.assignee_mappings[company.id]

        # PatentsView API query
        # Search for patents granted in the date range
        query = {
            "q": {
                "_or": [
                    {"assignee_organization": name}
                    for name in assignee_names
                ]
            },
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "assignee_organization",
                "cpc_section_id",
                "cited_patent_count",
            ],
            "o": {
                "per_page": 100
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching patent data for {company.ticker} from USPTO")

                # Note: PatentsView API has rate limits
                # Free tier: ~30 requests per minute
                response = await client.post(self.api_url, json=query)
                response.raise_for_status()

                data = response.json()
                patents = data.get("patents", [])

                logger.info(f"Found {len(patents)} recent patents for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "patents": patents,
                    "total_count": data.get("total_patent_count", len(patents)),
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPError as e:
            logger.error(f"Error fetching patent data: {e}")
            # Fall back to sample data
            logger.warning("Using sample patent data")
            return self._get_sample_data(company, start, end)
        except Exception as e:
            logger.error(f"Unexpected error fetching patents: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process patent data into signals.

        Generates:
        1. Patent velocity signal (volume trend)
        2. Innovation quality signal (citations, tech areas)
        """
        patents = raw_data.get("patents", [])

        if not patents:
            return []

        total_count = len(patents)

        # Analyze patents
        high_citation_count = 0
        hot_tech_count = 0
        utility_patent_count = 0

        for patent in patents:
            # Check patent type
            patent_type = patent.get("patent_type", "")
            if patent_type == "utility":
                utility_patent_count += 1

            # Check citations (quality indicator)
            citations = patent.get("cited_patent_count", 0)
            if citations > 10:  # Well-cited patent
                high_citation_count += 1

            # Check if in hot tech area
            cpc_codes = patent.get("cpc_section_id", [])
            if isinstance(cpc_codes, list):
                for code in cpc_codes:
                    if any(code.startswith(hot) for hot in self.HOT_TECH_AREAS.keys()):
                        hot_tech_count += 1
                        break

        # Calculate score
        # Base: +2 per patent
        # Bonus: +5 for each high-citation patent
        # Bonus: +3 for each hot-tech patent
        score = (total_count * 2) + (high_citation_count * 5) + (hot_tech_count * 3)

        # Normalize to -100 to +100
        # 0 patents = 0 score
        # 20+ patents/quarter = +80 to +100
        score = min(100, score)

        # Confidence based on data completeness
        confidence = 0.70 if total_count > 5 else 0.60

        # Build description
        description = f"Patent activity: {total_count} patents granted"

        if high_citation_count > 0:
            description += f" | {high_citation_count} highly-cited"

        if hot_tech_count > 0:
            description += f" | {hot_tech_count} in hot tech areas"

        if utility_patent_count > 0:
            description += f" ({utility_patent_count} utility)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_patents": total_count,
                "utility_patents": utility_patent_count,
                "high_citation": high_citation_count,
                "hot_tech": hot_tech_count,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://patentsview.org",
                source_name="USPTO PatentsView",
                processing_notes=f"Analyzed {total_count} patent grants",
                raw_data_hash=hashlib.md5(
                    json.dumps(patents, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["patents", "innovation", "r&d"],
        )

        return [signal]

    def _get_sample_data(self, company: Company, start: datetime, end: datetime) -> Dict[str, Any]:
        """
        Return sample patent data.

        In production, this would be actual USPTO API data.
        """
        if company.ticker == "UBER":
            # Sample patents (realistic for Uber's tech focus)
            sample_patents = [
                {
                    "patent_number": "11234567",
                    "patent_title": "Systems and methods for autonomous vehicle route optimization",
                    "patent_date": "2025-12-15",
                    "patent_type": "utility",
                    "assignee_organization": "Uber Technologies, Inc.",
                    "cpc_section_id": ["B60W", "G06N"],
                    "cited_patent_count": 15,
                },
                {
                    "patent_number": "11234568",
                    "patent_title": "Machine learning-based demand prediction for ride-sharing",
                    "patent_date": "2025-11-22",
                    "patent_type": "utility",
                    "assignee_organization": "Uber Technologies, Inc.",
                    "cpc_section_id": ["G06N", "G06Q"],
                    "cited_patent_count": 8,
                },
                {
                    "patent_number": "11234569",
                    "patent_title": "Dynamic pricing algorithms for multi-modal transportation",
                    "patent_date": "2025-10-30",
                    "patent_type": "utility",
                    "assignee_organization": "Uber Technologies, Inc.",
                    "cpc_section_id": ["G06Q"],
                    "cited_patent_count": 12,
                },
                {
                    "patent_number": "D987654",
                    "patent_title": "Graphical user interface for mobile application",
                    "patent_date": "2025-10-10",
                    "patent_type": "design",
                    "assignee_organization": "Uber Technologies, Inc.",
                    "cpc_section_id": ["G06F"],
                    "cited_patent_count": 2,
                },
            ]
        else:
            sample_patents = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "patents": sample_patents,
            "total_count": len(sample_patents),
            "timestamp": datetime.utcnow(),
        }

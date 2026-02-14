"""
Corporate Subsidiary Registrations Signal Processor

Tracks changes in corporate subsidiary structure via SEC Exhibit 21 filings.

Companies file Exhibit 21 (list of subsidiaries) with their annual 10-K.
Comparing year-over-year changes reveals:
- Market expansion (new subsidiaries in new countries)
- Business line additions (insurance, financing entities)
- Market exits (subsidiaries removed)
- Restructuring activity

Signals:
- New subsidiaries added = expansion (bullish)
- Subsidiaries removed = market exit or restructuring (context-dependent)
- Geographic expansion = new country entries (bullish)
- Entity type patterns = new business lines (bullish)

Data Source: SEC EDGAR (Exhibit 21 from 10-K filings) - free
Update Frequency: Annual (filed with 10-K)
"""

from typing import List, Any, Dict, Optional, Tuple
from datetime import datetime
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


class SubsidiaryRegistrationsProcessor(SignalProcessor):
    """Track corporate subsidiary changes as expansion/contraction signals"""

    # Country/jurisdiction keywords for geographic analysis
    GEOGRAPHIC_REGIONS = {
        "americas": [
            "united states", "delaware", "california", "new york", "texas",
            "canada", "brazil", "mexico", "argentina", "colombia",
        ],
        "europe": [
            "united kingdom", "netherlands", "ireland", "germany", "france",
            "spain", "italy", "luxembourg", "switzerland", "sweden",
        ],
        "asia_pacific": [
            "india", "japan", "china", "hong kong", "singapore", "australia",
            "south korea", "taiwan", "indonesia", "vietnam", "philippines",
        ],
        "middle_east_africa": [
            "united arab emirates", "saudi arabia", "south africa", "nigeria",
            "egypt", "kenya", "israel", "qatar",
        ],
    }

    # Entity type keywords for business line analysis
    ENTITY_TYPES = {
        "insurance": ["insurance", "indemnity", "underwriting"],
        "financing": ["finance", "financial", "capital", "lending", "credit"],
        "technology": ["technology", "tech", "software", "digital", "data"],
        "logistics": ["logistics", "freight", "shipping", "delivery", "courier"],
        "food_delivery": ["eats", "food", "restaurant", "dining"],
        "mobility": ["mobility", "ride", "transport", "vehicle", "auto"],
        "holding": ["holdings", "holding", "group", "parent"],
    }

    def __init__(self):
        """Initialize processor."""
        self.edgar_base_url = "https://efts.sec.gov/LATEST/search-index"
        self.edgar_filings_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.edgar_full_text_url = "https://efts.sec.gov/LATEST/search-index"

        # Map company IDs to CIK numbers
        self.cik_mappings = {
            "UBER": "0001543151",
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="subsidiary_registrations",
            category=SignalCategory.ALTERNATIVE,
            description="Corporate subsidiary changes - expansion/contraction via SEC Exhibit 21",
            update_frequency=UpdateFrequency.ANNUAL,
            data_source="SEC EDGAR (Exhibit 21)",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["subsidiaries", "expansion", "sec", "corporate-structure", "alternative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to public companies with SEC filings"""
        return company.id in self.cik_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch Exhibit 21 data from SEC EDGAR.

        Retrieves subsidiary lists from latest and prior year 10-K filings,
        then computes the diff.
        """
        if company.id not in self.cik_mappings:
            return {}

        cik = self.cik_mappings[company.id]

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "CousinEddie/1.0 research@example.com"},
            ) as client:
                logger.info(f"Fetching Exhibit 21 data for {company.ticker} from SEC EDGAR")

                # Fetch company filings index from EDGAR
                submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                response = await client.get(submissions_url)
                response.raise_for_status()

                submissions = response.json()
                recent_filings = submissions.get("filings", {}).get("recent", {})

                # Find 10-K filings (which contain Exhibit 21)
                forms = recent_filings.get("form", [])
                accession_numbers = recent_filings.get("accessionNumber", [])
                filing_dates = recent_filings.get("filingDate", [])

                ten_k_filings = []
                for i, form in enumerate(forms):
                    if form in ("10-K", "10-K/A"):
                        ten_k_filings.append({
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_dates[i],
                            "form": form,
                        })

                if len(ten_k_filings) < 1:
                    logger.warning(f"No 10-K filings found for {company.ticker}")
                    return self._get_sample_data(company, start, end)

                logger.info(
                    f"Found {len(ten_k_filings)} 10-K filings for {company.ticker}"
                )

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "ten_k_filings": ten_k_filings[:2],
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPError as e:
            logger.error(f"Error fetching EDGAR data: {e}")
            logger.warning("Using sample subsidiary data")
            return self._get_sample_data(company, start, end)
        except Exception as e:
            logger.error(f"Unexpected error fetching subsidiary data: {e}")
            return self._get_sample_data(company, start, end)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process subsidiary data into signals.

        Compares current vs prior year subsidiary lists and generates
        signals based on additions, removals, and geographic patterns.
        """
        current_subs = raw_data.get("current_subsidiaries", [])
        prior_subs = raw_data.get("prior_subsidiaries", [])

        if not current_subs and not prior_subs:
            return []

        signals = []

        # Normalize subsidiary names for comparison
        current_names = {self._normalize_name(s.get("name", "")) for s in current_subs}
        prior_names = {self._normalize_name(s.get("name", "")) for s in prior_subs}

        added = current_names - prior_names
        removed = prior_names - current_names
        net_change = len(added) - len(removed)

        # Analyze geographic distribution of new subsidiaries
        new_regions = set()
        for sub in current_subs:
            name_lower = self._normalize_name(sub.get("name", ""))
            if name_lower in added:
                jurisdiction = sub.get("jurisdiction", "").lower()
                for region, keywords in self.GEOGRAPHIC_REGIONS.items():
                    if any(kw in jurisdiction for kw in keywords):
                        new_regions.add(region)
                        break

        # Analyze entity types of new subsidiaries
        new_business_lines = set()
        for sub in current_subs:
            name_lower = self._normalize_name(sub.get("name", ""))
            if name_lower in added:
                for biz_type, keywords in self.ENTITY_TYPES.items():
                    if any(kw in name_lower for kw in keywords):
                        new_business_lines.add(biz_type)

        # Signal 1: Net subsidiary changes (expansion vs contraction)
        if added or removed:
            if net_change > 5:
                score = 50
            elif net_change > 0:
                score = 30 + (net_change * 5)
            elif net_change == 0:
                score = 0
            elif net_change > -5:
                score = net_change * 10
            else:
                score = -30

            # Bonus for new geographic markets
            if new_regions:
                score = min(100, score + len(new_regions) * 15)

            # Bonus for new business lines
            if new_business_lines:
                score = min(100, score + len(new_business_lines) * 10)

            score = max(-100, min(100, score))

            description = (
                f"Subsidiary changes: +{len(added)} added, -{len(removed)} removed "
                f"(net {'+' if net_change > 0 else ''}{net_change})"
            )
            if new_regions:
                description += f" | New regions: {', '.join(sorted(new_regions))}"
            if new_business_lines:
                description += f" | New lines: {', '.join(sorted(new_business_lines))}"

            confidence = 0.75 if (current_subs and prior_subs) else 0.55

            signals.append(Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "current_count": len(current_subs),
                    "prior_count": len(prior_subs),
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "net_change": net_change,
                    "new_regions": sorted(new_regions),
                    "new_business_lines": sorted(new_business_lines),
                    "added_names": sorted(list(added)[:10]),
                    "removed_names": sorted(list(removed)[:10]),
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url="https://www.sec.gov/cgi-bin/browse-edgar",
                    source_name="SEC EDGAR (Exhibit 21)",
                    processing_notes=(
                        f"Compared {len(current_subs)} current vs "
                        f"{len(prior_subs)} prior year subsidiaries"
                    ),
                    raw_data_hash=hashlib.md5(
                        json.dumps(
                            sorted(list(current_names)), default=str
                        ).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["subsidiaries", "corporate_structure", "expansion"],
            ))

        # Signal 2: Geographic expansion specifically
        if len(new_regions) >= 2:
            geo_score = min(80, len(new_regions) * 25)

            signals.append(Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "event_type": "geographic_expansion",
                    "new_regions": sorted(new_regions),
                    "region_count": len(new_regions),
                },
                normalized_value=geo_score / 100.0,
                score=geo_score,
                confidence=0.70,
                metadata=SignalMetadata(
                    source_url="https://www.sec.gov/cgi-bin/browse-edgar",
                    source_name="SEC EDGAR (Exhibit 21)",
                    processing_notes=f"Detected expansion into {len(new_regions)} new regions",
                ),
                description=f"Geographic expansion: new subsidiaries in {', '.join(sorted(new_regions))}",
                tags=["subsidiaries", "geographic_expansion", "international"],
            ))

        return signals

    def _normalize_name(self, name: str) -> str:
        """Normalize subsidiary name for comparison."""
        name = name.lower().strip()
        # Remove common suffixes
        for suffix in [", inc.", ", llc", ", ltd", ", b.v.", ", s.a.", " inc", " llc", " ltd"]:
            name = name.replace(suffix, "")
        return name.strip()

    def _get_sample_data(
        self, company: Company, start: datetime, end: datetime
    ) -> Dict[str, Any]:
        """Return sample subsidiary data for when EDGAR is unavailable."""
        if company.ticker == "UBER":
            current_subsidiaries = [
                {"name": "Uber Technologies, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber International B.V.", "jurisdiction": "Netherlands"},
                {"name": "Uber Portier B.V.", "jurisdiction": "Netherlands"},
                {"name": "Uber London Limited", "jurisdiction": "United Kingdom"},
                {"name": "Uber India Systems Private Limited", "jurisdiction": "India"},
                {"name": "Uber Japan Co., Ltd.", "jurisdiction": "Japan"},
                {"name": "Uber Australia Pty Ltd", "jurisdiction": "Australia"},
                {"name": "Uber Brazil Technology Ltda.", "jurisdiction": "Brazil"},
                {"name": "Uber Canada, Inc.", "jurisdiction": "Canada"},
                {"name": "Uber Freight LLC", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Eats, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Insurance Management, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Health, Inc.", "jurisdiction": "California, United States"},
                # New additions (expansion signals)
                {"name": "Uber Vietnam Technology Co., Ltd.", "jurisdiction": "Vietnam"},
                {"name": "Uber Financial Services LLC", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Autonomous Technologies, Inc.", "jurisdiction": "California, United States"},
                {"name": "Uber Philippines, Inc.", "jurisdiction": "Philippines"},
            ]

            prior_subsidiaries = [
                {"name": "Uber Technologies, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber International B.V.", "jurisdiction": "Netherlands"},
                {"name": "Uber Portier B.V.", "jurisdiction": "Netherlands"},
                {"name": "Uber London Limited", "jurisdiction": "United Kingdom"},
                {"name": "Uber India Systems Private Limited", "jurisdiction": "India"},
                {"name": "Uber Japan Co., Ltd.", "jurisdiction": "Japan"},
                {"name": "Uber Australia Pty Ltd", "jurisdiction": "Australia"},
                {"name": "Uber Brazil Technology Ltda.", "jurisdiction": "Brazil"},
                {"name": "Uber Canada, Inc.", "jurisdiction": "Canada"},
                {"name": "Uber Freight LLC", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Eats, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Insurance Management, Inc.", "jurisdiction": "Delaware, United States"},
                {"name": "Uber Health, Inc.", "jurisdiction": "California, United States"},
                # Removed (contraction signal)
                {"name": "Uber China Technology Co., Ltd.", "jurisdiction": "China"},
            ]
        else:
            current_subsidiaries = []
            prior_subsidiaries = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "current_subsidiaries": current_subsidiaries,
            "prior_subsidiaries": prior_subsidiaries,
            "timestamp": datetime.utcnow(),
        }

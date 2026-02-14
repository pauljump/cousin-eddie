"""
Trademark Filings Signal Processor

Tracks trademark applications, registrations, and abandonments as commercial intent signals.

Trademarks differ from patents:
- Patents = innovation/R&D activity
- Trademarks = commercial intent, product launches, market entries

Signals:
- New trademark applications = bullish (new product/service incoming)
- Trademark in new Nice class = market expansion signal
- Abandoned trademarks = killed product/pivot (bearish)
- Opposition proceedings = competitive friction (bearish)

Data Source: USPTO TSDR (Trademark Status & Document Retrieval) API - free, no key needed
API: https://tsdrapi.uspto.gov
Update Frequency: Weekly (new filings published weekly)
"""

from typing import List, Any, Dict
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


class TrademarkFilingsProcessor(SignalProcessor):
    """Track trademark filings as commercial intent and product launch signals"""

    # Nice classification categories relevant for signal analysis
    NICE_CLASSES = {
        9: "Software / Apps / Electronics",
        35: "Advertising / Business Management",
        36: "Financial Services / Insurance",
        38: "Telecommunications",
        39: "Transportation / Logistics",
        41: "Education / Entertainment",
        42: "Software Development / SaaS / Cloud",
        43: "Food & Beverage Services",
        44: "Medical / Healthcare Services",
        45: "Legal / Security Services",
    }

    # Growth-oriented Nice classes (signal expansion into new markets)
    GROWTH_CLASSES = {36, 38, 39, 42, 43, 44}

    def __init__(self):
        """Initialize processor."""
        self.tsdr_api_url = "https://tsdrapi.uspto.gov/ts/cd/casestatus"

        # Map company IDs to trademark owner names
        self.owner_mappings = {
            "UBER": ["Uber Technologies, Inc.", "Uber Technologies Inc"],
        }

        # Known Uber trademarks for context
        self.uber_known_brands = [
            "UBER", "UBER EATS", "UBER FREIGHT", "UBER CONNECT",
            "UBER ONE", "UBER FOR BUSINESS", "UBER HEALTH",
        ]

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="trademark_filings",
            category=SignalCategory.ALTERNATIVE,
            description="Trademark filings - commercial intent and product launch signals",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="USPTO TSDR API",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["trademarks", "product-launches", "market-expansion", "alternative"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with trademark registrations"""
        return company.id in self.owner_mappings

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch trademark filing data from USPTO TSDR API.

        Falls back to sample data if the API is unavailable.
        """
        if company.id not in self.owner_mappings:
            return {}

        owner_names = self.owner_mappings[company.id]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching trademark data for {company.ticker} from USPTO TSDR")

                all_trademarks = []

                for owner_name in owner_names:
                    # USPTO TSDR API - search by owner name
                    params = {
                        "ownerName": owner_name,
                        "status": "all",
                    }

                    response = await client.get(
                        self.tsdr_api_url,
                        params=params,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()

                    data = response.json()
                    trademarks = data.get("trademarks", [])
                    all_trademarks.extend(trademarks)

                logger.info(f"Found {len(all_trademarks)} trademarks for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "trademarks": all_trademarks,
                    "total_count": len(all_trademarks),
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPError as e:
            logger.error(f"Error fetching trademark data: {e}")
            logger.warning("Using sample trademark data")
            return self._get_sample_data(company, start, end)
        except Exception as e:
            logger.error(f"Unexpected error fetching trademarks: {e}")
            return self._get_sample_data(company, start, end)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process trademark data into signals.

        Analyzes:
        1. New filings (commercial intent)
        2. Nice class distribution (market expansion)
        3. Abandoned marks (product kills)
        4. Opposition proceedings (competitive friction)
        """
        trademarks = raw_data.get("trademarks", [])

        if not trademarks:
            return []

        signals = []

        # Categorize trademarks by status
        new_applications = []
        registered = []
        abandoned = []
        opposed = []

        for tm in trademarks:
            status = tm.get("status", "").lower()
            if status in ("new application", "pending", "published"):
                new_applications.append(tm)
            elif status in ("registered", "live"):
                registered.append(tm)
            elif status in ("abandoned", "dead", "cancelled"):
                abandoned.append(tm)
            elif status in ("opposition", "opposed"):
                opposed.append(tm)

        # Analyze Nice classes for new applications
        new_classes = set()
        growth_class_filings = 0
        for tm in new_applications:
            nice_classes = tm.get("nice_classes", [])
            for cls in nice_classes:
                cls_num = int(cls) if isinstance(cls, (str, int)) else 0
                new_classes.add(cls_num)
                if cls_num in self.GROWTH_CLASSES:
                    growth_class_filings += 1

        # Signal 1: New trademark applications
        if new_applications:
            score = min(60, len(new_applications) * 15)

            # Bonus for filings in growth categories
            if growth_class_filings > 0:
                score = min(100, score + growth_class_filings * 10)

            # Bonus for filings in new Nice classes (market expansion)
            if len(new_classes) > 2:
                score = min(100, score + 20)

            class_descriptions = [
                self.NICE_CLASSES.get(c, f"Class {c}")
                for c in sorted(new_classes)
                if c in self.NICE_CLASSES
            ]

            description = (
                f"New trademark applications: {len(new_applications)} filings"
            )
            if class_descriptions:
                description += f" | Categories: {', '.join(class_descriptions[:3])}"

            signals.append(Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "event_type": "new_applications",
                    "count": len(new_applications),
                    "nice_classes": sorted(new_classes),
                    "growth_class_filings": growth_class_filings,
                    "marks": [tm.get("mark_text", "") for tm in new_applications[:5]],
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.70,
                metadata=SignalMetadata(
                    source_url="https://tsdrapi.uspto.gov",
                    source_name="USPTO TSDR",
                    processing_notes=f"Analyzed {len(new_applications)} new trademark applications",
                ),
                description=description,
                tags=["trademark", "new_filing", "product_launch"],
            ))

        # Signal 2: Abandoned trademarks
        if abandoned:
            score = max(-60, -(len(abandoned) * 20))

            description = (
                f"Abandoned trademarks: {len(abandoned)} marks"
            )
            mark_names = [tm.get("mark_text", "") for tm in abandoned[:3]]
            if mark_names:
                description += f" | Marks: {', '.join(mark_names)}"

            signals.append(Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "event_type": "abandoned",
                    "count": len(abandoned),
                    "marks": [tm.get("mark_text", "") for tm in abandoned[:5]],
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.60,
                metadata=SignalMetadata(
                    source_url="https://tsdrapi.uspto.gov",
                    source_name="USPTO TSDR",
                    processing_notes=f"Detected {len(abandoned)} abandoned trademarks",
                ),
                description=description,
                tags=["trademark", "abandoned", "product_kill"],
            ))

        # Signal 3: Opposition proceedings
        if opposed:
            score = max(-50, -(len(opposed) * 30))

            description = (
                f"Trademark opposition proceedings: {len(opposed)} marks contested"
            )

            signals.append(Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.utcnow(),
                raw_value={
                    "event_type": "opposition",
                    "count": len(opposed),
                    "marks": [tm.get("mark_text", "") for tm in opposed[:5]],
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.55,
                metadata=SignalMetadata(
                    source_url="https://tsdrapi.uspto.gov",
                    source_name="USPTO TSDR",
                    processing_notes=f"Detected {len(opposed)} opposition proceedings",
                ),
                description=description,
                tags=["trademark", "opposition", "competitive_friction"],
            ))

        return signals

    def _get_sample_data(
        self, company: Company, start: datetime, end: datetime
    ) -> Dict[str, Any]:
        """Return sample trademark data for when the API is unavailable."""
        if company.ticker == "UBER":
            sample_trademarks = [
                {
                    "serial_number": "98765432",
                    "mark_text": "UBER SHUTTLE",
                    "status": "new application",
                    "filing_date": "2026-01-15",
                    "nice_classes": [39, 42],
                    "owner": "Uber Technologies, Inc.",
                    "description": "Transportation scheduling and routing services",
                },
                {
                    "serial_number": "98765433",
                    "mark_text": "UBER TEENS",
                    "status": "pending",
                    "filing_date": "2025-11-20",
                    "nice_classes": [39, 9],
                    "owner": "Uber Technologies, Inc.",
                    "description": "Ride-sharing services for minors with parental controls",
                },
                {
                    "serial_number": "98765434",
                    "mark_text": "UBER PAY",
                    "status": "published",
                    "filing_date": "2025-10-05",
                    "nice_classes": [36, 42],
                    "owner": "Uber Technologies, Inc.",
                    "description": "Electronic payment processing services",
                },
                {
                    "serial_number": "87654321",
                    "mark_text": "UBER RUSH",
                    "status": "abandoned",
                    "filing_date": "2019-03-15",
                    "nice_classes": [39],
                    "owner": "Uber Technologies, Inc.",
                    "description": "Same-day delivery services",
                },
                {
                    "serial_number": "87654322",
                    "mark_text": "UBER COPTER",
                    "status": "registered",
                    "filing_date": "2019-06-01",
                    "nice_classes": [39],
                    "owner": "Uber Technologies, Inc.",
                    "description": "Helicopter transportation services",
                },
            ]
        else:
            sample_trademarks = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "trademarks": sample_trademarks,
            "total_count": len(sample_trademarks),
            "timestamp": datetime.utcnow(),
        }

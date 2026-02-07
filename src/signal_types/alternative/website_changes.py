"""
Website Change Monitor Signal Processor

Tracks changes to company websites for early signals.

Why website changes matter (from ChatGPT research):
"Using Archive.org's Wayback Machine or custom HTML diff tools, you can spot
when a company quietly adds a new product page, removes an offering, or shifts
messaging. For example, if a SaaS company suddenly removes enterprise pricing
from its site, it might signal a pivot. These changes often precede press
releases."

Key Signals:
- New product pages added = product launch imminent
- Pricing page changes = pricing strategy shift
- Job listings added to careers page = hiring surge
- Feature removals = product sunset or pivot
- Press/media page updates = news coming
- Messaging shifts = strategic pivot

Examples:
- Stripe adding crypto page before launch announcement
- Netflix removing DVD rental page before shutdown
- Pricing tier removals before restructuring

Red Flags:
- Multiple features removed = struggling products
- Pricing transparency reduced = pricing power issues
- "Contact us" replacing pricing = desperation
- Careers page emptied = layoffs

Data Source: Archive.org Wayback Machine, custom HTML monitoring
Update Frequency: Weekly
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json
import re

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


class WebsiteChangeProcessor(SignalProcessor):
    """Monitors website changes for strategic signals"""

    # Key pages to monitor
    KEY_PAGES = [
        "/products",
        "/pricing",
        "/features",
        "/careers",
        "/about",
        "/press",
        "/blog",
    ]

    # Change types
    POSITIVE_CHANGES = [
        "new product",
        "new feature",
        "expansion",
        "partnership",
        "hiring",
    ]

    NEGATIVE_CHANGES = [
        "removed",
        "discontinued",
        "sunset",
        "deprecated",
        "legacy",
    ]

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="website_changes",
            category=SignalCategory.ALTERNATIVE,
            description="Website change monitoring - product launches and strategic shifts",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="Website monitoring, Archive.org Wayback Machine",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["website", "html_diff", "product_signals", "strategic_shifts"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with websites"""
        return True  # All companies have websites

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch website changes.

        For POC, use sample data.
        Production would:
        1. Query Archive.org Wayback Machine API
        2. Diff HTML between snapshots
        3. Extract semantic changes (new sections, removed content)
        4. Track specific pages (pricing, products, careers)
        """
        logger.warning("Website monitoring not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process website changes for signals.

        Analyzes:
        1. Type of changes (additions vs removals)
        2. Pages changed (pricing = strategic, products = launches)
        3. Change magnitude (minor update vs major overhaul)
        4. Change velocity (many changes = active development)
        """
        changes = raw_data.get("changes", [])

        if not changes:
            return []

        # Categorize changes
        additions = 0
        removals = 0
        pricing_changes = 0
        product_changes = 0
        careers_changes = 0

        for change in changes:
            change_type = change.get("type", "").lower()
            page = change.get("page", "").lower()
            description = change.get("description", "").lower()

            # Type
            if "added" in change_type or "new" in change_type:
                additions += 1
            elif "removed" in change_type or "deleted" in change_type:
                removals += 1

            # Page significance
            if "pricing" in page:
                pricing_changes += 1
            if "product" in page or "feature" in page:
                product_changes += 1
            if "career" in page or "jobs" in page:
                careers_changes += 1

        # Calculate score
        score = 0

        # Additions generally positive
        score += additions * 15

        # Removals generally negative
        score -= removals * 10

        # Product changes = positive (innovation)
        score += product_changes * 20

        # Pricing changes = neutral (could be good or bad)
        # Careers changes = positive (hiring)
        score += careers_changes * 10

        score = max(-100, min(100, score))

        # Confidence
        confidence = 0.65  # Website changes are moderate confidence

        # Build description
        description = f"Website changes: {len(changes)} change(s)"

        if product_changes > 0:
            description += f" | {product_changes} product page(s)"

        if pricing_changes > 0:
            description += f" | Pricing updated"

        if additions > removals:
            description += " | 🚀 Net additions (growth signal)"
        elif removals > additions:
            description += " | ⚠️ Net removals (contraction)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_changes": len(changes),
                "additions": additions,
                "removals": removals,
                "pricing_changes": pricing_changes,
                "product_changes": product_changes,
                "careers_changes": careers_changes,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://archive.org/web",
                source_name="Website Change Monitor",
                processing_notes=f"{additions} additions, {removals} removals",
                raw_data_hash=hashlib.md5(
                    json.dumps(changes, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["website", "product_signals"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample website change data"""

        if company.ticker == "UBER":
            # Sample: Product expansion
            changes = [
                {
                    "page": "/products/uber-health",
                    "type": "added",
                    "description": "New product page: Uber Health",
                    "timestamp": datetime.utcnow() - timedelta(days=7),
                },
                {
                    "page": "/pricing",
                    "type": "modified",
                    "description": "Pricing tiers updated",
                    "timestamp": datetime.utcnow() - timedelta(days=14),
                },
                {
                    "page": "/careers",
                    "type": "modified",
                    "description": "50 new job listings added",
                    "timestamp": datetime.utcnow() - timedelta(days=3),
                },
            ]
        else:
            changes = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "changes": changes,
            "timestamp": datetime.utcnow(),
        }

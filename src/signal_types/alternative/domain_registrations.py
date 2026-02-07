"""
Domain Registration Tracker Signal Processor

Tracks new domain registrations related to company brands.

Why domain registrations matter (from ChatGPT research):
"A spike in domain registrations (e.g., companyname-newproduct.com) can
hint at an upcoming product launch before official announcements. WHOIS data
is public and searchable. This is rarely monitored systematically."

Key Signals:
- New domains registered with company brand name = product launch signal
- New geographic domains (uber-india.com) = market expansion
- Defensive registrations (common misspellings) = brand protection (neutral)
- Domains registered by competitors = competitive threat
- Multiple related domains in short time = major initiative

Examples:
- apple-vision.com registered 6 months before Vision Pro announcement
- uber-freight.com before Uber Freight launch
- tesla-energy.com before Tesla Energy products

Red Flags:
- Competitor registering similar domains = trademark infringement or confusion
- Third parties registering brand domains = cyber squatting
- No new domains in years = stagnation

Data Source: WHOIS databases, domain monitoring services (free tier available)
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


class DomainRegistrationProcessor(SignalProcessor):
    """Tracks domain registration activity for signals"""

    # Domain categories
    PRODUCT_KEYWORDS = ["app", "product", "service", "platform", "tool"]
    GEOGRAPHIC_KEYWORDS = ["us", "uk", "india", "china", "eu", "asia", "global"]
    DEFENSIVE_KEYWORDS = ["official", "support", "help", "info"]

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="domain_registrations",
            category=SignalCategory.ALTERNATIVE,
            description="Domain registration tracking - early product launch signals",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="WHOIS databases, domain monitoring",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["domains", "product_launches", "expansion", "whois"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all companies with digital presence"""
        return company.is_tech_company or company.has_app

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch domain registration data.

        For POC, use sample data.
        Production would:
        1. Query WHOIS databases for brand-related domains
        2. Monitor domain marketplaces
        3. Track registrations via domain APIs (DomainTools, etc.)
        """
        logger.warning("Domain monitoring not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process domain registrations for signals.

        Analyzes:
        1. New domains registered
        2. Domain type (product, geographic, defensive)
        3. Registration patterns (clusters indicate major initiatives)
        4. Registrar (company vs third-party)
        """
        domains = raw_data.get("domains", [])

        if not domains:
            return []

        # Categorize domains
        product_domains = []
        geographic_domains = []
        defensive_domains = []
        unknown_domains = []

        for domain in domains:
            domain_name = domain.get("name", "").lower()

            # Categorize
            if any(keyword in domain_name for keyword in self.PRODUCT_KEYWORDS):
                product_domains.append(domain)
            elif any(keyword in domain_name for keyword in self.GEOGRAPHIC_KEYWORDS):
                geographic_domains.append(domain)
            elif any(keyword in domain_name for keyword in self.DEFENSIVE_KEYWORDS):
                defensive_domains.append(domain)
            else:
                unknown_domains.append(domain)

        # Calculate score
        # Product domains = positive (new products coming)
        # Geographic = positive (expansion)
        # Defensive = neutral
        # Unknown third-party = neutral/negative

        score = 0

        score += len(product_domains) * 25  # Up to +100 for 4 product domains
        score += len(geographic_domains) * 15  # Geographic expansion positive

        # Cluster bonus: multiple domains in short time = major initiative
        if len(domains) >= 5:
            score += 20

        score = max(-100, min(100, score))

        # Confidence
        confidence = 0.70  # Domain signals are moderate confidence

        # Build description
        description = f"Domain activity: {len(domains)} new domain(s)"

        if product_domains:
            description += f" | {len(product_domains)} product-related"

        if geographic_domains:
            description += f" | {len(geographic_domains)} geographic expansion"

        if len(domains) >= 5:
            description += " | 🚀 Major initiative cluster"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_domains": len(domains),
                "product_domains": len(product_domains),
                "geographic_domains": len(geographic_domains),
                "defensive_domains": len(defensive_domains),
                "unknown_domains": len(unknown_domains),
                "domain_names": [d["name"] for d in domains],
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://whois.com",
                source_name="WHOIS Domain Monitoring",
                processing_notes=f"{len(domains)} domains registered",
                raw_data_hash=hashlib.md5(
                    json.dumps(domains, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["domains", "product_signals"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample domain data"""

        if company.ticker == "UBER":
            # Sample: Product expansion domains
            domains = [
                {
                    "name": "uber-health.com",
                    "registered_date": datetime.utcnow() - timedelta(days=30),
                    "registrar": "GoDaddy",
                },
                {
                    "name": "uber-logistics.com",
                    "registered_date": datetime.utcnow() - timedelta(days=25),
                    "registrar": "GoDaddy",
                },
            ]
        else:
            domains = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "domains": domains,
            "timestamp": datetime.utcnow(),
        }

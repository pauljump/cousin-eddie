"""
Alternative Marketplace Activity Signal Processor

Tracks seller/product activity on alternative marketplaces.

Why marketplace activity matters (from ChatGPT research):
"For consumer brands, tracking Etsy seller counts, eBay completed listings,
or Amazon Best Seller rankings can indicate demand shifts. For example, rising
sales velocity of a company's products on third-party marketplaces = strong
demand. Declining listings = weakening interest."

Key Signals:
- Etsy seller count growth = brand popularity (handmade/crafts)
- eBay completed listing volume = secondary market demand
- Amazon Best Seller rank changes = retail momentum
- Alibaba/AliExpress supplier growth = manufacturing scale
- Walmart Marketplace presence = retail expansion

Examples:
- Nike products surging on eBay = hype/resale demand
- Apple product resale prices dropping = weak demand
- New sellers offering company's products = distribution growth

Red Flags:
- Declining completed listings = demand weakness
- Heavy discounting on marketplaces = excess inventory
- Counterfeit surge = brand protection issues
- Product removals = quality/compliance problems

Data Source: eBay API, Amazon Product Advertising API, marketplace scraping
Update Frequency: Weekly
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json

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


class MarketplaceActivityProcessor(SignalProcessor):
    """Tracks activity on alternative marketplaces"""

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="marketplace_activity",
            category=SignalCategory.ALTERNATIVE,
            description="Alternative marketplace tracking - Etsy, eBay, Amazon seller metrics",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="eBay API, Amazon, Etsy, Alibaba",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["marketplaces", "demand", "sellers", "ecommerce"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to consumer brands and retail companies"""
        # Companies with products sold on marketplaces
        return company.has_physical_locations or company.is_tech_company  # Broad applicability

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch marketplace activity data.

        For POC, use sample data.
        Production would query marketplace APIs.
        """
        logger.warning("Marketplace APIs not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """Process marketplace activity for demand signals"""

        listings = raw_data.get("total_listings", 0)
        completed_sales = raw_data.get("completed_sales", 0)
        avg_price = raw_data.get("average_price", 0)
        seller_count = raw_data.get("seller_count", 0)

        if listings == 0:
            return []

        # Calculate score based on activity metrics
        score = 0
        score += min(completed_sales / 10, 40)  # Up to +40 for sales volume
        score += min(seller_count * 5, 30)  # Up to +30 for seller growth
        score += min((avg_price / 100) * 20, 30)  # Price strength

        score = max(-100, min(100, score))

        description = f"Marketplace: {listings} listings, {completed_sales} sales"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_listings": listings,
                "completed_sales": completed_sales,
                "seller_count": seller_count,
                "average_price": avg_price,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=0.70,
            metadata=SignalMetadata(
                source_url="https://ebay.com",
                source_name="Marketplace Activity",
                processing_notes=f"{listings} listings tracked",
                raw_data_hash=hashlib.md5(
                    json.dumps(raw_data, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["marketplace", "demand"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample marketplace data"""
        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "total_listings": 150,
            "completed_sales": 45,
            "seller_count": 12,
            "average_price": 25.99,
            "timestamp": datetime.utcnow(),
        }

"""
Pricing Intelligence Signal Processor

Tracks product/service pricing changes and competitor pricing.

Why pricing matters:
- Price increases = confidence in demand (bullish)
- Price decreases = competitive pressure or weak demand (bearish)
- Pricing power = moat strength
- Dynamic pricing reveals demand elasticity
- Competitor price gaps = market positioning

Key Metrics:
- Current price vs historical average
- Price change frequency
- Price vs competitors (premium, parity, discount)
- Promotional activity (discounts, deals)
- Price elasticity signals

Signals:
- Price increase = strong demand, pricing power (bullish)
- Price decrease = competition, weak demand (bearish)
- Surge pricing (Uber) = high demand periods
- Promotional activity = struggling to convert
- Closing price gap with premium competitors = brand strength

Use Cases:
- Uber: Surge pricing patterns, base fares
- E-commerce: Product pricing vs Amazon
- SaaS: Plan pricing changes
- Airlines: Ticket price trends
- Hotels: Room rate changes

Data Sources:
1. Web scraping (company websites, app)
2. Third-party price tracking (Keepa for Amazon, Camelcamelcamel)
3. API access (if available)
4. Manual tracking

Update Frequency: Daily
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


class PricingIntelligenceProcessor(SignalProcessor):
    """Track product/service pricing changes"""

    def __init__(self):
        """Initialize processor."""
        # Manual price tracking
        # Format: {company_id: {product: [(date, price, competitors), ...]}}
        self.pricing_snapshots = {
            "UBER": {
                "base_fare_uberx": [
                    ("2026-02-01", 8.50, {"lyft": 8.25}),
                    ("2026-01-01", 8.25, {"lyft": 8.00}),
                    ("2025-12-01", 8.00, {"lyft": 7.75}),
                    ("2025-11-01", 7.75, {"lyft": 7.50}),
                ],
                "uber_eats_delivery_fee": [
                    ("2026-02-01", 4.99, {"doordash": 5.99, "grubhub": 4.99}),
                    ("2026-01-01", 4.99, {"doordash": 5.49, "grubhub": 4.99}),
                    ("2025-12-01", 3.99, {"doordash": 4.99, "grubhub": 3.99}),
                ],
            },
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="pricing_intelligence",
            category=SignalCategory.ALTERNATIVE,
            description="Product/service pricing tracking - pricing power and competitive positioning",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Web scraping / Manual tracking",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["pricing", "competitive_intelligence", "demand"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with trackable pricing"""
        return company.id in self.pricing_snapshots

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch pricing data.

        In production: web scraping or API calls
        For POC: manual snapshots
        """
        if company.id not in self.pricing_snapshots:
            return {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "products": self.pricing_snapshots[company.id],
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process pricing data into signals.

        Analyzes:
        1. Price changes over time
        2. Pricing vs competitors
        3. Pricing power trends
        """
        products = raw_data.get("products", {})

        if not products:
            return []

        signals = []

        for product_name, snapshots in products.items():
            if len(snapshots) < 2:
                continue

            # Sort by date (newest first)
            snapshots = sorted(snapshots, key=lambda x: x[0], reverse=True)

            latest_date, latest_price, latest_competitors = snapshots[0]
            prev_date, prev_price, prev_competitors = snapshots[1]

            # Calculate price change
            price_change = latest_price - prev_price
            price_change_pct = (price_change / prev_price * 100) if prev_price > 0 else 0

            # Calculate competitor positioning
            if latest_competitors:
                competitor_prices = list(latest_competitors.values())
                avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
                price_premium = ((latest_price - avg_competitor_price) / avg_competitor_price * 100) if avg_competitor_price > 0 else 0
            else:
                avg_competitor_price = 0
                price_premium = 0

            # Calculate score
            # Price increase component
            if price_change_pct > 5:
                # Significant price increase = strong pricing power
                price_change_score = min(40, 20 + price_change_pct * 2)
            elif price_change_pct > 0:
                # Small increase = moderate pricing power
                price_change_score = price_change_pct * 4
            elif price_change_pct > -5:
                # Small decrease = slight weakness
                price_change_score = price_change_pct * 3
            else:
                # Large decrease = competitive pressure
                price_change_score = max(-40, -20 + price_change_pct * 2)

            # Competitive positioning component
            if price_premium > 10:
                # Premium pricing = brand strength (if sustainable)
                positioning_score = 20
            elif price_premium > 0:
                # Slight premium = good positioning
                positioning_score = 10
            elif price_premium > -10:
                # Parity pricing = neutral
                positioning_score = 0
            else:
                # Discount pricing = weak positioning
                positioning_score = -15

            total_score = int(price_change_score + positioning_score)
            total_score = max(-100, min(100, total_score))

            # Confidence
            confidence = 0.70

            # Build description
            product_display = product_name.replace("_", " ").title()
            description = f"{product_display}: ${latest_price:.2f} ({price_change_pct:+.1f}%)"

            if price_change_pct > 0:
                description += " | 📈 Price increase (strong demand/pricing power)"
            elif price_change_pct < 0:
                description += " | 📉 Price decrease (competition/weak demand)"

            if latest_competitors:
                comp_names = list(latest_competitors.keys())
                description += f" | vs {', '.join(comp_names)}: {price_premium:+.0f}%"

            signal = Signal(
                company_id=company.id,
                signal_type=f"{self.metadata.signal_type}_{product_name}",
                category=self.metadata.category,
                timestamp=datetime.fromisoformat(latest_date),
                raw_value={
                    "product": product_name,
                    "current_price": latest_price,
                    "price_change_pct": price_change_pct,
                    "competitor_avg": avg_competitor_price,
                    "price_premium_pct": price_premium,
                },
                normalized_value=total_score / 100.0,
                score=total_score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=f"https://www.{company.name.lower().replace(' ', '')}.com",
                    source_name="Pricing Intelligence",
                    processing_notes=f"{price_change_pct:+.1f}% price change, {price_premium:+.0f}% vs competitors",
                    raw_data_hash=hashlib.md5(
                        json.dumps(snapshots, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["pricing", "competitive_intelligence", product_name],
            )

            signals.append(signal)

        return signals

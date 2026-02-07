"""
Credit Card Transaction Data Signal Processor

Tracks aggregated credit card spending as a real-time revenue proxy.

Why credit card data matters:
- Real-time revenue proxy (weeks before earnings)
- Most accurate alternative data source
- Transaction volume = customer demand
- Spending trends = business momentum
- Geographic/demographic breakdowns
- Leading indicator for quarterly results

Key Metrics:
- Total transaction volume (dollars)
- Transaction count
- Average transaction size
- Month-over-month growth
- Year-over-year growth
- Geographic breakdown
- Customer cohort analysis

Signals:
- Transaction growth >10% MoM = very bullish (revenue beat likely)
- Transaction decline = bearish (revenue miss risk)
- Increasing avg transaction = upsell success
- Decreasing avg transaction = discounting/weakness

Data Providers:
1. Second Measure (most comprehensive, expensive)
2. Earnest Research
3. Affinity Solutions
4. Yodlee
5. M Science

Limitations:
- Very expensive ($10k-$100k+/year)
- Limited to B2C companies
- Privacy concerns
- Sample bias (not all cardholders)

Coverage:
- Retail: High coverage (Target, Walmart, etc.)
- Restaurants: Medium coverage
- E-commerce: High coverage (Amazon, etc.)
- Ride-sharing: Medium coverage (Uber, Lyft)
- Travel: High coverage (airlines, hotels)

Update Frequency: Daily (real-time data)
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


class CreditCardTransactionsProcessor(SignalProcessor):
    """Track aggregated credit card transaction data"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize processor.

        Args:
            api_key: Second Measure / alternative data provider API key
        """
        self.api_key = api_key

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="credit_card_transactions",
            category=SignalCategory.ALTERNATIVE,
            description="Credit card transaction data - real-time revenue proxy",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Second Measure / Alternative data providers",
            cost=DataCost.PAID,
            difficulty=Difficulty.HARD,
            tags=["credit_card", "transactions", "revenue_proxy", "alternative_data"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to B2C companies with credit card transactions"""
        # For now, only Uber in POC
        return company.id == "UBER"

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch credit card transaction data.

        For POC, uses sample data.
        Production requires expensive data provider subscription.
        """
        if not self.api_key:
            logger.warning("Credit card data provider not configured - using sample data")
            return self._get_sample_data(company)

        # In production, call Second Measure API here
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process transaction data into signals.

        Analyzes:
        1. Transaction volume growth
        2. Transaction count trends
        3. Average ticket size
        """
        transactions = raw_data.get("transactions", {})

        if not transactions:
            return []

        current_volume = transactions.get("current_month_volume", 0)
        previous_volume = transactions.get("previous_month_volume", 0)
        current_count = transactions.get("current_month_count", 0)
        previous_count = transactions.get("previous_month_count", 0)

        # Calculate growth
        if previous_volume > 0:
            volume_growth = ((current_volume - previous_volume) / previous_volume) * 100
        else:
            volume_growth = 0

        if previous_count > 0:
            count_growth = ((current_count - previous_count) / previous_count) * 100
        else:
            count_growth = 0

        # Calculate average transaction size
        current_avg = current_volume / current_count if current_count > 0 else 0
        previous_avg = previous_volume / previous_count if previous_count > 0 else 0

        if previous_avg > 0:
            avg_change = ((current_avg - previous_avg) / previous_avg) * 100
        else:
            avg_change = 0

        # Calculate score
        # Volume growth is primary signal
        if volume_growth > 15:
            volume_score = min(70, 50 + volume_growth * 1.5)
        elif volume_growth > 5:
            volume_score = 30 + (volume_growth - 5) * 2
        elif volume_growth > 0:
            volume_score = volume_growth * 6
        elif volume_growth > -5:
            volume_score = volume_growth * 8
        else:
            volume_score = max(-70, -50 + volume_growth * 2)

        # Average ticket size component
        if avg_change > 5:
            avg_score = 20  # Upselling success
        elif avg_change > 0:
            avg_score = 10
        elif avg_change > -5:
            avg_score = 0
        else:
            avg_score = -15  # Discounting/weakness

        total_score = int(volume_score + avg_score)
        total_score = max(-100, min(100, total_score))

        # Confidence - very high for credit card data
        confidence = 0.90  # Most accurate alternative data

        # Build description
        description = f"Credit card transactions: ${current_volume/1e6:.1f}M volume ({volume_growth:+.1f}% MoM)"
        description += f" | {current_count:,} transactions ({count_growth:+.1f}%)"
        description += f" | Avg ticket: ${current_avg:.2f} ({avg_change:+.1f}%)"

        if volume_growth > 10:
            description += " 🚀 Strong growth (revenue beat likely)"
        elif volume_growth < -5:
            description += " ⚠ Declining (revenue miss risk)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "current_month_volume": current_volume,
                "volume_growth_pct": volume_growth,
                "current_month_count": current_count,
                "count_growth_pct": count_growth,
                "avg_transaction": current_avg,
                "avg_change_pct": avg_change,
            },
            normalized_value=total_score / 100.0,
            score=total_score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://www.secondmeasure.com",
                source_name="Second Measure (Credit Card Panel)",
                processing_notes=f"${current_volume/1e6:.1f}M volume, {volume_growth:+.1f}% MoM",
                raw_data_hash=hashlib.md5(
                    json.dumps(transactions, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["credit_card", "transactions", "revenue_proxy"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample credit card transaction data"""
        if company.ticker == "UBER":
            # Sample monthly transaction data
            sample_transactions = {
                "current_month_volume": 2850000000,  # $2.85B
                "previous_month_volume": 2720000000,  # $2.72B
                "current_month_count": 95000000,  # 95M transactions
                "previous_month_count": 91000000,  # 91M transactions
                "current_month": "2026-01",
                "panel_size": 5000000,  # 5M cardholders
                "coverage_pct": 2.5,  # 2.5% of all US cardholders
            }
        else:
            sample_transactions = {}

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "transactions": sample_transactions,
            "timestamp": datetime.utcnow(),
        }

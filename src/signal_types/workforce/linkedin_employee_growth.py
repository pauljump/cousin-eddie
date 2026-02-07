"""
LinkedIn Employee Growth Signal Processor

Tracks employee headcount changes as a leading indicator of company growth.

Why employee growth matters:
- Hiring = growth expectations (bullish)
- Layoffs = cost cuts or weakness (bearish)
- Department-specific hiring reveals strategy (AI team growth, sales expansion)
- Senior hires = new initiatives
- Executive departures = problems

Key Metrics:
- Total employee count
- Month-over-month growth rate
- Department growth (Engineering, Sales, Marketing)
- Geographic expansion (new office locations)
- Senior hires (Director+, VP+, C-level)
- Employee departures (churn rate)

Signals:
- Rapid headcount growth (>5% MoM) = very bullish
- Moderate growth (2-5% MoM) = bullish
- Flat headcount (0-2% MoM) = neutral
- Declining headcount = bearish (layoffs, attrition)
- Executive departures = very bearish

LinkedIn provides:
- Company page shows "X employees on LinkedIn"
- Historical snapshots (if tracked over time)
- Employee list (public profiles)
- Job postings (hiring intent)

Data Sources:
1. LinkedIn API (requires partnership - expensive)
2. Web scraping (rate limited, requires auth)
3. Third-party data providers (Thinknum, AlternativeData.org)
4. Manual tracking (periodic snapshots)

Update Frequency: Monthly (LinkedIn updates slowly)
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


class LinkedInEmployeeGrowthProcessor(SignalProcessor):
    """Track employee headcount changes via LinkedIn"""

    def __init__(self):
        """Initialize processor."""
        # Manual employee count tracking
        # Format: {company_id: [(date, employee_count, notes), ...]}
        # In production, this would come from a database or API
        self.employee_snapshots = {
            "UBER": [
                ("2026-02-01", 32450, "Steady growth"),
                ("2026-01-01", 32100, "Post-holiday hiring"),
                ("2025-12-01", 31800, "Q4 headcount"),
                ("2025-11-01", 31500, "Pre-holiday freeze"),
                ("2025-10-01", 31200, "Expansion phase"),
                ("2025-09-01", 30800, "Q3 hiring push"),
            ],
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="linkedin_employee_growth",
            category=SignalCategory.WORKFORCE,
            description="Employee headcount growth tracking via LinkedIn",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="LinkedIn (manual tracking)",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["linkedin", "employee_growth", "headcount", "hiring"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to companies with LinkedIn presence"""
        return company.id in self.employee_snapshots

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch employee count data.

        In production, this would:
        1. Scrape LinkedIn company page
        2. Query third-party data provider
        3. Use LinkedIn API (if available)

        For POC, we use manual snapshots.
        """
        if company.id not in self.employee_snapshots:
            return {}

        snapshots = self.employee_snapshots[company.id]

        # Convert to dict format
        snapshot_data = []
        for date_str, count, notes in snapshots:
            snapshot_data.append({
                "date": date_str,
                "employee_count": count,
                "notes": notes,
            })

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "snapshots": snapshot_data,
            "timestamp": datetime.utcnow(),
        }

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process employee growth data into signals.

        Calculates:
        1. Month-over-month growth rate
        2. Trend (accelerating, steady, decelerating)
        3. Absolute growth numbers
        """
        snapshots = raw_data.get("snapshots", [])

        if len(snapshots) < 2:
            logger.warning(f"Need at least 2 snapshots for growth calc - only have {len(snapshots)}")
            return []

        # Sort by date (newest first)
        snapshots = sorted(snapshots, key=lambda x: x["date"], reverse=True)

        # Calculate MoM growth
        latest = snapshots[0]
        previous = snapshots[1]

        latest_count = latest["employee_count"]
        previous_count = previous["employee_count"]

        growth_absolute = latest_count - previous_count
        growth_rate = (growth_absolute / previous_count) * 100 if previous_count > 0 else 0

        # Calculate score based on growth rate
        # >5% MoM = +80 to +100 (very bullish)
        # 2-5% MoM = +40 to +80 (bullish)
        # 0-2% MoM = 0 to +40 (neutral/slightly positive)
        # -2 to 0% = 0 to -40 (slightly negative)
        # < -2% = -40 to -100 (bearish - layoffs)

        if growth_rate > 5:
            score = min(100, 80 + (growth_rate - 5) * 4)
        elif growth_rate > 2:
            score = 40 + (growth_rate - 2) * 13
        elif growth_rate > 0:
            score = growth_rate * 20
        elif growth_rate > -2:
            score = growth_rate * 20
        else:
            score = max(-100, -40 + (growth_rate + 2) * 10)

        score = int(score)

        # Check for trend (accelerating vs decelerating)
        trend = "steady"
        if len(snapshots) >= 3:
            older = snapshots[2]
            older_count = older["employee_count"]
            prev_growth_rate = (previous_count - older_count) / older_count * 100 if older_count > 0 else 0

            if growth_rate > prev_growth_rate + 1:
                trend = "accelerating"
                score += 10  # Bonus for acceleration
            elif growth_rate < prev_growth_rate - 1:
                trend = "decelerating"
                score -= 10  # Penalty for deceleration

        score = max(-100, min(100, score))

        # Confidence based on data recency
        latest_date = datetime.fromisoformat(latest["date"])
        days_old = (datetime.utcnow() - latest_date).days

        if days_old < 7:
            confidence = 0.85
        elif days_old < 30:
            confidence = 0.75
        elif days_old < 60:
            confidence = 0.65
        else:
            confidence = 0.55

        # Build description
        direction = "growth" if growth_absolute > 0 else "decline"
        description = f"LinkedIn: {growth_rate:+.1f}% MoM employee {direction}"
        description += f" ({latest_count:,} employees, {growth_absolute:+,} from previous month)"

        if trend == "accelerating":
            description += " | 📈 Accelerating hiring"
        elif trend == "decelerating":
            description += " | 📉 Hiring slowdown"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=latest_date,
            raw_value={
                "latest_count": latest_count,
                "previous_count": previous_count,
                "growth_absolute": growth_absolute,
                "growth_rate_pct": growth_rate,
                "trend": trend,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://www.linkedin.com/company/{company.name.lower().replace(' ', '-')}",
                source_name="LinkedIn",
                processing_notes=f"MoM growth: {growth_rate:+.1f}% ({trend})",
                raw_data_hash=hashlib.md5(
                    json.dumps(snapshots, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["linkedin", "employee_growth", "hiring", trend],
        )

        return [signal]

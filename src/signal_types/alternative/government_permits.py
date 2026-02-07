"""
Government Permits & Violations Tracking

Tracks EPA violations, building permits, and government compliance.

Why permits matter (from ChatGPT research):
"State and local government databases often publish permits (building permits,
environmental violations, liquor licenses). A surge in building permits for a
retailer = expansion. EPA violations = regulatory risk."

Data Source: EPA Enforcement Database, local building permit databases
Update Frequency: Monthly
"""

from typing import List, Any, Dict
from datetime import datetime
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


class GovernmentPermitsProcessor(SignalProcessor):
    """Tracks government permits and violations"""

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="government_permits",
            category=SignalCategory.REGULATORY,
            description="Government permits - EPA violations, building permits, compliance",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="EPA Database, local permit databases",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["permits", "compliance", "epa", "expansion"],
        )

    def is_applicable(self, company: Company) -> bool:
        return company.has_physical_locations

    async def fetch(self, company: Company, start: datetime, end: datetime) -> Dict:
        logger.warning("Permit databases not fully implemented - using sample data")
        return {"company_id": company.id, "permits": [], "violations": []}

    def process(self, company: Company, raw_data: Dict) -> List[Signal]:
        permits = len(raw_data.get("permits", []))
        violations = len(raw_data.get("violations", []))

        if permits == 0 and violations == 0:
            return []

        score = permits * 15 - violations * 30
        score = max(-100, min(100, score))

        return [Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={"permits": permits, "violations": violations},
            normalized_value=score / 100.0,
            score=score,
            confidence=0.80,
            metadata=SignalMetadata(
                source_url="https://echo.epa.gov",
                source_name="Government Permits",
                processing_notes=f"{permits} permits, {violations} violations",
                raw_data_hash=hashlib.md5(json.dumps(raw_data, sort_keys=True).encode()).hexdigest(),
            ),
            description=f"Permits: {permits} issued, {violations} violations",
            tags=["permits", "compliance"],
        )]

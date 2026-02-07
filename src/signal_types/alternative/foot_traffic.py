"""
Foot Traffic / Geolocation Data Processor

Tracks store visit patterns and foot traffic.

Why foot traffic matters (from ChatGPT research):
"Geo-location data from apps (aggregated/anonymized) can show foot traffic
to retail stores or restaurants. SafeGraph and Placer.ai offer some free data.
Declining foot traffic often precedes poor earnings."

Data Source: SafeGraph (limited free tier), aggregated GPS data
Update Frequency: Weekly
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


class FootTrafficProcessor(SignalProcessor):
    """Tracks foot traffic and geolocation data"""

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="foot_traffic",
            category=SignalCategory.ALTERNATIVE,
            description="Foot traffic tracking - store visits, geolocation patterns",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="SafeGraph, aggregated GPS data",
            cost=DataCost.FREEMIUM,
            difficulty=Difficulty.HARD,
            tags=["foot_traffic", "geolocation", "retail", "visits"],
        )

    def is_applicable(self, company: Company) -> bool:
        return company.has_physical_locations

    async def fetch(self, company: Company, start: datetime, end: datetime) -> Dict:
        logger.warning("Foot traffic data not fully implemented - using sample data")
        return {"company_id": company.id, "visit_count": 0, "trend": "stable"}

    def process(self, company: Company, raw_data: Dict) -> List[Signal]:
        visits = raw_data.get("visit_count", 0)
        trend = raw_data.get("trend", "stable")

        if visits == 0:
            return []

        score = 0
        if trend == "increasing":
            score = 50
        elif trend == "decreasing":
            score = -50

        return [Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={"visits": visits, "trend": trend},
            normalized_value=score / 100.0,
            score=score,
            confidence=0.80,
            metadata=SignalMetadata(
                source_url="https://safegraph.com",
                source_name="Foot Traffic Data",
                processing_notes=f"{visits} visits, {trend}",
                raw_data_hash=hashlib.md5(json.dumps(raw_data, sort_keys=True).encode()).hexdigest(),
            ),
            description=f"Foot traffic: {visits} visits ({trend})",
            tags=["foot_traffic", "retail"],
        )]

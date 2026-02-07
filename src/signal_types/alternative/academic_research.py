"""
Academic Research & Grant Tracking Signal Processor

Tracks academic citations and research grants.

Why academic research matters (from ChatGPT research):
"For some sectors (biotech, AI, semiconductors), tracking NIH grants, DoD R&D
contracts, or Google Scholar citations of key researchers can signal innovation.
A surge in academic interest = technology validation."

Key Signals:
- NIH grants awarded = federal R&D funding (biotech/pharma)
- DoD contracts = defense/aerospace funding
- Google Scholar citations = academic validation
- Patent citations = technology importance
- University partnerships = innovation pipeline

Red Flags:
- Grant funding drying up = technology not competitive
- Declining citations = research interest waning
- Loss of key researchers = brain drain

Data Source: NIH RePORTER, Google Scholar, patent databases
Update Frequency: Monthly
"""

from typing import List, Any, Dict, Optional
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


class AcademicResearchProcessor(SignalProcessor):
    """Tracks academic research and grants"""

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="academic_research",
            category=SignalCategory.ALTERNATIVE,
            description="Academic research tracking - grants, citations, partnerships",
            update_frequency=UpdateFrequency.MONTHLY,
            data_source="NIH RePORTER, Google Scholar, DoD contracts",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["research", "grants", "academia", "innovation"],
        )

    def is_applicable(self, company: Company) -> bool:
        return company.is_tech_company  # Tech/biotech companies have research activity

    async def fetch(self, company: Company, start: datetime, end: datetime) -> Dict[str, Any]:
        logger.warning("Academic research APIs not fully implemented - using sample data")
        return {"company_id": company.id, "grants": [], "citations": 0}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        grants = len(raw_data.get("grants", []))
        citations = raw_data.get("citations", 0)

        if grants == 0 and citations == 0:
            return []

        score = min(grants * 20 + citations / 100, 100)

        return [Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={"grants": grants, "citations": citations},
            normalized_value=score / 100.0,
            score=score,
            confidence=0.75,
            metadata=SignalMetadata(
                source_url="https://reporter.nih.gov",
                source_name="Academic Research",
                processing_notes=f"{grants} grants",
                raw_data_hash=hashlib.md5(json.dumps(raw_data, sort_keys=True).encode()).hexdigest(),
            ),
            description=f"Research: {grants} grants, {citations} citations",
            tags=["research", "grants"],
        )]

"""
Clinical Trials Tracker Signal Processor

Tracks clinical trial activity for pharma/biotech companies.

Why clinical trials matter (from ChatGPT research):
"For pharma or biotech, clinicaltrials.gov is a free resource listing new trials,
phase advancements, and results. A trial moving from Phase II to Phase III is
a positive signal; a trial halted early is negative. Few retail investors
systematically monitor this."

Key Signals:
- New trials initiated = R&D pipeline growth (positive)
- Phase advancement (I→II, II→III) = progress (very positive)
- Trial completion with positive results = FDA approval path (very positive)
- Trial termination/suspension = failure (very negative)
- Enrollment speed = confidence in drug (fast = positive)
- Investigator-initiated trials = academic interest (positive)

Phase Progression:
- Phase I: Safety testing (50-100 patients)
- Phase II: Efficacy testing (100-500 patients)
- Phase III: Large-scale efficacy (1000+ patients, expensive)
- Phase IV: Post-market surveillance

Red Flags:
- Trials halted early = safety/efficacy concerns
- Slow enrollment = lack of interest
- Multiple Phase III failures = pipeline trouble
- No new trials in years = stagnation

Data Source: ClinicalTrials.gov API (free, public)
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


class ClinicalTrialsProcessor(SignalProcessor):
    """Tracks clinical trial activity for pharma/biotech"""

    # Trial statuses
    POSITIVE_STATUSES = [
        "Completed",
        "Active, not recruiting",
        "Enrolling by invitation",
    ]

    NEUTRAL_STATUSES = [
        "Recruiting",
        "Not yet recruiting",
        "Enrolling",
    ]

    NEGATIVE_STATUSES = [
        "Terminated",
        "Suspended",
        "Withdrawn",
    ]

    # Phase scores
    PHASE_SCORES = {
        "Phase 1": 10,
        "Phase 2": 25,
        "Phase 3": 50,
        "Phase 4": 15,
    }

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="clinical_trials",
            category=SignalCategory.ALTERNATIVE,
            description="Clinical trial tracking - pharma/biotech R&D pipeline",
            update_frequency=UpdateFrequency.WEEKLY,
            data_source="ClinicalTrials.gov API",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["clinical_trials", "pharma", "biotech", "fda", "pipeline"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable only to pharma/biotech companies"""
        # For now, filter by industry or tags
        # In production, check company.industry == "Pharmaceuticals" or "Biotechnology"
        return False  # UBER is not pharma - would be True for pharma companies

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch clinical trials data.

        For POC, use sample data.
        Production would:
        1. Query ClinicalTrials.gov API
        2. Filter by company/sponsor name
        3. Track phase changes over time
        4. Monitor enrollment rates
        """
        logger.warning("ClinicalTrials.gov API not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process clinical trial data for signals.

        Analyzes:
        1. New trials initiated
        2. Phase advancements
        3. Trial completions vs terminations
        4. Enrollment progress
        """
        trials = raw_data.get("trials", [])

        if not trials:
            return []

        # Metrics
        total_trials = len(trials)
        phase_1_count = 0
        phase_2_count = 0
        phase_3_count = 0
        completed_count = 0
        terminated_count = 0
        new_trials = 0

        for trial in trials:
            phase = trial.get("phase", "")
            status = trial.get("status", "")
            start_date = trial.get("start_date")

            # Count by phase
            if "Phase 1" in phase:
                phase_1_count += 1
            if "Phase 2" in phase:
                phase_2_count += 1
            if "Phase 3" in phase:
                phase_3_count += 1

            # Count by status
            if status in self.POSITIVE_STATUSES:
                completed_count += 1
            elif status in self.NEGATIVE_STATUSES:
                terminated_count += 1

            # New trials (started in last 90 days)
            if start_date and (datetime.utcnow() - start_date).days < 90:
                new_trials += 1

        # Calculate score
        score = 0

        # Phase 3 trials are most valuable
        score += phase_3_count * 40  # Phase 3 = high value

        # Phase 2 = moderate value
        score += phase_2_count * 20

        # Phase 1 = early stage
        score += phase_1_count * 10

        # Completions = very positive
        score += completed_count * 30

        # Terminations = very negative
        score -= terminated_count * 50

        # New trials = positive (active R&D)
        score += new_trials * 15

        score = max(-100, min(100, score))

        # Confidence
        confidence = min(0.90, 0.75 + (total_trials / 50))  # More trials = higher confidence

        # Build description
        description = f"Clinical trials: {total_trials} active"

        if phase_3_count > 0:
            description += f" | {phase_3_count} Phase III"

        if completed_count > 0:
            description += f" | {completed_count} completed"

        if terminated_count > 0:
            description += f" | ⚠️ {terminated_count} terminated"

        if new_trials > 2:
            description += " | 🚀 Strong R&D activity"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_trials": total_trials,
                "phase_1": phase_1_count,
                "phase_2": phase_2_count,
                "phase_3": phase_3_count,
                "completed": completed_count,
                "terminated": terminated_count,
                "new_trials": new_trials,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://clinicaltrials.gov",
                source_name="ClinicalTrials.gov",
                processing_notes=f"{total_trials} trials, {phase_3_count} Phase III",
                raw_data_hash=hashlib.md5(
                    json.dumps(trials, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["clinical_trials", "r&d", "pipeline"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample clinical trial data"""

        # Sample data for a hypothetical pharma company
        # (UBER doesn't have trials, so this would return empty for UBER)
        trials = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "trials": trials,
            "timestamp": datetime.utcnow(),
        }

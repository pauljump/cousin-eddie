"""
Earnings Call Q&A Tone Analysis Signal Processor

Analyzes CEO/CFO behavior and tone during Q&A section of earnings calls.

Why Q&A matters (from ChatGPT research):
"Most sentiment tools lump the entire transcript together. But Q&A often reveals
more than prepared remarks. A CEO's tone when challenged (defensive vs. confident),
how many times they dodge a question, or the number of 'tough' analyst questions
can be a leading indicator of trouble. Parsing Q&A separately and tracking
evasiveness or shifts in tone is rarely done by retail traders."

Key Signals:
- Evasiveness: How many questions are dodged or answered vaguely
- Defensive Tone: CEO gets defensive when challenged
- Uncertainty Language: "we'll see", "maybe", "hopefully", "trying"
- Overly Optimistic: Too many superlatives when answering tough questions
- Question Quality: Are analysts asking pointed/skeptical questions?

Red Flags:
- CEO avoids specific revenue/margin questions = hiding problems
- Tone shifts from prepared remarks to Q&A = not confident
- Multiple "I don't have that number" responses = unprepared or hiding
- Long rambling answers = evasion
- Excessive hedging language = uncertainty

Data Source: Publicly available earnings call transcripts (Seeking Alpha, EDGAR)
Update Frequency: Quarterly
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json
import re

import httpx
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


class EarningsCallQAToneProcessor(SignalProcessor):
    """Analyzes Q&A section tone and evasiveness in earnings calls"""

    # Evasiveness indicators
    EVASIVE_PHRASES = [
        "i don't have that number",
        "i'll get back to you",
        "i'll have to check",
        "we'll provide more detail later",
        "we're not disclosing",
        "we're not breaking out",
        "we're not guiding",
        "we don't provide guidance on",
        "that's a good question but",
        "i can't comment on that",
    ]

    # Uncertainty language
    UNCERTAINTY_WORDS = [
        "maybe",
        "hopefully",
        "we'll see",
        "trying",
        "attempting",
        "working on",
        "looking at",
        "considering",
        "might",
        "could",
        "possibly",
    ]

    # Defensive language
    DEFENSIVE_PHRASES = [
        "as i said",
        "like i mentioned",
        "i already answered that",
        "we've been clear",
        "to be clear",
        "let me be clear",
        "i think i addressed that",
    ]

    # Overly optimistic superlatives
    SUPERLATIVES = [
        "incredible",
        "amazing",
        "fantastic",
        "unprecedented",
        "tremendous",
        "outstanding",
        "exceptional",
        "extraordinary",
    ]

    # Tough question keywords (analyst skepticism)
    TOUGH_QUESTION_KEYWORDS = [
        "concern",
        "worried",
        "challenge",
        "pressure",
        "weakness",
        "decline",
        "miss",
        "below expectations",
        "disappointing",
        "shortfall",
    ]

    def __init__(self):
        """Initialize processor"""
        pass

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="earnings_call_qa_tone",
            category=SignalCategory.ALTERNATIVE,
            description="Earnings call Q&A tone analysis - evasiveness and CEO behavior",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="Earnings Call Transcripts",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["earnings_calls", "sentiment", "management_tone", "q_and_a"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all public companies"""
        return company.has_sec_filings  # Public companies have earnings calls

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch earnings call transcripts and extract Q&A section.

        For POC, use sample data.
        Production would:
        1. Fetch from Seeking Alpha / EDGAR 8-K exhibits
        2. Parse transcript to separate prepared remarks from Q&A
        3. Extract questions and answers
        """
        logger.warning("Transcript Q&A parsing not fully implemented - using sample data")
        return self._get_sample_data(company)

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process Q&A section for tone and evasiveness signals.

        Analyzes:
        1. Evasiveness: How often CEO dodges questions
        2. Uncertainty: Hedging language frequency
        3. Defensiveness: CEO gets defensive
        4. Over-optimism: Excessive superlatives
        5. Question quality: Are analysts skeptical?
        """
        qa_exchanges = raw_data.get("qa_exchanges", [])

        if not qa_exchanges:
            return []

        # Metrics
        total_exchanges = len(qa_exchanges)
        evasive_count = 0
        uncertainty_count = 0
        defensive_count = 0
        superlative_count = 0
        tough_question_count = 0

        for exchange in qa_exchanges:
            question = exchange.get("question", "").lower()
            answer = exchange.get("answer", "").lower()

            # Count tough questions
            for keyword in self.TOUGH_QUESTION_KEYWORDS:
                if keyword in question:
                    tough_question_count += 1
                    break  # Count once per question

            # Count evasiveness in answers
            for phrase in self.EVASIVE_PHRASES:
                if phrase in answer:
                    evasive_count += 1

            # Count uncertainty
            for word in self.UNCERTAINTY_WORDS:
                uncertainty_count += answer.count(word)

            # Count defensiveness
            for phrase in self.DEFENSIVE_PHRASES:
                if phrase in answer:
                    defensive_count += 1

            # Count superlatives (can indicate over-optimism when answering tough questions)
            for word in self.SUPERLATIVES:
                superlative_count += answer.count(word)

        # Calculate score
        # Negative signals: evasiveness, defensiveness, uncertainty
        # Context matters: tough questions + evasiveness = very bad

        score = 0

        # Evasiveness penalty
        evasiveness_rate = evasive_count / max(total_exchanges, 1)
        score -= evasiveness_rate * 50  # Up to -50 points

        # Uncertainty penalty
        uncertainty_rate = uncertainty_count / max(total_exchanges, 1)
        score -= min(uncertainty_rate * 20, 30)  # Up to -30 points

        # Defensiveness penalty
        defensive_rate = defensive_count / max(total_exchanges, 1)
        score -= defensive_rate * 30  # Up to -30 points

        # Tough questions = negative (shows analyst concern)
        tough_rate = tough_question_count / max(total_exchanges, 1)
        score -= tough_rate * 20  # Up to -20 points

        # Normalize to -100 to +100
        score = max(-100, min(0, score))

        # Confidence
        confidence = min(0.90, 0.70 + (total_exchanges / 50))  # More exchanges = higher confidence

        # Build description
        description = f"Q&A analysis: {total_exchanges} exchanges"

        if evasiveness_rate > 0.3:
            description += " | 🚨 HIGH EVASIVENESS"

        if tough_question_count > total_exchanges * 0.4:
            description += " | ⚠️ Skeptical analysts"

        if defensive_count > 3:
            description += " | Defensive tone"

        if uncertainty_count > total_exchanges * 2:
            description += " | High uncertainty language"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_exchanges": total_exchanges,
                "evasive_count": evasive_count,
                "uncertainty_count": uncertainty_count,
                "defensive_count": defensive_count,
                "superlative_count": superlative_count,
                "tough_question_count": tough_question_count,
                "evasiveness_rate": round(evasiveness_rate, 2),
                "tough_question_rate": round(tough_rate, 2),
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url="https://seekingalpha.com",
                source_name="Earnings Call Transcripts",
                processing_notes=f"{evasive_count} evasive, {tough_question_count} tough questions",
                raw_data_hash=hashlib.md5(
                    json.dumps(qa_exchanges, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["earnings_call", "q_and_a", "management_tone"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """Return sample Q&A data"""

        if company.ticker == "UBER":
            # Sample: Moderately evasive Q&A
            qa_exchanges = [
                {
                    "question": "Can you provide more color on the decline in take rates?",
                    "answer": "I don't have that number in front of me right now, but we'll provide more detail in our investor deck. Overall, we're seeing tremendous growth in the platform.",
                },
                {
                    "question": "Are you concerned about increasing competition from autonomous vehicles?",
                    "answer": "We'll see how that plays out. We're working on our own autonomous initiatives. It's a great opportunity for us.",
                },
                {
                    "question": "Your guidance was below expectations. What's driving the weakness?",
                    "answer": "As I mentioned earlier, we're investing heavily for long-term growth. We remain very optimistic about our position.",
                },
            ]
        else:
            qa_exchanges = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "qa_exchanges": qa_exchanges,
            "timestamp": datetime.utcnow(),
        }

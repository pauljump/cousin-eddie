"""Signal Processor abstract base class - the core extension interface"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

from .company import Company
from .signal import Signal, SignalCategory, SignalMetadata


class UpdateFrequency(str, Enum):
    """How often a signal type updates"""
    REALTIME = "realtime"  # Continuous / event-driven
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class DataCost(str, Enum):
    """Cost to acquire data"""
    FREE = "free"
    FREEMIUM = "freemium"  # Free tier available
    PAID = "paid"


class Difficulty(str, Enum):
    """Difficulty to implement/maintain"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SignalProcessorMetadata:
    """Metadata describing a signal processor"""

    def __init__(
        self,
        signal_type: str,
        category: SignalCategory,
        description: str,
        update_frequency: UpdateFrequency,
        data_source: str,
        cost: DataCost,
        difficulty: Difficulty,
        tags: Optional[List[str]] = None,
    ):
        self.signal_type = signal_type
        self.category = category
        self.description = description
        self.update_frequency = update_frequency
        self.data_source = data_source
        self.cost = cost
        self.difficulty = difficulty
        self.tags = tags or []


class SignalProcessor(ABC):
    """
    Abstract base class for all signal processors.

    Each signal type (SEC Form 4, job postings, app reviews, etc.) implements this interface.
    This is the core extension point of the platform.

    Example implementation:

        class SECForm4Processor(SignalProcessor):
            @property
            def metadata(self) -> SignalProcessorMetadata:
                return SignalProcessorMetadata(
                    signal_type="sec_form_4",
                    category=SignalCategory.REGULATORY,
                    description="Insider trading filings",
                    update_frequency=UpdateFrequency.REALTIME,
                    data_source="SEC EDGAR",
                    cost=DataCost.FREE,
                    difficulty=Difficulty.MEDIUM
                )

            def is_applicable(self, company: Company) -> bool:
                return company.has_sec_filings

            async def fetch(self, company: Company, start: datetime, end: datetime):
                # Call SEC API
                return edgar_api.get_form4(company.cik, start, end)

            def process(self, company: Company, raw_data: Any) -> List[Signal]:
                # Parse filings and return signals
                signals = []
                for filing in raw_data:
                    signal = Signal(
                        company_id=company.id,
                        signal_type=self.metadata.signal_type,
                        category=self.metadata.category,
                        timestamp=filing.filing_date,
                        raw_value=filing.to_dict(),
                        normalized_value=self._normalize(filing),
                        score=self._score(filing),
                        confidence=self._calculate_confidence(filing),
                        metadata=SignalMetadata(...)
                    )
                    signals.append(signal)
                return signals

            def score(self, signal: Signal) -> int:
                # Already scored during process()
                return signal.score
    """

    @property
    @abstractmethod
    def metadata(self) -> SignalProcessorMetadata:
        """
        Return metadata describing this signal processor.

        Returns:
            SignalProcessorMetadata with signal type, category, description, etc.
        """
        pass

    @abstractmethod
    def is_applicable(self, company: Company) -> bool:
        """
        Determine if this signal type can be applied to the given company.

        Args:
            company: Company to check

        Returns:
            True if this signal can be collected for this company

        Example:
            - SEC filings: applicable to all public companies
            - App store data: only applicable if company.has_app == True
            - Parking lot satellite data: only if company.has_physical_locations == True
        """
        pass

    @abstractmethod
    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Any:
        """
        Fetch raw data from the source.

        Args:
            company: Company to fetch data for
            start: Start of time range
            end: End of time range

        Returns:
            Raw data from source (format depends on implementation)

        Raises:
            Exception: If data fetching fails

        Note:
            - This method should be async to allow parallel fetching
            - Implement rate limiting within this method
            - Cache responses when appropriate
            - Handle API errors gracefully
        """
        pass

    @abstractmethod
    def process(
        self,
        company: Company,
        raw_data: Any
    ) -> List[Signal]:
        """
        Process raw data into normalized Signal objects.

        Args:
            company: Company the data is for
            raw_data: Raw data from fetch()

        Returns:
            List of normalized Signal objects

        Note:
            - Convert raw data to standard Signal format
            - Calculate normalized_value (-1 to +1)
            - Calculate score (-100 to +100)
            - Calculate confidence (0 to 1)
            - Include rich metadata
        """
        pass

    def score(self, signal: Signal) -> int:
        """
        Score a signal for trading implications.

        Args:
            signal: Signal to score

        Returns:
            Score from -100 (strong bearish) to +100 (strong bullish)

        Note:
            - Override this if you want custom scoring logic
            - Default implementation returns signal.score (set during process())
            - Negative = bearish, Positive = bullish, 0 = neutral
        """
        return signal.score

    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate that a signal is well-formed.

        Args:
            signal: Signal to validate

        Returns:
            True if valid

        Note:
            Override this to add custom validation logic
        """
        return (
            -1.0 <= signal.normalized_value <= 1.0
            and -100 <= signal.score <= 100
            and 0.0 <= signal.confidence <= 1.0
        )

    async def run(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> List[Signal]:
        """
        Full pipeline: fetch -> process -> validate.

        This is the main entry point for running a signal processor.

        Args:
            company: Company to analyze
            start: Start time
            end: End time

        Returns:
            List of validated signals

        Raises:
            Exception: If fetching or processing fails
        """
        if not self.is_applicable(company):
            return []

        # Fetch raw data
        raw_data = await self.fetch(company, start, end)

        # Process to signals
        signals = self.process(company, raw_data)

        # Validate
        valid_signals = [s for s in signals if self.validate_signal(s)]

        return valid_signals

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.metadata.signal_type}>"


class SignalProcessorRegistry:
    """Registry of all available signal processors"""

    def __init__(self):
        self._processors: Dict[str, SignalProcessor] = {}

    def register(self, processor: SignalProcessor) -> None:
        """Register a signal processor"""
        signal_type = processor.metadata.signal_type
        self._processors[signal_type] = processor

    def get(self, signal_type: str) -> Optional[SignalProcessor]:
        """Get processor by signal type"""
        return self._processors.get(signal_type)

    def list_all(self) -> List[SignalProcessor]:
        """List all registered processors"""
        return list(self._processors.values())

    def list_applicable(self, company: Company) -> List[SignalProcessor]:
        """List processors applicable to a company"""
        return [p for p in self._processors.values() if p.is_applicable(company)]

    def list_by_category(self, category: SignalCategory) -> List[SignalProcessor]:
        """List processors in a category"""
        return [p for p in self._processors.values() if p.metadata.category == category]

    def exists(self, signal_type: str) -> bool:
        """Check if processor exists"""
        return signal_type in self._processors


# Global registry instance
_processor_registry = SignalProcessorRegistry()


def get_processor_registry() -> SignalProcessorRegistry:
    """Get the global signal processor registry"""
    return _processor_registry

"""
Signal Orchestration Engine

Runs multiple signal processors in parallel and stores results to database.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import uuid

from loguru import logger
from sqlalchemy.orm import Session

from .company import Company, get_registry
from .signal import Signal
from .signal_processor import SignalProcessor, get_processor_registry
from ..models.base import SessionLocal
from ..models.signal import SignalModel


class SignalOrchestrator:
    """
    Orchestrates signal ingestion across multiple processors.

    Usage:
        orchestrator = SignalOrchestrator()
        await orchestrator.ingest_all(company, days_back=30)
    """

    def __init__(self):
        self.processor_registry = get_processor_registry()
        self.company_registry = get_registry()

    async def ingest_company(
        self,
        company: Company,
        start: datetime,
        end: datetime,
        processor_types: Optional[List[str]] = None,
    ) -> Dict[str, List[Signal]]:
        """
        Ingest all applicable signals for a company.

        Args:
            company: Company to ingest
            start: Start date
            end: End date
            processor_types: Optional list of specific processor types to run.
                           If None, runs all applicable processors.

        Returns:
            Dict mapping processor type to list of generated signals
        """

        # Get applicable processors
        if processor_types:
            processors = [
                self.processor_registry.get(pt)
                for pt in processor_types
                if self.processor_registry.get(pt)
            ]
        else:
            processors = self.processor_registry.list_applicable(company)

        if not processors:
            logger.warning(f"No applicable processors for {company.id}")
            return {}

        logger.info(f"Running {len(processors)} processors for {company.id}")

        # Run all processors in parallel
        tasks = []
        for processor in processors:
            task = self._run_processor_safe(processor, company, start, end)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Build results dict
        signals_by_type = {}
        for processor, signals in zip(processors, results):
            signal_type = processor.metadata.signal_type
            signals_by_type[signal_type] = signals
            logger.info(f"  {signal_type}: {len(signals)} signals")

        return signals_by_type

    async def _run_processor_safe(
        self,
        processor: SignalProcessor,
        company: Company,
        start: datetime,
        end: datetime
    ) -> List[Signal]:
        """
        Run a processor with error handling.

        Returns empty list on error instead of raising.
        """
        try:
            logger.info(f"Running {processor.metadata.signal_type} for {company.id}")
            signals = await processor.run(company, start, end)
            logger.info(f"✓ {processor.metadata.signal_type}: {len(signals)} signals")
            return signals
        except Exception as e:
            logger.error(f"✗ {processor.metadata.signal_type} failed: {e}")
            return []

    def store_signals(self, signals: List[Signal], db: Optional[Session] = None) -> int:
        """
        Store signals to database.

        Args:
            signals: List of signals to store
            db: Optional database session. If None, creates new session.

        Returns:
            Number of signals stored
        """

        if not signals:
            return 0

        # Create session if not provided
        close_session = db is None
        if db is None:
            db = SessionLocal()

        try:
            stored_count = 0

            for signal in signals:
                # Check if signal already exists (by hash)
                existing = db.query(SignalModel).filter(
                    SignalModel.company_id == signal.company_id,
                    SignalModel.signal_type == signal.signal_type,
                    SignalModel.metadata['raw_data_hash'].astext == signal.metadata.raw_data_hash
                ).first()

                if existing:
                    logger.debug(f"Signal already exists: {signal.signal_type} at {signal.timestamp}")
                    continue

                # Create model
                signal_model = SignalModel(
                    id=str(uuid.uuid4()),
                    company_id=signal.company_id,
                    signal_type=signal.signal_type,
                    category=signal.category,
                    timestamp=signal.timestamp,
                    raw_value=signal.raw_value,
                    normalized_value=signal.normalized_value,
                    score=signal.score,
                    confidence=signal.confidence,
                    metadata=signal.metadata.model_dump(),
                    description=signal.description,
                    tags=signal.tags,
                )

                db.add(signal_model)
                stored_count += 1

            db.commit()
            logger.info(f"Stored {stored_count} new signals to database")
            return stored_count

        except Exception as e:
            logger.error(f"Error storing signals: {e}")
            db.rollback()
            raise

        finally:
            if close_session:
                db.close()

    async def ingest_and_store(
        self,
        company: Company,
        start: datetime,
        end: datetime,
        processor_types: Optional[List[str]] = None,
    ) -> int:
        """
        Ingest signals and store to database in one operation.

        Args:
            company: Company to ingest
            start: Start date
            end: End date
            processor_types: Optional specific processors to run

        Returns:
            Total number of signals stored
        """

        # Ingest
        signals_by_type = await self.ingest_company(
            company, start, end, processor_types
        )

        # Flatten all signals
        all_signals = []
        for signals in signals_by_type.values():
            all_signals.extend(signals)

        # Store
        stored_count = self.store_signals(all_signals)

        logger.info(
            f"✓ Ingestion complete for {company.id}: "
            f"{len(all_signals)} signals generated, "
            f"{stored_count} stored"
        )

        return stored_count

    async def ingest_all_companies(
        self,
        days_back: int = 30,
        processor_types: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """
        Ingest signals for all registered companies.

        Args:
            days_back: How many days of historical data to fetch
            processor_types: Optional specific processors to run

        Returns:
            Dict mapping company ID to number of signals stored
        """

        end = datetime.utcnow()
        start = end - timedelta(days=days_back)

        companies = self.company_registry.list_all()

        logger.info(f"Ingesting {len(companies)} companies, last {days_back} days")

        results = {}
        for company in companies:
            try:
                count = await self.ingest_and_store(
                    company, start, end, processor_types
                )
                results[company.id] = count
            except Exception as e:
                logger.error(f"Failed to ingest {company.id}: {e}")
                results[company.id] = 0

        total = sum(results.values())
        logger.info(f"✓ All companies ingested: {total} total signals stored")

        return results


# Convenience function
async def ingest_company_signals(
    company_id: str,
    days_back: int = 30,
    processor_types: Optional[List[str]] = None,
) -> int:
    """
    Convenience function to ingest signals for a company.

    Args:
        company_id: Company ID (e.g., "UBER")
        days_back: Days of historical data
        processor_types: Optional specific processors

    Returns:
        Number of signals stored
    """

    company_registry = get_registry()
    company = company_registry.get(company_id)

    if not company:
        raise ValueError(f"Company {company_id} not found in registry")

    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    orchestrator = SignalOrchestrator()
    return await orchestrator.ingest_and_store(company, start, end, processor_types)

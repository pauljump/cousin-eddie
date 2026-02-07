"""Core abstractions for the platform"""

from .company import Company
from .signal import Signal, SignalMetadata
from .signal_processor import SignalProcessor, SignalCategory
from .orchestrator import SignalOrchestrator, ingest_company_signals

__all__ = [
    "Company",
    "Signal",
    "SignalMetadata",
    "SignalProcessor",
    "SignalCategory",
    "SignalOrchestrator",
    "ingest_company_signals",
]

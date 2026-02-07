"""Signal synthesis and analysis"""

from .thesis_generator import ThesisGenerator, InvestmentThesis
from .correlation_engine import CorrelationEngine, CorrelationResult

__all__ = [
    "ThesisGenerator",
    "InvestmentThesis",
    "CorrelationEngine",
    "CorrelationResult",
]

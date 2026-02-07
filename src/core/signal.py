"""Signal model - normalized representation of all data points"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SignalCategory(str, Enum):
    """Categories of signals"""
    REGULATORY = "regulatory"
    WORKFORCE = "workforce"
    WEB_DIGITAL = "web_digital"
    GEOSPATIAL = "geospatial"
    PRODUCT = "product"
    GOVERNMENT_DATA = "government_data"
    FINANCIAL = "financial"
    ALTERNATIVE = "alternative"


class SignalMetadata(BaseModel):
    """Metadata about a signal"""
    source_url: Optional[str] = Field(None, description="URL where data was fetched")
    source_name: str = Field(..., description="Name of data source")
    processing_notes: Optional[str] = Field(None, description="Notes about processing")
    raw_data_hash: Optional[str] = Field(None, description="Hash of raw data for caching")
    fetch_duration_ms: Optional[int] = Field(None, description="Time to fetch data")
    process_duration_ms: Optional[int] = Field(None, description="Time to process data")


class Signal(BaseModel):
    """
    Normalized signal representation.
    All signal processors output this standardized format.
    """

    # Identity
    company_id: str = Field(..., description="Company identifier")
    signal_type: str = Field(..., description="Type of signal (e.g., 'sec_form_4')")
    category: SignalCategory = Field(..., description="Signal category")

    # Temporal
    timestamp: datetime = Field(..., description="When the signal occurred")
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When signal was ingested"
    )

    # Signal value
    raw_value: Dict[str, Any] = Field(..., description="Original data from source")
    normalized_value: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Normalized signal value from -1 (max bearish) to +1 (max bullish)"
    )
    score: int = Field(
        ...,
        ge=-100,
        le=100,
        description="Signal strength from -100 (strong bearish) to +100 (strong bullish)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in signal quality (0 = no confidence, 1 = high confidence)"
    )

    # Metadata
    metadata: SignalMetadata = Field(..., description="Signal metadata")

    # Optional fields
    description: Optional[str] = Field(None, description="Human-readable description")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    class Config:
        json_schema_extra = {
            "example": {
                "company_id": "UBER",
                "signal_type": "sec_form_4",
                "category": "regulatory",
                "timestamp": "2026-02-07T20:15:00Z",
                "raw_value": {
                    "filer": "Dara Khosrowshahi",
                    "title": "CEO",
                    "transaction_type": "Buy",
                    "shares": 100000,
                    "price": 65.50,
                    "total_value": 6550000
                },
                "normalized_value": 0.85,
                "score": 90,
                "confidence": 0.95,
                "metadata": {
                    "source_url": "https://sec.gov/...",
                    "source_name": "SEC EDGAR",
                    "processing_notes": "Large insider buy by CEO"
                },
                "description": "CEO purchased $6.55M worth of stock",
                "tags": ["insider_buy", "ceo", "large_transaction"]
            }
        }


class SignalSummary(BaseModel):
    """Aggregated summary of signals for a company/timeframe"""

    company_id: str
    signal_type: str
    start_date: datetime
    end_date: datetime

    total_signals: int = Field(..., description="Total number of signals")
    avg_score: float = Field(..., description="Average signal score")
    avg_confidence: float = Field(..., description="Average confidence")

    bullish_signals: int = Field(default=0, description="Count of bullish signals (score > 0)")
    bearish_signals: int = Field(default=0, description="Count of bearish signals (score < 0)")
    neutral_signals: int = Field(default=0, description="Count of neutral signals (score = 0)")

    strongest_signal: Optional[Signal] = Field(None, description="Highest absolute score signal")
    latest_signal: Optional[Signal] = Field(None, description="Most recent signal")

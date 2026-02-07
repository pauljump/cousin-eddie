"""
FastAPI Backend for Cousin Eddie Dashboard

Serves signal data from database for frontend visualization.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.models.base import SessionLocal
from src.models.signal import SignalModel
from src.core.company import get_registry
from src.core.signal_processor import get_processor_registry

app = FastAPI(
    title="Cousin Eddie API",
    description="Alternative data intelligence platform for public companies",
    version="0.1.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class ProcessorInfo(BaseModel):
    signal_type: str
    category: str
    description: str
    status: str  # "active", "coming_soon"
    update_frequency: str
    data_source: str
    confidence: Optional[float] = None


class SignalResponse(BaseModel):
    company_id: str
    signal_type: str
    category: str
    timestamp: datetime
    score: int
    confidence: float
    description: str
    source_name: str


class CompanyInfo(BaseModel):
    id: str
    ticker: str
    name: str
    sector: str
    signal_count: int


class DashboardStats(BaseModel):
    total_companies: int
    total_signals: int
    active_processors: int
    planned_processors: int
    last_updated: datetime


@app.get("/")
def root():
    """API root"""
    return {
        "name": "Cousin Eddie API",
        "version": "0.1.0",
        "description": "Alternative data intelligence platform",
        "endpoints": {
            "companies": "/api/companies",
            "signals": "/api/signals/{company_id}",
            "processors": "/api/processors",
            "stats": "/api/stats"
        }
    }


@app.get("/api/companies", response_model=List[CompanyInfo])
def list_companies():
    """Get all companies with signal counts"""
    registry = get_registry()
    companies = registry.list_all()

    session = SessionLocal()
    try:
        result = []
        for company in companies:
            # Count signals
            count = session.query(SignalModel).filter(
                SignalModel.company_id == company.id
            ).count()

            result.append(CompanyInfo(
                id=company.id,
                ticker=company.ticker,
                name=company.name,
                sector=company.sector,
                signal_count=count
            ))

        return result
    finally:
        session.close()


@app.get("/api/signals/{company_id}", response_model=List[SignalResponse])
def get_signals(
    company_id: str,
    lookback_days: int = 90,
    signal_type: Optional[str] = None,
    category: Optional[str] = None
):
    """Get signals for a company"""
    session = SessionLocal()
    try:
        query = session.query(SignalModel).filter(
            SignalModel.company_id == company_id.upper()
        )

        # Filter by date
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        query = query.filter(SignalModel.timestamp >= cutoff)

        # Optional filters
        if signal_type:
            query = query.filter(SignalModel.signal_type == signal_type)
        if category:
            query = query.filter(SignalModel.category == category)

        signals = query.order_by(SignalModel.timestamp.desc()).all()

        return [
            SignalResponse(
                company_id=s.company_id,
                signal_type=s.signal_type,
                category=s.category,
                timestamp=s.timestamp,
                score=s.score,
                confidence=s.confidence,
                description=s.description,
                source_name=s.metadata.get("source_name", "Unknown")
            )
            for s in signals
        ]
    finally:
        session.close()


@app.get("/api/processors", response_model=List[ProcessorInfo])
def list_processors():
    """Get all signal processors (active + coming soon)"""

    # Active processors
    registry = get_processor_registry()
    active = []

    for processor in registry.list_all():
        meta = processor.metadata
        active.append(ProcessorInfo(
            signal_type=meta.signal_type,
            category=meta.category.value,
            description=meta.description,
            status="active",
            update_frequency=meta.update_frequency.value,
            data_source=meta.data_source,
            confidence=0.75  # Average
        ))

    # Coming soon (hardcoded for now)
    coming_soon = [
        ProcessorInfo(
            signal_type="risk_factors",
            category="regulatory",
            description="Risk factor disclosures from 10-K/10-Q",
            status="coming_soon",
            update_frequency="quarterly",
            data_source="SEC EDGAR"
        ),
        ProcessorInfo(
            signal_type="sec_8k",
            category="regulatory",
            description="Material events (8-K filings)",
            status="coming_soon",
            update_frequency="realtime",
            data_source="SEC EDGAR"
        ),
        ProcessorInfo(
            signal_type="institutional_holdings",
            category="regulatory",
            description="13F institutional ownership tracking",
            status="coming_soon",
            update_frequency="quarterly",
            data_source="SEC EDGAR"
        ),
        ProcessorInfo(
            signal_type="news_sentiment",
            category="alternative",
            description="News sentiment from major outlets",
            status="coming_soon",
            update_frequency="daily",
            data_source="NewsAPI / GDELT"
        ),
        ProcessorInfo(
            signal_type="twitter_sentiment",
            category="alternative",
            description="Twitter/X mentions and sentiment",
            status="coming_soon",
            update_frequency="realtime",
            data_source="Twitter API"
        ),
        ProcessorInfo(
            signal_type="play_store_ratings",
            category="web_digital",
            description="Android Play Store ratings",
            status="coming_soon",
            update_frequency="daily",
            data_source="Google Play API"
        ),
    ]

    return active + coming_soon


@app.get("/api/stats", response_model=DashboardStats)
def get_stats():
    """Get dashboard statistics"""
    session = SessionLocal()
    try:
        total_signals = session.query(SignalModel).count()

        # Count companies with signals
        companies = session.query(SignalModel.company_id).distinct().count()

        # Count active processors
        registry = get_processor_registry()
        active_processors = len(registry.list_all())

        # Get latest signal timestamp
        latest = session.query(SignalModel).order_by(
            SignalModel.timestamp.desc()
        ).first()

        last_updated = latest.timestamp if latest else datetime.utcnow()

        return DashboardStats(
            total_companies=companies,
            total_signals=total_signals,
            active_processors=active_processors,
            planned_processors=25,  # From inventory
            last_updated=last_updated
        )
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

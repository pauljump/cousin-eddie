"""Company model and registry"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Company(BaseModel):
    """Represents a public company that can be analyzed"""

    id: str = Field(..., description="Unique identifier (usually ticker symbol)")
    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    cik: Optional[str] = Field(None, description="SEC CIK number")
    sector: Optional[str] = Field(None, description="Industry sector")
    industry: Optional[str] = Field(None, description="Specific industry")
    country: str = Field(default="US", description="Country of incorporation")

    # Capabilities - what signal types are applicable
    has_sec_filings: bool = Field(default=True, description="Files with SEC")
    has_app: bool = Field(default=False, description="Has mobile app")
    has_physical_locations: bool = Field(default=False, description="Has retail/physical presence")
    is_tech_company: bool = Field(default=False, description="Technology company")
    is_public_company: bool = Field(default=True, description="Publicly traded")

    # Custom metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Company-specific metadata (competitors, geographies, etc.)"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "UBER",
                "ticker": "UBER",
                "name": "Uber Technologies Inc",
                "cik": "0001543151",
                "sector": "Technology",
                "industry": "Ride-hailing / Delivery",
                "has_app": True,
                "has_physical_locations": False,
                "is_tech_company": True,
                "metadata": {
                    "competitors": ["LYFT", "DASH"],
                    "cities_count": 10000,
                    "primary_markets": ["US", "LATAM", "EU"]
                }
            }
        }


class CompanyRegistry:
    """Registry of companies available for analysis"""

    def __init__(self):
        self._companies: Dict[str, Company] = {}

    def register(self, company: Company) -> None:
        """Register a company"""
        self._companies[company.id] = company

    def get(self, company_id: str) -> Optional[Company]:
        """Get company by ID"""
        return self._companies.get(company_id)

    def list_all(self) -> List[Company]:
        """List all registered companies"""
        return list(self._companies.values())

    def exists(self, company_id: str) -> bool:
        """Check if company exists"""
        return company_id in self._companies


# Global registry instance
_registry = CompanyRegistry()


def get_registry() -> CompanyRegistry:
    """Get the global company registry"""
    return _registry


# Pre-register Uber for POC
UBER = Company(
    id="UBER",
    ticker="UBER",
    name="Uber Technologies Inc",
    cik="0001543151",
    sector="Technology",
    industry="Ride-hailing / Delivery",
    has_app=True,
    has_physical_locations=False,
    is_tech_company=True,
    metadata={
        "competitors": ["LYFT", "DASH"],
        "cities_count": 10000,
        "primary_markets": ["US", "LATAM", "EU"],
        "key_metrics": ["rides", "eats_orders", "drivers", "riders"],
    }
)

_registry.register(UBER)

# Pre-register Lyft for competitive analysis
LYFT = Company(
    id="LYFT",
    ticker="LYFT",
    name="Lyft Inc",
    cik="0001759509",
    sector="Technology",
    industry="Ride-hailing",
    has_app=True,
    has_physical_locations=False,
    is_tech_company=True,
    metadata={
        "competitors": ["UBER"],
        "primary_markets": ["US", "Canada"],
        "key_metrics": ["rides", "drivers", "riders"],
    }
)

_registry.register(LYFT)

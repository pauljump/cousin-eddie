"""Company database model"""

from sqlalchemy import Column, String, Boolean, JSON, DateTime
from sqlalchemy.sql import func
from .base import Base


class CompanyModel(Base):
    """Database model for companies"""

    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    cik = Column(String, nullable=True, index=True)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    country = Column(String, default="US")

    # Capabilities
    has_sec_filings = Column(Boolean, default=True)
    has_app = Column(Boolean, default=False)
    has_physical_locations = Column(Boolean, default=False)
    is_tech_company = Column(Boolean, default=False)
    is_public_company = Column(Boolean, default=True)

    # Metadata
    metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Company {self.ticker} ({self.name})>"

"""
SEC Financial Statements Processor (10-K/10-Q)

Extracts structured financial data from SEC Company Facts API (XBRL data).
This is THE GROUND TRUTH - legally required financial disclosures.

Data Source: SEC EDGAR Company Facts API (free, quarterly/annual)
Update Frequency: Quarterly (10-Q) and Annual (10-K)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import hashlib
import json

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


class SECFinancialsProcessor(SignalProcessor):
    """
    Process SEC 10-K/10-Q financial statements from Company Facts API.

    Extracts and analyzes:
    - Income Statement (revenue, net income, margins)
    - Balance Sheet (assets, liabilities, cash, debt)
    - Cash Flow Statement (operating cash flow, free cash flow)
    - Key metrics and growth rates
    """

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov/api/xbrl"

        # Key XBRL concepts to extract (US GAAP)
        self.concepts = {
            # Income Statement
            'revenue': 'Revenues',
            'cost_of_revenue': 'CostOfRevenue',
            'gross_profit': 'GrossProfit',
            'operating_expenses': 'OperatingExpenses',
            'operating_income': 'OperatingIncomeLoss',
            'net_income': 'NetIncomeLoss',

            # Balance Sheet
            'total_assets': 'Assets',
            'total_liabilities': 'Liabilities',
            'stockholders_equity': 'StockholdersEquity',
            'cash': 'CashAndCashEquivalentsAtCarryingValue',
            'current_assets': 'AssetsCurrent',
            'current_liabilities': 'LiabilitiesCurrent',

            # Cash Flow
            'operating_cash_flow': 'NetCashProvidedByUsedInOperatingActivities',
            'investing_cash_flow': 'NetCashProvidedByUsedInInvestingActivities',
            'financing_cash_flow': 'NetCashProvidedByUsedInFinancingActivities',
            'capex': 'PaymentsToAcquirePropertyPlantAndEquipment',

            # Shares
            'shares_outstanding': 'CommonStockSharesOutstanding',
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_financials",
            category=SignalCategory.REGULATORY,
            description="Financial statements from 10-K/10-Q - THE GROUND TRUTH",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC EDGAR Company Facts API",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["financials", "sec", "10-k", "10-q", "xbrl", "ground_truth"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all US public companies with SEC filings"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch company facts from SEC EDGAR API.

        Returns structured financial data for all historical periods.
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return {}

        # Format CIK (must be 10 digits, zero-padded)
        cik = company.cik.zfill(10)

        url = f"{self.base_url}/companyfacts/CIK{cik}.json"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching SEC Company Facts for {company.ticker} (CIK: {cik})")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()

                logger.info(f"Retrieved company facts for {data.get('entityName', company.ticker)}")

                return {
                    'company_id': company.id,
                    'cik': data.get('cik'),
                    'entity_name': data.get('entityName'),
                    'facts': data.get('facts', {}),
                    'fetched_at': datetime.utcnow(),
                }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Company Facts for {company.ticker}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching Company Facts for {company.ticker}: {e}")
            return {}

    def process(
        self,
        company: Company,
        raw_data: Dict[str, Any]
    ) -> List[Signal]:
        """
        Process company facts into financial signals.

        Generates signals for each quarter showing:
        - Revenue growth (QoQ, YoY)
        - Profit margins
        - Balance sheet health
        - Cash flow generation
        """
        if not raw_data or 'facts' not in raw_data:
            return []

        facts = raw_data.get('facts', {})
        us_gaap = facts.get('us-gaap', {})

        # Extract quarterly financial data
        quarterly_data = self._extract_quarterly_financials(us_gaap)

        if not quarterly_data:
            logger.warning(f"No quarterly financial data found for {company.id}")
            return []

        # Generate signals from financial data
        signals = []

        # Sort by period end date
        periods = sorted(quarterly_data.keys())

        for i, period_end in enumerate(periods):
            data = quarterly_data[period_end]

            # Calculate growth rates if we have prior period
            prior_period = periods[i-1] if i > 0 else None
            prior_data = quarterly_data.get(prior_period) if prior_period else None

            # Generate signals for this period
            period_signals = self._generate_period_signals(
                company=company,
                period_end=period_end,
                data=data,
                prior_data=prior_data
            )

            signals.extend(period_signals)

        logger.info(f"Generated {len(signals)} financial signals for {company.id}")
        return signals

    def _extract_quarterly_financials(self, us_gaap: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """
        Extract quarterly financial data from US GAAP facts.

        Returns dict mapping period_end → financial metrics
        """
        quarterly_data = {}

        for metric_name, concept_name in self.concepts.items():
            if concept_name not in us_gaap:
                continue

            concept_data = us_gaap[concept_name]
            units = concept_data.get('units', {})

            # Get USD data (or shares for shares outstanding)
            unit_key = 'USD' if 'USD' in units else 'shares' if 'shares' in units else None
            if not unit_key:
                continue

            values = units[unit_key]

            # Filter for 10-Q and 10-K filings only
            for entry in values:
                if entry.get('form') not in ['10-Q', '10-K']:
                    continue

                period_end = entry.get('end')
                fiscal_period = entry.get('fp', 'FY')
                value = entry.get('val')

                if not period_end or value is None:
                    continue

                # Initialize period if not exists
                if period_end not in quarterly_data:
                    quarterly_data[period_end] = {
                        'form': entry.get('form'),
                        'fiscal_year': entry.get('fy'),
                        'fiscal_period': fiscal_period,
                        'filed_date': entry.get('filed'),
                    }

                # Store the metric
                quarterly_data[period_end][metric_name] = value

        return quarterly_data

    def _generate_period_signals(
        self,
        company: Company,
        period_end: str,
        data: Dict[str, float],
        prior_data: Optional[Dict[str, float]]
    ) -> List[Signal]:
        """Generate signals for a single financial period"""
        signals = []
        timestamp = datetime.fromisoformat(period_end)

        # Revenue Growth Signal
        revenue = data.get('revenue')
        if revenue and prior_data and 'revenue' in prior_data:
            prior_revenue = prior_data['revenue']
            revenue_growth = (revenue - prior_revenue) / prior_revenue

            # Score revenue growth
            if revenue_growth > 0.20:  # >20% growth
                score = 90
                description = f"Exceptional revenue growth: +{revenue_growth*100:.1f}% QoQ"
            elif revenue_growth > 0.10:  # >10% growth
                score = 70
                description = f"Strong revenue growth: +{revenue_growth*100:.1f}% QoQ"
            elif revenue_growth > 0.05:  # >5% growth
                score = 50
                description = f"Solid revenue growth: +{revenue_growth*100:.1f}% QoQ"
            elif revenue_growth > 0:
                score = 20
                description = f"Modest revenue growth: +{revenue_growth*100:.1f}% QoQ"
            elif revenue_growth > -0.05:
                score = -20
                description = f"Revenue decline: {revenue_growth*100:.1f}% QoQ"
            else:
                score = -60
                description = f"Significant revenue decline: {revenue_growth*100:.1f}% QoQ"

            signals.append(Signal(
                company_id=company.id,
                signal_type="revenue_growth_qoq",
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value={
                    'current_revenue': revenue,
                    'prior_revenue': prior_revenue,
                    'growth_rate': revenue_growth,
                    'period_end': period_end,
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.95,  # Financial data is high confidence
                metadata=SignalMetadata(
                    source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=10-Q",
                    source_name="SEC EDGAR 10-Q/10-K",
                    processing_notes=f"Revenue growth calculated from {data['form']}",
                    raw_data_hash=hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(),
                ),
                description=description,
                tags=["revenue", "growth", "financials", data['form'].lower()],
            ))

        # Profit Margin Signal
        if revenue and 'net_income' in data:
            net_income = data['net_income']
            net_margin = net_income / revenue if revenue > 0 else 0

            # Score profitability
            if net_margin > 0.20:  # >20% margins
                score = 85
                description = f"Exceptional profitability: {net_margin*100:.1f}% net margin"
            elif net_margin > 0.10:
                score = 60
                description = f"Strong profitability: {net_margin*100:.1f}% net margin"
            elif net_margin > 0.05:
                score = 40
                description = f"Profitable: {net_margin*100:.1f}% net margin"
            elif net_margin > 0:
                score = 10
                description = f"Marginally profitable: {net_margin*100:.1f}% net margin"
            else:
                score = -50
                description = f"Unprofitable: {net_margin*100:.1f}% net margin"

            signals.append(Signal(
                company_id=company.id,
                signal_type="profit_margin",
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value={
                    'revenue': revenue,
                    'net_income': net_income,
                    'net_margin': net_margin,
                    'period_end': period_end,
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.95,
                metadata=SignalMetadata(
                    source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=10-Q",
                    source_name="SEC EDGAR 10-Q/10-K",
                    processing_notes=f"Profit margin from {data['form']}",
                    raw_data_hash=hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(),
                ),
                description=description,
                tags=["profitability", "margins", "financials", data['form'].lower()],
            ))

        # Cash Flow Signal
        if 'operating_cash_flow' in data and revenue:
            ocf = data['operating_cash_flow']
            ocf_margin = ocf / revenue if revenue > 0 else 0

            # Score cash generation
            if ocf_margin > 0.25:
                score = 80
                description = f"Excellent cash generation: {ocf_margin*100:.1f}% OCF margin"
            elif ocf_margin > 0.15:
                score = 60
                description = f"Strong cash generation: {ocf_margin*100:.1f}% OCF margin"
            elif ocf_margin > 0.05:
                score = 30
                description = f"Positive cash flow: {ocf_margin*100:.1f}% OCF margin"
            elif ocf_margin > 0:
                score = 5
                description = f"Weak cash generation: {ocf_margin*100:.1f}% OCF margin"
            else:
                score = -40
                description = f"Cash flow negative: {ocf_margin*100:.1f}% OCF margin"

            signals.append(Signal(
                company_id=company.id,
                signal_type="operating_cash_flow",
                category=self.metadata.category,
                timestamp=timestamp,
                raw_value={
                    'operating_cash_flow': ocf,
                    'revenue': revenue,
                    'ocf_margin': ocf_margin,
                    'period_end': period_end,
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=0.95,
                metadata=SignalMetadata(
                    source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=10-Q",
                    source_name="SEC EDGAR 10-Q/10-K",
                    processing_notes=f"Cash flow from {data['form']}",
                    raw_data_hash=hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(),
                ),
                description=description,
                tags=["cash_flow", "liquidity", "financials", data['form'].lower()],
            ))

        return signals

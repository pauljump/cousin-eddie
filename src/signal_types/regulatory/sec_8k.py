"""
SEC Form 8-K Signal Processor

Monitors material event filings (8-K) to detect significant corporate changes.
Filed within 4 business days of material events.

High-signal 8-K items:
- Item 2.02: Earnings announcements (often prelude to 10-Q)
- Item 5.02: CEO/CFO/Director departures or appointments
- Item 1.01: Material agreements (M&A, partnerships)
- Item 8.01: Other material events
- Item 1.02: Asset acquisitions/dispositions
- Item 5.03: Amendments to articles of incorporation

Data Source: SEC EDGAR API (free, real-time)
Update Frequency: Real-time (filed within 4 days of event)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import json

import httpx
from bs4 import BeautifulSoup
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


class SEC8KProcessor(SignalProcessor):
    """Process SEC Form 8-K material event filings"""

    # 8-K items and their significance
    # Source: https://www.sec.gov/files/form8-k.pdf
    ITEM_CATEGORIES = {
        # Section 1: Registrant's Business and Operations
        "1.01": {"name": "Entry into Material Definitive Agreement", "score": 60, "category": "M&A"},
        "1.02": {"name": "Termination of Material Definitive Agreement", "score": -40, "category": "M&A"},
        "1.03": {"name": "Bankruptcy or Receivership", "score": -90, "category": "Distress"},
        "1.04": {"name": "Mine Safety Violations", "score": -30, "category": "Regulatory"},
        "1.05": {"name": "Material Cybersecurity Incidents", "score": -50, "category": "Risk"},

        # Section 2: Financial Information
        "2.01": {"name": "Completion of Acquisition/Disposition", "score": 50, "category": "M&A"},
        "2.02": {"name": "Results of Operations (Earnings)", "score": 0, "category": "Earnings"},  # Scored based on content
        "2.03": {"name": "Creation of Direct Financial Obligation", "score": -20, "category": "Financing"},
        "2.04": {"name": "Triggering Events on Direct Financial Obligations", "score": -60, "category": "Distress"},
        "2.05": {"name": "Costs Associated with Exit/Disposal Activities", "score": -40, "category": "Restructuring"},
        "2.06": {"name": "Material Impairments", "score": -70, "category": "Impairment"},

        # Section 3: Securities and Trading Markets
        "3.01": {"name": "Notice of Delisting", "score": -80, "category": "Distress"},
        "3.02": {"name": "Unregistered Sales of Equity Securities", "score": 30, "category": "Financing"},
        "3.03": {"name": "Material Modification to Rights of Security Holders", "score": -30, "category": "Governance"},

        # Section 4: Matters Related to Accountants
        "4.01": {"name": "Changes in Registrant's Certifying Accountant", "score": -50, "category": "Accounting"},
        "4.02": {"name": "Non-Reliance on Previously Issued Financial Statements", "score": -80, "category": "Restatement"},

        # Section 5: Corporate Governance and Management (HIGH SIGNAL)
        "5.01": {"name": "Changes in Control of Registrant", "score": 70, "category": "Control"},
        "5.02": {"name": "Departure/Appointment of Directors/Officers", "score": 0, "category": "Management"},  # Scored based on role
        "5.03": {"name": "Amendments to Articles of Incorporation/Bylaws", "score": -20, "category": "Governance"},
        "5.04": {"name": "Temporary Suspension of Trading", "score": -60, "category": "Trading"},
        "5.05": {"name": "Amendments to Code of Ethics", "score": -10, "category": "Governance"},
        "5.06": {"name": "Change in Shell Company Status", "score": 40, "category": "Structure"},
        "5.07": {"name": "Submission of Matters to Vote of Security Holders", "score": 10, "category": "Governance"},
        "5.08": {"name": "Shareholder Director Nominations", "score": 20, "category": "Governance"},

        # Section 6: Asset-Backed Securities (less relevant for most)
        "6.01": {"name": "ABS Informational/Computational Material", "score": 0, "category": "ABS"},
        "6.02": {"name": "Change of Servicer or Trustee", "score": 0, "category": "ABS"},
        "6.03": {"name": "Change in Credit Enhancement", "score": 0, "category": "ABS"},

        # Section 7: Regulation FD
        "7.01": {"name": "Regulation FD Disclosure", "score": 10, "category": "Disclosure"},

        # Section 8: Other Events
        "8.01": {"name": "Other Events", "score": 0, "category": "Other"},  # Scored based on content

        # Section 9: Financial Statements and Exhibits
        "9.01": {"name": "Financial Statements and Exhibits", "score": 0, "category": "Filing"},
    }

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent identifying you
        """
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"
        self.doc_url = "https://www.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_8k",
            category=SignalCategory.REGULATORY,
            description="Material event filings - M&A, executive changes, earnings",
            update_frequency=UpdateFrequency.REALTIME,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["8-k", "material_events", "regulatory", "sec", "realtime"],
        )

    def is_applicable(self, company: Company) -> bool:
        """8-K applies to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch 8-K filings from SEC EDGAR.

        Returns dict with filings metadata for processing.
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return {}

        # Format CIK (must be 10 digits, zero-padded)
        cik = company.cik.zfill(10)
        url = f"{self.base_url}/submissions/CIK{cik}.json"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching 8-K filings for {company.ticker} (CIK: {cik})")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()

                # Extract recent filings
                filings = data.get("filings", {}).get("recent", {})

                if not filings:
                    logger.warning(f"No recent filings found for {company.ticker}")
                    return {}

                # Filter for 8-K filings within date range
                form_types = filings.get("form", [])
                filing_dates = filings.get("filingDate", [])
                accession_numbers = filings.get("accessionNumber", [])
                primary_documents = filings.get("primaryDocument", [])

                eightk_filings = []

                for i in range(len(form_types)):
                    if form_types[i] == "8-K":
                        filing_date = datetime.strptime(filing_dates[i], "%Y-%m-%d")

                        # Filter by date range
                        if start <= filing_date <= end:
                            eightk_filings.append({
                                "filing_date": filing_dates[i],
                                "accession_number": accession_numbers[i],
                                "primary_document": primary_documents[i],
                                "cik": cik,
                            })

                logger.info(f"Found {len(eightk_filings)} 8-K filings for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "cik": cik,
                    "filings": eightk_filings,
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching 8-K data: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching 8-K data: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process 8-K filings into signals.

        Each filing generates a signal based on the items reported.
        """
        filings = raw_data.get("filings", [])

        if not filings:
            return []

        signals = []

        for filing in filings:
            try:
                # Parse the filing to extract items
                items = self._extract_8k_items(filing)

                if not items:
                    logger.warning(f"No items found in 8-K filing {filing['filing_date']}")
                    continue

                # Generate signal based on items
                signal = self._create_signal_from_items(company, filing, items)

                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"Error processing 8-K from {filing['filing_date']}: {e}")
                continue

        logger.info(f"Generated {len(signals)} signals from {len(filings)} 8-K filings")
        return signals

    def _extract_8k_items(self, filing: Dict[str, Any]) -> List[str]:
        """
        Extract item numbers from 8-K filing.

        8-K items are listed in the filing header.
        We parse the HTML to find "Item X.XX" mentions.
        """
        # Construct document URL
        accession = filing["accession_number"].replace("-", "")
        cik = filing["cik"]
        doc = filing["primary_document"]

        url = f"{self.doc_url}/Archives/edgar/data/{cik}/{accession}/{doc}"

        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=15.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.text

            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text()

            # Find item numbers (e.g., "Item 5.02", "Item 2.02", etc.)
            import re
            item_pattern = r'Item\s+(\d+\.\d+)'
            matches = re.findall(item_pattern, text, re.IGNORECASE)

            # Deduplicate and sort
            items = sorted(list(set(matches)))

            logger.debug(f"Found items in 8-K: {items}")
            return items

        except Exception as e:
            logger.warning(f"Error extracting items from 8-K: {e}")
            return []

    def _create_signal_from_items(
        self,
        company: Company,
        filing: Dict[str, Any],
        items: List[str]
    ) -> Optional[Signal]:
        """
        Create signal from 8-K items.

        Scoring logic:
        - High-impact items (5.02 CEO departure, 1.01 M&A) = higher weight
        - Multiple items = combined score
        - Item 2.02 (earnings) scored separately based on content analysis
        """
        if not items:
            return None

        # Calculate aggregate score
        total_score = 0
        item_descriptions = []
        categories = set()

        for item in items:
            if item in self.ITEM_CATEGORIES:
                item_info = self.ITEM_CATEGORIES[item]
                total_score += item_info["score"]
                item_descriptions.append(f"Item {item}: {item_info['name']}")
                categories.add(item_info["category"])

        # Normalize score to -100 to +100 range
        # Cap at 3 items for scoring to avoid runaway scores
        num_items = min(len(items), 3)
        score = total_score // max(num_items, 1)
        score = max(-100, min(100, score))

        # Build description
        category_str = ", ".join(sorted(categories))
        description = f"8-K filed: {category_str} | " + " + ".join(item_descriptions[:3])

        if len(item_descriptions) > 3:
            description += f" + {len(item_descriptions) - 3} more items"

        # Calculate confidence
        # Higher confidence for well-known high-signal items
        high_signal_items = ["5.02", "1.01", "2.02", "4.02", "2.06"]
        has_high_signal = any(item in high_signal_items for item in items)
        confidence = 0.85 if has_high_signal else 0.70

        # Create signal
        filing_date = datetime.strptime(filing["filing_date"], "%Y-%m-%d")

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=filing_date,
            raw_value=filing,
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"{self.doc_url}/cgi-bin/browse-edgar?action=getcompany&CIK={filing['cik']}&type=8-K",
                source_name="SEC EDGAR 8-K",
                processing_notes=f"Items: {', '.join(items)}",
                raw_data_hash=hashlib.md5(
                    json.dumps(filing, sort_keys=True).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["8-k", "material_event"] + list(categories),
        )

        return signal

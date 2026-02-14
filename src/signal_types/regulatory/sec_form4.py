"""
SEC Form 4 Signal Processor

Monitors insider trading filings to detect buying/selling by company executives.
Large insider buys are often bullish signals, especially from CEO/CFO.

Data Source: SEC EDGAR API (free, real-time)
Update Frequency: Real-time (as filings occur)
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET

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
from .edgar_client import EdgarClient


class SECForm4Processor(SignalProcessor):
    """Process SEC Form 4 insider trading filings"""

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """
        Initialize processor.

        Args:
            user_agent: SEC requires a user agent identifying you
                       Format: "CompanyName email@example.com"
        """
        self.user_agent = user_agent
        self.base_url = "https://data.sec.gov"
        self._edgar_client = EdgarClient(user_agent=user_agent)

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sec_form_4",
            category=SignalCategory.REGULATORY,
            description="Insider trading filings - detect executive buying/selling",
            update_frequency=UpdateFrequency.REALTIME,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["insider_trading", "regulatory", "executives", "sec"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Form 4 applies to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch Form 4 filings from SEC EDGAR and parse XML for transaction details.

        Uses EdgarClient to fetch ALL filings (recent + archived batches).
        """
        if not company.cik:
            logger.warning(f"No CIK for company {company.id}")
            return []

        cik = company.cik.zfill(10)

        # Fetch all Form 4 filings (recent + archived)
        all_filings = await self._edgar_client.get_all_filings(
            cik=company.cik, form_type="4", start_date=start, end_date=end
        )

        if not all_filings:
            return []

        # Fetch and parse XML for each filing
        form4_filings = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for filing in all_filings:
                    accession_number = filing["accessionNumber"]
                    primary_document = filing["primaryDocument"]

                    filing_info = {
                        "accessionNumber": accession_number,
                        "filingDate": filing["filingDate"],
                        "reportDate": filing.get("reportDate"),
                        "acceptanceDateTime": filing.get("acceptanceDateTime"),
                        "primaryDocument": primary_document,
                        "primaryDocDescription": filing.get("primaryDocDescription"),
                    }

                    # Fetch and parse the XML document
                    xml_data = await self._fetch_form4_xml(
                        client, cik, accession_number, primary_document
                    )
                    if xml_data:
                        filing_info["xml_data"] = xml_data

                    form4_filings.append(filing_info)

                    # Rate limit: SEC requests max 10 requests/second
                    await asyncio.sleep(0.15)

        except Exception as e:
            logger.error(f"Error fetching Form 4 XMLs for {company.ticker}: {e}")

        logger.info(f"Found {len(form4_filings)} Form 4 filings for {company.ticker}")
        return form4_filings

    async def _fetch_form4_xml(
        self,
        client: httpx.AsyncClient,
        cik: str,
        accession_number: str,
        primary_document: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse the Form 4 XML document.

        URL format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_doc}
        Note: primarydocument.xml is the raw XML (not xslF345X05/primarydocument.xml which is HTML)
        """
        try:
            # Remove dashes from accession number for URL
            accession_no_dashes = accession_number.replace("-", "")

            # Remove XSLT path if present (xslF345X05/)
            # The raw XML is just "primarydocument.xml" at the root of the filing directory
            if "/" in primary_document:
                primary_document = primary_document.split("/")[-1]

            # Construct XML URL
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no_dashes}/{primary_document}"

            logger.debug(f"Fetching Form 4 XML: {xml_url}")

            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/xml",
            }

            response = await client.get(xml_url, headers=headers)
            response.raise_for_status()

            # Parse XML
            xml_text = response.text
            parsed_data = self._parse_form4_xml(xml_text)

            return parsed_data

        except Exception as e:
            logger.error(f"Error fetching/parsing Form 4 XML {accession_number}: {e}")
            return None

    def _parse_form4_xml(self, xml_text: str) -> Dict[str, Any]:
        """
        Parse Form 4 XML to extract transaction details.

        Form 4 XML structure:
        - <ownershipDocument>
          - <reportingOwner>
            - <reportingOwnerId><rptOwnerName>
            - <reportingOwnerRelationship><isDirector>, <isOfficer>, <officerTitle>
          - <nonDerivativeTable>
            - <nonDerivativeTransaction>
              - <transactionCode> (P=purchase, S=sale, A=award, etc.)
              - <transactionShares><value>
              - <transactionPricePerShare><value>
        """
        try:
            root = ET.fromstring(xml_text)

            # XML namespace handling
            ns = {'ns': 'http://www.sec.gov/edgar/document/ownership/xml/0003'}

            # Extract reporting owner info
            owner_name = "Unknown"
            owner_title = "Unknown"
            is_director = False
            is_officer = False

            reporting_owner = root.find('.//ns:reportingOwner', ns)
            if reporting_owner is None:
                # Try without namespace
                reporting_owner = root.find('.//reportingOwner')

            if reporting_owner is not None:
                owner_id = reporting_owner.find('.//ns:rptOwnerName', ns)
                if owner_id is None:
                    owner_id = reporting_owner.find('.//rptOwnerName')
                if owner_id is not None and owner_id.text:
                    owner_name = owner_id.text

                relationship = reporting_owner.find('.//ns:reportingOwnerRelationship', ns)
                if relationship is None:
                    relationship = reporting_owner.find('.//reportingOwnerRelationship')

                if relationship is not None:
                    director_elem = relationship.find('.//ns:isDirector', ns)
                    if director_elem is None:
                        director_elem = relationship.find('.//isDirector')
                    if director_elem is not None and director_elem.text == '1':
                        is_director = True

                    officer_elem = relationship.find('.//ns:isOfficer', ns)
                    if officer_elem is None:
                        officer_elem = relationship.find('.//isOfficer')
                    if officer_elem is not None and officer_elem.text == '1':
                        is_officer = True

                    title_elem = relationship.find('.//ns:officerTitle', ns)
                    if title_elem is None:
                        title_elem = relationship.find('.//officerTitle')
                    if title_elem is not None and title_elem.text:
                        owner_title = title_elem.text
                    elif is_director:
                        owner_title = "Director"

            # If title is "See Remarks", extract from remarks section
            if owner_title == "See Remarks":
                remarks_elem = root.find('.//ns:remarks', ns)
                if remarks_elem is None:
                    remarks_elem = root.find('.//remarks')
                if remarks_elem is not None and remarks_elem.text:
                    owner_title = remarks_elem.text

            # Extract transactions
            transactions = []

            # Non-derivative transactions (actual stock buys/sells)
            non_deriv_table = root.find('.//ns:nonDerivativeTable', ns)
            if non_deriv_table is None:
                non_deriv_table = root.find('.//nonDerivativeTable')

            if non_deriv_table is not None:
                trans_elements = non_deriv_table.findall('.//ns:nonDerivativeTransaction', ns)
                if not trans_elements:
                    trans_elements = non_deriv_table.findall('.//nonDerivativeTransaction')

                for trans in trans_elements:
                    transaction_code_elem = trans.find('.//ns:transactionCode', ns)
                    if transaction_code_elem is None:
                        transaction_code_elem = trans.find('.//transactionCode')
                    transaction_code = transaction_code_elem.text if transaction_code_elem is not None else None

                    shares_elem = trans.find('.//ns:transactionShares/ns:value', ns)
                    if shares_elem is None:
                        shares_elem = trans.find('.//transactionShares/value')
                    shares = float(shares_elem.text) if shares_elem is not None and shares_elem.text else 0.0

                    price_elem = trans.find('.//ns:transactionPricePerShare/ns:value', ns)
                    if price_elem is None:
                        price_elem = trans.find('.//transactionPricePerShare/value')
                    price = float(price_elem.text) if price_elem is not None and price_elem.text else 0.0

                    # Transaction codes:
                    # P=Purchase, S=Sale (open market)
                    # F=Payment of tax liability (shares withheld for taxes)
                    # A=Award/Grant, M=Exercise
                    transaction_type = "unknown"
                    if transaction_code == "P":
                        transaction_type = "buy"
                    elif transaction_code == "S":
                        transaction_type = "sell"
                    elif transaction_code == "F":
                        transaction_type = "tax_withhold"  # Shares sold for tax, not insider choice
                    elif transaction_code in ["A", "M"]:
                        transaction_type = "award"  # Treat awards/exercises separately

                    total_value = shares * price

                    transactions.append({
                        "transaction_code": transaction_code,
                        "transaction_type": transaction_type,
                        "shares": shares,
                        "price": price,
                        "total_value": total_value,
                    })

            return {
                "owner_name": owner_name,
                "owner_title": owner_title,
                "is_director": is_director,
                "is_officer": is_officer,
                "transactions": transactions,
            }

        except Exception as e:
            logger.error(f"Error parsing Form 4 XML: {e}")
            return {
                "owner_name": "Unknown",
                "owner_title": "Unknown",
                "is_director": False,
                "is_officer": False,
                "transactions": [],
            }

    def process(
        self,
        company: Company,
        raw_data: List[Dict[str, Any]]
    ) -> List[Signal]:
        """
        Process Form 4 filings into signals.

        Now with full XML parsing to extract transaction details and score them.
        """
        signals = []

        for filing in raw_data:
            # Parse filing date
            filing_date_str = filing.get("filingDate")
            if not filing_date_str:
                continue

            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

            # Get acceptance datetime for timing analysis
            acceptance_datetime = filing.get("acceptanceDateTime")
            filing_time = filing_date
            if acceptance_datetime:
                try:
                    filing_time = datetime.fromisoformat(acceptance_datetime.replace("Z", "+00:00"))
                except:
                    pass

            # Extract parsed XML data
            xml_data = filing.get("xml_data", {})
            insider_name = xml_data.get("owner_name", "Unknown")
            insider_title = xml_data.get("owner_title", "Unknown")
            transactions = xml_data.get("transactions", [])

            # Process each transaction in the filing
            for transaction in transactions:
                transaction_type = transaction.get("transaction_type", "unknown")
                shares = transaction.get("shares", 0)
                price = transaction.get("price", 0)
                total_value = transaction.get("total_value", 0)

                # Skip award/grant transactions and tax withholdings (not meaningful insider signals)
                if transaction_type in ["award", "tax_withhold"]:
                    continue

                # Score the transaction
                score, confidence = self._score_form4_transaction(
                    transaction_type=transaction_type,
                    insider_title=insider_title,
                    total_value=total_value,
                    filing_time=filing_time,
                )

                raw_value = {
                    "accession_number": filing.get("accessionNumber"),
                    "filing_date": filing_date_str,
                    "acceptance_datetime": acceptance_datetime,
                    "primary_document": filing.get("primaryDocument"),
                    "transaction_type": transaction_type,
                    "insider_name": insider_name,
                    "insider_title": insider_title,
                    "shares": shares,
                    "price": price,
                    "total_value": total_value,
                }

                # Calculate hash for deduplication
                raw_hash = hashlib.md5(
                    json.dumps(raw_value, sort_keys=True, default=str).encode()
                ).hexdigest()

                normalized_value = score / 100.0

                # Create description
                action = "bought" if transaction_type == "buy" else "sold"
                description = f"{insider_title} {action} ${total_value:,.0f} ({shares:,.0f} shares @ ${price:.2f})"

                # Create signal
                signal = Signal(
                    company_id=company.id,
                    signal_type=self.metadata.signal_type,
                    category=self.metadata.category,
                    timestamp=filing_date,
                    raw_value=raw_value,
                    normalized_value=normalized_value,
                    score=score,
                    confidence=confidence,
                    metadata=SignalMetadata(
                        source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=4",
                        source_name="SEC EDGAR",
                        processing_notes=f"Form 4 XML parsed - {insider_name} ({insider_title})",
                        raw_data_hash=raw_hash,
                    ),
                    description=description,
                    tags=["form_4", "insider_trading", "sec", transaction_type],
                )

                signals.append(signal)

            # If no valid transactions found, create a neutral signal
            if not transactions or all(t.get("transaction_type") in ["award", "tax_withhold"] for t in transactions):
                raw_value = {
                    "accession_number": filing.get("accessionNumber"),
                    "filing_date": filing_date_str,
                    "acceptance_datetime": acceptance_datetime,
                    "primary_document": filing.get("primaryDocument"),
                    "transaction_type": "none",
                    "insider_name": insider_name,
                    "insider_title": insider_title,
                    "shares": 0,
                    "price": 0.0,
                    "total_value": 0.0,
                }

                raw_hash = hashlib.md5(
                    json.dumps(raw_value, sort_keys=True, default=str).encode()
                ).hexdigest()

                signal = Signal(
                    company_id=company.id,
                    signal_type=self.metadata.signal_type,
                    category=self.metadata.category,
                    timestamp=filing_date,
                    raw_value=raw_value,
                    normalized_value=0.0,
                    score=0,
                    confidence=0.3,
                    metadata=SignalMetadata(
                        source_url=f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=4",
                        source_name="SEC EDGAR",
                        processing_notes=f"Form 4 filed - no market transactions (awards/grants only)",
                        raw_data_hash=raw_hash,
                    ),
                    description=f"Form 4 filing by {insider_title} - no market buys/sells",
                    tags=["form_4", "insider_trading", "sec", "no_transaction"],
                )

                signals.append(signal)

        return signals

    def _score_form4_transaction(
        self,
        transaction_type: str,
        insider_title: str,
        total_value: float,
        filing_time: datetime,
    ) -> tuple[int, float]:
        """
        Score a Form 4 transaction.

        Returns:
            (score, confidence) tuple

        Scoring logic based on research showing:
        - CEO/CFO large buys outperform market by 6-10%
        - Friday night filings often hide bad news
        - Transactions > $1M are more significant
        """
        score = 0
        confidence = 0.8

        # Base score from transaction type
        if transaction_type == "buy":
            score = 50  # Base bullish
        elif transaction_type == "sell":
            score = -20  # Mildly bearish (insiders sell for many reasons)
        else:
            score = 0
            confidence = 0.3
            return score, confidence

        # Adjust for insider role
        role_multipliers = {
            "CEO": 1.8,
            "CFO": 1.6,
            "President": 1.5,
            "COO": 1.4,
            "Director": 1.0,
            "Officer": 0.8,
        }

        for role, multiplier in role_multipliers.items():
            if role.lower() in insider_title.lower():
                score = int(score * multiplier)
                break

        # Adjust for transaction size
        if transaction_type == "buy":
            if total_value > 5_000_000:
                score = min(score + 30, 100)
                confidence = 0.95
            elif total_value > 1_000_000:
                score = min(score + 20, 100)
                confidence = 0.9
            elif total_value > 500_000:
                score = min(score + 10, 100)
            elif total_value < 50_000:
                score = max(score - 10, 0)
                confidence = 0.6

        # Friday night filing red flag
        if filing_time.weekday() == 4 and filing_time.hour >= 17:  # Friday after 5pm
            score = int(score * 0.7)  # Reduce bullishness (might be burying news)
            confidence *= 0.9

        # Cap scores
        score = max(-100, min(100, score))

        return score, confidence

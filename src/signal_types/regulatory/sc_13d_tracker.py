"""
SC 13D/13G Large Position Tracker

Tracks when investors acquire 5%+ stakes in companies.

Why 13D/13G matters:
- SC 13D = Active investor (may seek control) = MAJOR CATALYST
- SC 13G = Passive investor (conviction play) = BULLISH
- Amendments show position increases/decreases
- Activist investors filing 13D often leads to stock appreciation
- Multiple 13Ds = takeover interest

Key Differences:
- 13D: Filed within 10 days of crossing 5%, plans to influence company
- 13G: Filed within 45 days, passive investment only

Famous Examples:
- Icahn files 13D on Apple → stock rallies
- Pershing Square 13D on Chipotle → activist campaign
- Buffett 13G on Coca-Cola → long-term conviction

Signals:
- New 13D filing = activist interest = VERY BULLISH
- 13D amendment (increasing stake) = conviction = BULLISH
- 13D amendment (decreasing) = exiting = BEARISH
- 13G = passive conviction = MODERATELY BULLISH
- 13G to 13D conversion = going active = VERY BULLISH

Data Source: SEC EDGAR
Update Frequency: Daily (filings happen sporadically)
"""

from typing import List, Any, Dict
from datetime import datetime, timedelta
import hashlib
import json
import re

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


class SC13DTrackerProcessor(SignalProcessor):
    """Tracks SC 13D/13G large position filings"""

    # Well-known activist investors (13D filings from these = very bullish)
    ACTIVIST_INVESTORS = [
        "icahn",
        "pershing square",
        "elliott",
        "jana partners",
        "starboard value",
        "third point",
        "trian",
        "valueact",
        "sachem head",
        "citadel",
    ]

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        """Initialize processor"""
        self.user_agent = user_agent
        self.base_url = "https://www.sec.gov"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="sc_13d_tracker",
            category=SignalCategory.REGULATORY,
            description="SC 13D/13G tracker - activist and large investor positions",
            update_frequency=UpdateFrequency.DAILY,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["13d", "13g", "activists", "large_positions", "ownership"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to all US public companies"""
        return company.has_sec_filings and company.cik is not None

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch SC 13D/13G filings for company.

        SEC EDGAR search for:
        - SC 13D (activist)
        - SC 13D/A (amendments)
        - SC 13G (passive)
        - SC 13G/A (amendments)
        """
        if not company.cik:
            return {}

        cik = company.cik.zfill(10)

        # SEC submissions endpoint
        url = f"{self.base_url}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": cik,
            "type": "",  # All types
            "dateb": "",
            "owner": "include",  # Include ownership forms
            "count": "100",
        }

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching 13D/13G filings for {company.ticker}")
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()

                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # Find filing table
                filings = []
                table = soup.find("table", class_="tableFile2")

                if not table:
                    logger.warning(f"No filings table found for {company.ticker}")
                    return {"company_id": company.id, "filings": []}

                rows = table.find_all("tr")[1:]  # Skip header

                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 4:
                        continue

                    form_type = cols[0].text.strip()
                    filing_date = cols[3].text.strip()

                    # Filter for 13D/13G only
                    if not ("13D" in form_type or "13G" in form_type):
                        continue

                    # Parse date
                    try:
                        filing_datetime = datetime.strptime(filing_date, "%Y-%m-%d")
                    except:
                        continue

                    # Filter by date range
                    if not (start <= filing_datetime <= end):
                        continue

                    # Get filer (owner)
                    filer_link = cols[2].find("a")
                    filer = filer_link.text.strip() if filer_link else "Unknown"

                    # Get document link
                    doc_link = cols[1].find("a")
                    doc_url = ""
                    if doc_link and doc_link.get("href"):
                        doc_url = f"{self.base_url}{doc_link['href']}"

                    filings.append({
                        "form_type": form_type,
                        "filer": filer,
                        "filing_date": filing_date,
                        "document_url": doc_url,
                    })

                logger.info(f"Found {len(filings)} 13D/13G filings for {company.ticker}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "filings": filings,
                    "timestamp": datetime.utcnow(),
                }

        except Exception as e:
            logger.error(f"Error fetching 13D/13G filings: {e}")
            return {"company_id": company.id, "filings": []}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process 13D/13G filings into signals.

        Signals generated:
        - New 13D = activist interest (very bullish)
        - New 13G = institutional conviction (bullish)
        - 13D/A = activist update (analyze if increasing/decreasing)
        - Known activist = higher score
        """
        filings = raw_data.get("filings", [])

        if not filings:
            return []

        signals = []

        for filing in filings:
            form_type = filing.get("form_type", "")
            filer = filing.get("filer", "").lower()
            filing_date = filing.get("filing_date", "")

            # Determine if activist or passive
            is_13d = "13D" in form_type and "13G" not in form_type
            is_amendment = "/A" in form_type

            # Check if known activist
            is_known_activist = any(activist in filer for activist in self.ACTIVIST_INVESTORS)

            # Score calculation
            score = 0

            if is_13d:
                if is_amendment:
                    score = 30  # Amendment to 13D (update to active position)
                else:
                    score = 70  # New 13D filing (activist taking position!)
            else:  # 13G
                if is_amendment:
                    score = 15  # Amendment to 13G
                else:
                    score = 40  # New 13G (passive conviction)

            # Boost for known activists
            if is_known_activist:
                score += 20
                score = min(100, score)

            # Confidence
            confidence = 0.90 if is_13d else 0.75

            # Description
            filing_type = "SC 13D" if is_13d else "SC 13G"
            if is_amendment:
                filing_type += "/A"

            description = f"{filing_type} filed by {filing.get('filer', 'Unknown')}"

            if is_13d:
                description += " | 🚨 ACTIVIST POSITION"
            if is_known_activist:
                description += " | ⭐ KNOWN ACTIVIST"

            signal = Signal(
                company_id=company.id,
                signal_type=self.metadata.signal_type,
                category=self.metadata.category,
                timestamp=datetime.strptime(filing_date, "%Y-%m-%d") if filing_date else datetime.utcnow(),
                raw_value={
                    "form_type": form_type,
                    "filer": filing.get("filer"),
                    "is_activist": is_13d,
                    "is_known_activist": is_known_activist,
                    "document_url": filing.get("document_url"),
                },
                normalized_value=score / 100.0,
                score=score,
                confidence=confidence,
                metadata=SignalMetadata(
                    source_url=filing.get("document_url", ""),
                    source_name="SEC 13D/13G Filings",
                    processing_notes=f"{filing_type} by {filing.get('filer')}",
                    raw_data_hash=hashlib.md5(
                        json.dumps(filing, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                ),
                description=description,
                tags=["13d", "13g", "activist", "ownership"],
            )

            signals.append(signal)

        return signals

"""
SEC Risk Factors Signal Processor

Extracts and analyzes "Risk Factors" section from 10-K and 10-Q filings.
Tracks changes in disclosed risks over time.

Risk Factors appear in:
- Item 1A of Form 10-K (annual)
- Item 1A of Form 10-Q (quarterly, if materially changed)

Signals:
- New risks added = negative signal
- Risks removed = positive signal
- Risk language becoming more severe = negative
- Number of risks increasing = negative
- Specific high-risk keywords (bankruptcy, litigation, regulatory) = very negative

Data Source: SEC EDGAR Filings
Update Frequency: Quarterly
"""

from typing import List, Any, Dict, Optional, Set
from datetime import datetime
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


class SECRiskFactorsProcessor(SignalProcessor):
    """Extract and analyze Risk Factors from 10-K/10-Q filings"""

    # High-severity risk keywords
    HIGH_SEVERITY_KEYWORDS = [
        "bankruptcy", "insolvent", "default", "violation",
        "investigation", "litigation", "lawsuit", "regulatory action",
        "going concern", "material weakness", "cybersecurity breach",
        "data breach", "fraud", "criminal", "sanctions"
    ]

    MODERATE_SEVERITY_KEYWORDS = [
        "competitive pressure", "market downturn", "recession",
        "supply chain", "talent retention", "customer concentration",
        "regulatory changes", "compliance costs", "interest rate"
    ]

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
            signal_type="sec_risk_factors",
            category=SignalCategory.REGULATORY,
            description="Risk factor disclosures from 10-K/10-Q - track changes over time",
            update_frequency=UpdateFrequency.QUARTERLY,
            data_source="SEC EDGAR",
            cost=DataCost.FREE,
            difficulty=Difficulty.HARD,
            tags=["risk_factors", "regulatory", "sec", "10-k", "10-q"],
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
        Fetch 10-K/10-Q filings that contain Risk Factors.
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
                logger.info(f"Fetching Risk Factors filings for {company.ticker}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                filings = data.get("filings", {}).get("recent", {})

                if not filings:
                    return {}

                # Get last 4 10-K and 10-Q filings (covers ~1 year)
                form_types = filings.get("form", [])
                filing_dates = filings.get("filingDate", [])
                accession_numbers = filings.get("accessionNumber", [])
                primary_documents = filings.get("primaryDocument", [])

                relevant_filings = []

                for i in range(len(form_types)):
                    if form_types[i] in ["10-K", "10-Q"]:
                        filing_date = datetime.strptime(filing_dates[i], "%Y-%m-%d")

                        relevant_filings.append({
                            "form_type": form_types[i],
                            "filing_date": filing_dates[i],
                            "accession_number": accession_numbers[i],
                            "primary_document": primary_documents[i],
                            "cik": cik,
                        })

                        # Limit to 4 most recent
                        if len(relevant_filings) >= 4:
                            break

                logger.info(f"Found {len(relevant_filings)} 10-K/10-Q filings for risk analysis")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "cik": cik,
                    "filings": relevant_filings,
                    "timestamp": datetime.utcnow(),
                }

        except Exception as e:
            logger.error(f"Error fetching risk factors data: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process risk factors from filings into signals.

        Analyzes each filing and generates signal based on:
        - Risk severity (keywords)
        - Change in number of risks
        - New risks vs previous filing
        """
        filings = raw_data.get("filings", [])

        if not filings:
            return []

        signals = []

        # Process each filing
        for i, filing in enumerate(filings):
            try:
                # Extract risk factors text
                risk_text = self._extract_risk_factors(filing)

                if not risk_text:
                    logger.warning(f"No risk factors found in {filing['form_type']} from {filing['filing_date']}")
                    continue

                # Analyze risk factors
                analysis = self._analyze_risks(risk_text)

                # Compare to previous filing if available
                if i < len(filings) - 1:
                    prev_filing = filings[i + 1]
                    prev_risk_text = self._extract_risk_factors(prev_filing)
                    if prev_risk_text:
                        prev_analysis = self._analyze_risks(prev_risk_text)
                        analysis["changes"] = self._compare_risks(prev_analysis, analysis)

                # Generate signal
                signal = self._create_signal(company, filing, analysis)

                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"Error processing risk factors from {filing['filing_date']}: {e}")
                continue

        logger.info(f"Generated {len(signals)} risk factor signals")
        return signals

    def _extract_risk_factors(self, filing: Dict[str, Any]) -> Optional[str]:
        """
        Extract Risk Factors section from filing HTML.

        Risk Factors appear in:
        - Item 1A of 10-K/10-Q
        - Between headers "Item 1A" and "Item 1B" (or "Item 2")
        """
        accession = filing["accession_number"].replace("-", "")
        cik = filing["cik"]
        doc = filing["primary_document"]

        url = f"{self.doc_url}/Archives/edgar/data/{cik}/{accession}/{doc}"

        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text()

            # Find "Item 1A. Risk Factors" section
            # Pattern: "Item 1A" ... "Risk Factors" followed by content until next item
            item_1a_pattern = r'Item\s+1A\.?\s*Risk\s+Factors(.*?)(?:Item\s+1B|Item\s+2\.)'
            match = re.search(item_1a_pattern, text, re.IGNORECASE | re.DOTALL)

            if match:
                risk_text = match.group(1).strip()
                logger.debug(f"Extracted {len(risk_text)} chars of risk factors")
                return risk_text
            else:
                logger.warning("Could not find Item 1A Risk Factors section")
                return None

        except Exception as e:
            logger.warning(f"Error extracting risk factors: {e}")
            return None

    def _analyze_risks(self, risk_text: str) -> Dict[str, Any]:
        """
        Analyze risk factors text.

        Returns dict with:
        - high_severity_count: count of high severity keywords
        - moderate_severity_count: count of moderate severity keywords
        - total_word_count: length of risk section
        - risk_keywords: list of found keywords
        """
        high_severity_matches = []
        moderate_severity_matches = []

        # Find high severity keywords
        for keyword in self.HIGH_SEVERITY_KEYWORDS:
            pattern = rf'\b{re.escape(keyword)}\b'
            matches = re.findall(pattern, risk_text, re.IGNORECASE)
            if matches:
                high_severity_matches.append((keyword, len(matches)))

        # Find moderate severity keywords
        for keyword in self.MODERATE_SEVERITY_KEYWORDS:
            pattern = rf'\b{re.escape(keyword)}\b'
            matches = re.findall(pattern, risk_text, re.IGNORECASE)
            if matches:
                moderate_severity_matches.append((keyword, len(matches)))

        return {
            "high_severity_count": sum(count for _, count in high_severity_matches),
            "moderate_severity_count": sum(count for _, count in moderate_severity_matches),
            "high_severity_keywords": [kw for kw, _ in high_severity_matches],
            "moderate_severity_keywords": [kw for kw, _ in moderate_severity_matches],
            "word_count": len(risk_text.split()),
        }

    def _compare_risks(self, prev_analysis: Dict, current_analysis: Dict) -> Dict:
        """
        Compare current vs previous risk factors.

        Returns changes:
        - new_high_severity: new high severity keywords
        - removed_high_severity: removed high severity keywords
        - word_count_change: change in total words (expansion = negative)
        """
        prev_high = set(prev_analysis.get("high_severity_keywords", []))
        curr_high = set(current_analysis.get("high_severity_keywords", []))

        prev_words = prev_analysis.get("word_count", 0)
        curr_words = current_analysis.get("word_count", 0)

        return {
            "new_high_severity": list(curr_high - prev_high),
            "removed_high_severity": list(prev_high - curr_high),
            "word_count_change": curr_words - prev_words,
            "word_count_pct_change": ((curr_words - prev_words) / prev_words * 100) if prev_words > 0 else 0,
        }

    def _create_signal(
        self,
        company: Company,
        filing: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Optional[Signal]:
        """
        Create signal from risk analysis.

        Scoring:
        - High severity keywords = -10 each
        - Moderate severity keywords = -3 each
        - New high severity risks = -20 each
        - Removed high severity risks = +15 each
        - Word count increase >20% = -20
        """
        score = 0

        # Base severity score
        high_count = analysis.get("high_severity_count", 0)
        moderate_count = analysis.get("moderate_severity_count", 0)

        score -= high_count * 10
        score -= moderate_count * 3

        # Changes from previous filing
        changes = analysis.get("changes", {})
        new_high = changes.get("new_high_severity", [])
        removed_high = changes.get("removed_high_severity", [])
        word_change_pct = changes.get("word_count_pct_change", 0)

        score -= len(new_high) * 20
        score += len(removed_high) * 15

        if word_change_pct > 20:
            score -= 20
        elif word_change_pct < -20:
            score += 15

        # Normalize to -100 to +100
        score = max(-100, min(100, score))

        # Build description
        high_keywords = analysis.get("high_severity_keywords", [])
        description_parts = []

        if high_count > 0:
            description_parts.append(f"{high_count} high-severity risks")
            if high_keywords:
                top_3 = high_keywords[:3]
                description_parts.append(f"({', '.join(top_3)})")

        if new_high:
            description_parts.append(f"⚠ {len(new_high)} new critical risks")

        if removed_high:
            description_parts.append(f"✓ {len(removed_high)} risks removed")

        if word_change_pct > 20:
            description_parts.append(f"Risk disclosures expanded {word_change_pct:.0f}%")

        description = f"Risk Factors ({filing['form_type']}): " + " | ".join(description_parts) if description_parts else f"Risk Factors ({filing['form_type']}): {high_count} high-severity, {moderate_count} moderate"

        # Confidence based on data quality
        confidence = 0.75 if high_count > 0 else 0.65

        filing_date = datetime.strptime(filing["filing_date"], "%Y-%m-%d")

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=filing_date,
            raw_value={"filing": filing, "analysis": analysis},
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"{self.doc_url}/cgi-bin/browse-edgar?action=getcompany&CIK={filing['cik']}&type={filing['form_type']}",
                source_name=f"SEC EDGAR {filing['form_type']}",
                processing_notes=f"High severity: {high_count}, Moderate: {moderate_count}",
                raw_data_hash=hashlib.md5(
                    json.dumps(analysis, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["risk_factors", filing["form_type"].lower()],
        )

        return signal

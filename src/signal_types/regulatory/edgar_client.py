"""
Shared EDGAR API client for SEC filing processors.

Fetches ALL filings for a CIK, including archived batches beyond the
~100 most recent filings returned in the `recent` array. The EDGAR
submissions endpoint also includes a `files` array referencing older
filing batches (e.g., CIK0001543151-submissions-001.json).

This client:
- Fetches the main submissions JSON
- Reads filings.recent (current behavior)
- Iterates through filings.files[] and fetches each archived batch
- Merges all filing arrays together
- Filters by form type and date range
- Handles SEC rate limiting (0.15s between requests)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

import httpx
from loguru import logger


class EdgarClient:
    """Reusable async client for fetching all SEC EDGAR filings for a CIK."""

    BASE_URL = "https://data.sec.gov"

    def __init__(self, user_agent: str = "cousin-eddie research@example.com"):
        self.user_agent = user_agent
        self._headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    async def get_all_filings(
        self,
        cik: str,
        form_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL filings of a given form type for a CIK, including archives.

        Args:
            cik: SEC CIK number (will be zero-padded to 10 digits)
            form_type: Form type to filter for (e.g., "4", "8-K", "144")
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of filing dicts with keys: accessionNumber, filingDate,
            primaryDocument, acceptanceDateTime, reportDate,
            primaryDocDescription, form
        """
        cik = cik.zfill(10)
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching EDGAR submissions for CIK {cik}")
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()

                data = response.json()

                filings_data = data.get("filings", {})
                recent = filings_data.get("recent", {})
                files = filings_data.get("files", [])

                if not recent:
                    logger.warning(f"No filings found for CIK {cik}")
                    return []

                # Collect all filing arrays: start with recent
                all_filing_arrays = [recent]

                # Fetch each archived batch
                for file_ref in files:
                    file_name = file_ref.get("name", "")
                    if not file_name:
                        continue

                    archive_url = f"{self.BASE_URL}/submissions/{file_name}"
                    logger.debug(f"Fetching archived filings: {file_name}")

                    await asyncio.sleep(0.15)  # SEC rate limit

                    try:
                        archive_response = await client.get(
                            archive_url, headers=self._headers
                        )
                        archive_response.raise_for_status()
                        archive_data = archive_response.json()
                        all_filing_arrays.append(archive_data)
                    except Exception as e:
                        logger.warning(f"Failed to fetch archive {file_name}: {e}")
                        continue

                # Merge and filter
                matched = self._filter_filings(
                    all_filing_arrays, form_type, start_date, end_date
                )

                logger.info(
                    f"Found {len(matched)} {form_type} filings for CIK {cik} "
                    f"({start_date.date()} to {end_date.date()}) "
                    f"from {len(all_filing_arrays)} batch(es)"
                )

                return matched

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching EDGAR submissions for CIK {cik}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching EDGAR submissions for CIK {cik}: {e}")
            return []

    def _filter_filings(
        self,
        filing_arrays: List[Dict[str, Any]],
        form_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Merge multiple filing arrays and filter by form type and date range.

        Each filing array has parallel lists: form[], filingDate[],
        accessionNumber[], primaryDocument[], etc.
        """
        matched = []

        # Keys we want to extract from each filing
        keys = [
            "form",
            "filingDate",
            "accessionNumber",
            "primaryDocument",
            "acceptanceDateTime",
            "reportDate",
            "primaryDocDescription",
        ]

        for filings in filing_arrays:
            forms = filings.get("form", [])
            num_filings = len(forms)

            for i in range(num_filings):
                if forms[i] != form_type:
                    continue

                filing_date_str = filings.get("filingDate", [])[i]
                try:
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")
                except (ValueError, IndexError):
                    continue

                if not (start_date <= filing_date <= end_date):
                    continue

                filing = {}
                for key in keys:
                    arr = filings.get(key, [])
                    filing[key] = arr[i] if i < len(arr) else None

                matched.append(filing)

        return matched

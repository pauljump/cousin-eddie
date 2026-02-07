"""
Job Postings Signal Processor

Tracks hiring velocity by scraping company career pages and job boards.
Hiring surges = expansion (bullish), hiring freezes = contraction (bearish).

Research shows 66% drop in job postings predicted Booz Allen's stock collapse.

Data Source: Company career pages + Indeed (free)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
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


class JobPostingsProcessor(SignalProcessor):
    """Process job posting data from career pages"""

    def __init__(self):
        # Greenhouse board tokens for companies using Greenhouse ATS
        self.greenhouse_boards = {
            # Add companies using Greenhouse ATS here
        }

        # Fallback career page URLs for custom ATS
        self.career_urls = {
            "UBER": "https://www.uber.com/us/en/careers/",
        }

        # Manual counts for companies with strong anti-scraping protection
        # Update these periodically by manually checking their careers pages
        # Format: "COMPANY_ID": (job_count, "last_updated_date", "notes")
        self.manual_counts = {
            "UBER": (850, "2026-02-07", "Checked jobs.uber.com manually - strong anti-bot protection"),
        }

        self.greenhouse_api = "https://boards-api.greenhouse.io/v1/boards"
        self.indeed_base = "https://www.indeed.com"

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="job_postings",
            category=SignalCategory.WORKFORCE,
            description="Hiring velocity from career pages - expansion vs contraction signal",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Company careers page + Indeed",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM,
            tags=["hiring", "workforce", "jobs", "expansion"],
        )

    def is_applicable(self, company: Company) -> bool:
        """All companies hire"""
        return True

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch job posting counts.

        For MVP: Just count jobs on career page and Indeed.
        Future: Track historical data to detect velocity changes.
        """

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            results = {
                "company_id": company.id,
                "timestamp": datetime.utcnow(),
                "sources": {}
            }

            # Check for manual count first (for companies with anti-scraping protection)
            if company.id in self.manual_counts:
                count, last_updated, notes = self.manual_counts[company.id]
                results["sources"]["manual"] = {
                    "job_count": count,
                    "last_updated": last_updated,
                    "notes": notes,
                    "status": "success"
                }
                logger.info(f"Using manual count for {company.ticker}: {count} jobs (updated: {last_updated})")

            # Try Greenhouse API first (most reliable)
            if company.id in self.greenhouse_boards:
                try:
                    board_token = self.greenhouse_boards[company.id]
                    greenhouse_url = f"{self.greenhouse_api}/{board_token}/jobs"
                    logger.info(f"Fetching {company.ticker} jobs from Greenhouse: {greenhouse_url}")

                    response = await client.get(
                        greenhouse_url,
                        headers={"User-Agent": "Alternative Data Platform research@example.com"}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        jobs = data.get("jobs", [])

                        # Group by category/location for richer data
                        categories = {}
                        locations = {}

                        for job in jobs:
                            # Get category from metadata
                            category = "Other"
                            metadata = job.get("metadata", [])
                            for meta in metadata:
                                if meta.get("name") == "Career Site Category":
                                    category = meta.get("value", "Other")
                                    break

                            loc = job.get("location", {}).get("name", "Unknown")

                            categories[category] = categories.get(category, 0) + 1
                            locations[loc] = locations.get(loc, 0) + 1

                        results["sources"]["greenhouse"] = {
                            "url": greenhouse_url,
                            "total_jobs": len(jobs),
                            "categories": categories,
                            "locations": locations,
                            "status": "success"
                        }
                        logger.info(f"Greenhouse API: {len(jobs)} open positions")
                    else:
                        results["sources"]["greenhouse"] = {
                            "url": greenhouse_url,
                            "status": "failed",
                            "error": f"HTTP {response.status_code}"
                        }
                except Exception as e:
                    logger.warning(f"Error fetching Greenhouse data: {e}")
                    results["sources"]["greenhouse"] = {
                        "status": "error",
                        "error": str(e)
                    }

            # Try company career page (fallback for non-Greenhouse companies)
            if company.id in self.career_urls:
                try:
                    career_url = self.career_urls[company.id]
                    logger.info(f"Fetching {company.ticker} career page: {career_url}")

                    response = await client.get(
                        career_url,
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                    )

                    if response.status_code == 200:
                        # Simple heuristic: look for job-related keywords
                        html = response.text
                        soup = BeautifulSoup(html, 'html.parser')

                        # Count "jobs" mentions or job listing elements
                        # This is a rough estimate - real implementation would parse structured data
                        job_count_estimate = len(soup.find_all(text=re.compile(r'\bjob\b', re.I)))

                        results["sources"]["career_page"] = {
                            "url": career_url,
                            "estimated_jobs": job_count_estimate,
                            "status": "success"
                        }
                        logger.info(f"Career page estimate: ~{job_count_estimate} job mentions")
                    else:
                        results["sources"]["career_page"] = {
                            "url": career_url,
                            "status": "failed",
                            "error": f"HTTP {response.status_code}"
                        }
                except Exception as e:
                    logger.warning(f"Error fetching career page: {e}")
                    results["sources"]["career_page"] = {
                        "status": "error",
                        "error": str(e)
                    }

            # Try Indeed (counts open positions)
            try:
                # Indeed search: "company name" jobs
                indeed_url = f"{self.indeed_base}/jobs?q={company.name}&l="
                logger.info(f"Fetching Indeed jobs: {indeed_url}")

                response = await client.get(
                    indeed_url,
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                )

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Indeed shows job count in search results
                    # Look for text like "Page 1 of 234 jobs"
                    job_count = 0

                    # Try to find the job count element
                    count_text = soup.find('div', {'class': re.compile(r'jobsearch-JobCountAndSortPane')})
                    if count_text:
                        text = count_text.get_text()
                        # Extract number
                        matches = re.findall(r'(\d+)\s+jobs?', text)
                        if matches:
                            job_count = int(matches[0])

                    # Also count actual job cards as backup
                    job_cards = soup.find_all('div', {'class': re.compile(r'job_seen_beacon')})
                    job_cards_count = len(job_cards)

                    results["sources"]["indeed"] = {
                        "url": indeed_url,
                        "job_count": job_count if job_count > 0 else job_cards_count,
                        "job_cards_found": job_cards_count,
                        "status": "success"
                    }
                    logger.info(f"Indeed jobs: {job_count if job_count > 0 else job_cards_count}")
                else:
                    results["sources"]["indeed"] = {
                        "status": "failed",
                        "error": f"HTTP {response.status_code}"
                    }
            except Exception as e:
                logger.warning(f"Error fetching Indeed: {e}")
                results["sources"]["indeed"] = {
                    "status": "error",
                    "error": str(e)
                }

            return results

    def process(
        self,
        company: Company,
        raw_data: Dict[str, Any]
    ) -> List[Signal]:
        """
        Process job posting data into signals.

        Scoring logic:
        - High job count (>1000) for large company = expansion = +60 to +80
        - Medium (100-1000) = steady growth = +30 to +50
        - Low (<100) = maintenance/slowdown = -10 to +10
        - For velocity: Compare to historical baseline (not implemented yet)
        """

        timestamp = raw_data.get("timestamp", datetime.utcnow())
        sources = raw_data.get("sources", {})

        # Aggregate job counts from all sources
        total_jobs = 0
        any_source_succeeded = False
        primary_source = None

        # Get all source objects upfront
        manual = sources.get("manual", {})
        greenhouse = sources.get("greenhouse", {})
        career_page = sources.get("career_page", {})
        indeed = sources.get("indeed", {})

        # Manual count is most reliable (verified by human)
        if manual.get("status") == "success":
            total_jobs = manual.get("job_count", 0)
            any_source_succeeded = True
            primary_source = "manual"
        # Greenhouse is second most reliable
        elif greenhouse.get("status") == "success":
            total_jobs = greenhouse.get("total_jobs", 0)
            any_source_succeeded = True
            primary_source = "greenhouse"
        else:
            # Fall back to other sources
            if career_page.get("status") == "success":
                total_jobs += career_page.get("estimated_jobs", 0)
                any_source_succeeded = True
                primary_source = "career_page"

            if indeed.get("status") == "success":
                total_jobs += indeed.get("job_count", 0)
                any_source_succeeded = True
                if not primary_source:
                    primary_source = "indeed"

        # If ALL sources failed, don't create a misleading signal
        if not any_source_succeeded:
            logger.warning(f"All job posting sources failed for {company.ticker} - skipping signal")
            return []

        # Score based on absolute count (will improve with historical data)
        # TODO: Track historical average and score based on % change
        score = 0

        # Determine base confidence based on source reliability
        if primary_source == "manual":
            base_confidence = 0.90  # Manually verified is most reliable
        elif primary_source == "greenhouse":
            base_confidence = 0.85  # Greenhouse API is very reliable
        else:
            base_confidence = 0.6  # Scraped data is less reliable

        if total_jobs > 1000:
            score = 75
            confidence = base_confidence
            description = f"High hiring activity: {total_jobs:,} open positions (expansion signal)"
        elif total_jobs > 500:
            score = 50
            confidence = base_confidence - 0.05
            description = f"Moderate hiring: {total_jobs:,} open positions (growth signal)"
        elif total_jobs > 100:
            score = 25
            confidence = base_confidence - 0.10
            description = f"Steady hiring: {total_jobs:,} open positions"
        elif total_jobs > 50:
            score = 0
            confidence = base_confidence - 0.15
            description = f"Low hiring: {total_jobs:,} open positions (neutral)"
        else:
            score = -20
            confidence = base_confidence - 0.20
            description = f"Minimal hiring: {total_jobs:,} open positions (potential contraction)"

        # Add category breakdown to description if available
        if greenhouse.get("status") == "success":
            categories = greenhouse.get("categories", {})
            if categories:
                top_cat = max(categories.items(), key=lambda x: x[1])
                description += f" | Top category: {top_cat[0]} ({top_cat[1]} positions)"

        normalized_value = score / 100.0

        # Determine source name and URL
        if primary_source == "manual":
            manual_data = sources.get("manual", {})
            source_name = f"Manual Count (updated: {manual_data.get('last_updated', 'unknown')})"
            source_url = sources.get("career_page", {}).get("url", "")  # Link to career page for reference
        elif primary_source == "greenhouse":
            source_name = "Greenhouse API"
            source_url = sources.get("greenhouse", {}).get("url", "")
        elif primary_source == "career_page":
            source_name = "Career Page"
            source_url = sources.get("career_page", {}).get("url", "")
        else:
            source_name = "Indeed"
            source_url = sources.get("indeed", {}).get("url", "")

        # Create signal
        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=timestamp,
            raw_value=raw_data,
            normalized_value=normalized_value,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=source_url,
                source_name=source_name,
                processing_notes=f"Primary source: {primary_source} | {len(sources)} sources checked",
                raw_data_hash=hashlib.md5(
                    json.dumps(raw_data, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["hiring", "jobs", "workforce", "expansion"],
        )

        return [signal]


# Historical tracking helper (for future implementation)
class JobPostingTracker:
    """
    Track job posting counts over time to detect velocity changes.

    This would store daily snapshots and calculate:
    - 7-day moving average
    - 30-day % change
    - YoY comparison

    Then score based on velocity:
    - +50% month-over-month = +90 score (major expansion)
    - +20% = +60
    - -20% = -40
    - -50% = -80 (major contraction like Booz Allen)
    """

    def __init__(self):
        self.history: Dict[str, List[Dict]] = {}

    def add_snapshot(self, company_id: str, timestamp: datetime, job_count: int):
        """Add a snapshot"""
        if company_id not in self.history:
            self.history[company_id] = []

        self.history[company_id].append({
            "timestamp": timestamp,
            "count": job_count
        })

    def calculate_velocity(self, company_id: str, days_back: int = 30) -> Optional[float]:
        """Calculate % change over last N days"""
        if company_id not in self.history or len(self.history[company_id]) < 2:
            return None

        snapshots = self.history[company_id]
        snapshots.sort(key=lambda x: x["timestamp"])

        # Get latest and N days ago
        latest = snapshots[-1]
        cutoff = latest["timestamp"] - timedelta(days=days_back)

        historical = [s for s in snapshots if s["timestamp"] <= cutoff]
        if not historical:
            return None

        old_count = historical[-1]["count"]
        new_count = latest["count"]

        if old_count == 0:
            return None

        return ((new_count - old_count) / old_count) * 100

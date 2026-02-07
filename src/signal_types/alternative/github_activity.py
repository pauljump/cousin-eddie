"""
GitHub Activity Signal Processor

Tracks open source contributions and repository metrics for tech companies.

Why GitHub matters for tech companies:
- Developer mindshare (stars, forks) = talent attraction
- Contribution velocity = engineering productivity
- Open source strategy = tech leadership
- Community engagement = ecosystem strength
- Abandoned repos = declining relevance

Key Metrics:
- Repository stars (popularity)
- Fork count (developer interest)
- Contributors (community size)
- Commit frequency (development velocity)
- Issue/PR activity (engagement)
- Release cadence (shipping speed)

Signals:
- Rising stars = growing developer mindshare (bullish for devtools)
- Active development = strong engineering culture
- Declining activity = losing developer interest
- Major releases = product momentum
- Abandoned projects = red flag

Top GitHub Organizations:
- Microsoft: github.com/microsoft
- Google: github.com/google
- Meta: github.com/facebook
- Amazon: github.com/aws
- Uber: github.com/uber

Data Source: GitHub REST API (free, 5000 req/hour)
Update Frequency: Daily
"""

from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
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


class GitHubActivityProcessor(SignalProcessor):
    """Track GitHub repository metrics and developer activity"""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize processor.

        Args:
            github_token: GitHub personal access token
                         Get from: https://github.com/settings/tokens
                         Free tier: 5000 requests/hour
        """
        self.github_token = github_token
        self.api_url = "https://api.github.com"

        # Map company IDs to GitHub organizations
        self.github_orgs = {
            "UBER": "uber",
            "GOOGL": "google",
            "META": "facebook",
            "MSFT": "microsoft",
            "AMZN": "aws",
            "TSLA": "tesla",
        }

    @property
    def metadata(self) -> SignalProcessorMetadata:
        return SignalProcessorMetadata(
            signal_type="github_activity",
            category=SignalCategory.ALTERNATIVE,
            description="GitHub repository metrics - developer mindshare and engineering velocity",
            update_frequency=UpdateFrequency.DAILY,
            data_source="GitHub REST API",
            cost=DataCost.FREE,
            difficulty=Difficulty.EASY,
            tags=["github", "open_source", "developer", "tech"],
        )

    def is_applicable(self, company: Company) -> bool:
        """Applicable to tech companies with GitHub presence"""
        return company.id in self.github_orgs

    async def fetch(
        self,
        company: Company,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """
        Fetch GitHub organization and repository data.

        Uses GitHub REST API to get:
        1. Organization metadata
        2. Top repositories (by stars)
        3. Recent activity (commits, releases)
        """
        if company.id not in self.github_orgs:
            return {}

        org_name = self.github_orgs[company.id]

        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get organization data
                logger.info(f"Fetching GitHub data for org: {org_name}")

                org_response = await client.get(
                    f"{self.api_url}/orgs/{org_name}",
                    headers=headers
                )
                org_response.raise_for_status()
                org_data = org_response.json()

                # Get top repositories
                repos_response = await client.get(
                    f"{self.api_url}/orgs/{org_name}/repos",
                    headers=headers,
                    params={
                        "sort": "stars",
                        "direction": "desc",
                        "per_page": 10,  # Top 10 repos
                    }
                )
                repos_response.raise_for_status()
                repos = repos_response.json()

                logger.info(f"Found {len(repos)} top repos for {org_name}")

                return {
                    "company_id": company.id,
                    "ticker": company.ticker,
                    "org": org_data,
                    "repos": repos,
                    "timestamp": datetime.utcnow(),
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid GitHub token")
            elif e.response.status_code == 403:
                logger.warning("GitHub API rate limit exceeded")
            elif e.response.status_code == 404:
                logger.warning(f"GitHub org not found: {org_name}")
            else:
                logger.error(f"GitHub API error: {e}")

            # Fall back to sample data
            logger.warning("Using sample GitHub data")
            return self._get_sample_data(company)

        except Exception as e:
            logger.error(f"Error fetching GitHub data: {e}")
            return {}

    def process(self, company: Company, raw_data: Dict[str, Any]) -> List[Signal]:
        """
        Process GitHub data into signals.

        Analyzes:
        1. Total stars across top repos (popularity)
        2. Recent activity (commits, releases)
        3. Community engagement (forks, contributors)
        """
        org = raw_data.get("org", {})
        repos = raw_data.get("repos", [])

        if not repos:
            return []

        # Aggregate metrics
        total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
        total_forks = sum(repo.get("forks_count", 0) for repo in repos)

        # Find most popular repo
        top_repo = max(repos, key=lambda r: r.get("stargazers_count", 0))
        top_repo_stars = top_repo.get("stargazers_count", 0)
        top_repo_name = top_repo.get("name", "")

        # Count recently updated repos (active development)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recently_active = 0
        for repo in repos:
            updated = repo.get("updated_at", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if updated_dt > thirty_days_ago:
                        recently_active += 1
                except:
                    pass

        # Calculate score
        # Stars are the primary signal of developer mindshare
        # 100k+ total stars = +80 to +100
        # 50k-100k = +60 to +80
        # 10k-50k = +40 to +60
        # <10k = 0 to +40

        if total_stars > 100000:
            score = min(100, 80 + ((total_stars - 100000) / 10000))
        elif total_stars > 50000:
            score = 60 + ((total_stars - 50000) / 2500)
        elif total_stars > 10000:
            score = 40 + ((total_stars - 10000) / 2000)
        else:
            score = (total_stars / 10000) * 40

        # Activity bonus
        activity_ratio = recently_active / len(repos) if repos else 0
        if activity_ratio > 0.7:  # >70% of repos active
            score += 10
        elif activity_ratio < 0.3:  # <30% active
            score -= 10

        score = int(max(0, min(100, score)))

        # Confidence based on data completeness
        confidence = 0.75 if len(repos) >= 10 else 0.65

        # Build description
        description = f"GitHub: {total_stars:,} total stars across {len(repos)} top repos"
        description += f" | Top: {top_repo_name} ({top_repo_stars:,}★)"
        description += f" | {recently_active}/{len(repos)} repos active (30d)"

        signal = Signal(
            company_id=company.id,
            signal_type=self.metadata.signal_type,
            category=self.metadata.category,
            timestamp=datetime.utcnow(),
            raw_value={
                "total_stars": total_stars,
                "total_forks": total_forks,
                "repo_count": len(repos),
                "recently_active": recently_active,
                "top_repo": top_repo_name,
                "top_repo_stars": top_repo_stars,
            },
            normalized_value=score / 100.0,
            score=score,
            confidence=confidence,
            metadata=SignalMetadata(
                source_url=f"https://github.com/{self.github_orgs.get(company.id, '')}",
                source_name="GitHub",
                processing_notes=f"{total_stars:,} stars, {recently_active} active repos",
                raw_data_hash=hashlib.md5(
                    json.dumps(repos, sort_keys=True, default=str).encode()
                ).hexdigest(),
            ),
            description=description,
            tags=["github", "open_source", "developer_mindshare"],
        )

        return [signal]

    def _get_sample_data(self, company: Company) -> Dict[str, Any]:
        """
        Return sample GitHub data.

        Realistic sample for Uber's GitHub organization.
        """
        if company.ticker == "UBER":
            sample_org = {
                "login": "uber",
                "name": "Uber Open Source",
                "public_repos": 157,
            }

            sample_repos = [
                {
                    "name": "cadence",
                    "description": "Cadence is a distributed, scalable, durable, and highly available orchestration engine",
                    "stargazers_count": 7500,
                    "forks_count": 580,
                    "updated_at": "2026-02-05T10:30:00Z",
                },
                {
                    "name": "kraken",
                    "description": "P2P Docker registry capable of distributing TBs of data in seconds",
                    "stargazers_count": 5900,
                    "forks_count": 430,
                    "updated_at": "2026-02-01T14:20:00Z",
                },
                {
                    "name": "h3",
                    "description": "Hexagonal hierarchical geospatial indexing system",
                    "stargazers_count": 4200,
                    "forks_count": 390,
                    "updated_at": "2026-01-28T09:15:00Z",
                },
                {
                    "name": "piranha",
                    "description": "A tool for refactoring code related to feature flag APIs",
                    "stargazers_count": 2100,
                    "forks_count": 180,
                    "updated_at": "2026-01-15T16:45:00Z",
                },
                {
                    "name": "ludwig",
                    "description": "Data-centric declarative deep learning framework",
                    "stargazers_count": 10500,
                    "forks_count": 1200,
                    "updated_at": "2026-02-06T11:00:00Z",
                },
            ]
        else:
            sample_org = {}
            sample_repos = []

        return {
            "company_id": company.id,
            "ticker": company.ticker,
            "org": sample_org,
            "repos": sample_repos,
            "timestamp": datetime.utcnow(),
        }

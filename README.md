# cousin-eddie

**Alternative Data Intelligence Platform for Quantitative Trading**

[![Signal Processors](https://img.shields.io/badge/Signal%20Processors-41-brightgreen)]()
[![Research Coverage](https://img.shields.io/badge/Research%20Coverage-100%25-brightgreen)]()
[![Real Data](https://img.shields.io/badge/Real%20Data-17%20processors-blue)]()
[![Cost](https://img.shields.io/badge/Monthly%20Cost-$0-success)]()

> **Status:** 41 signal processors implemented with 17 using real data sources. All free APIs documented.

## 📚 Quick Links

- **[Session Log](docs/SESSION_LOG.md)** - Latest progress and next steps
- **[Free API Setup](docs/FREE_API_SETUP.md)** - How to get free API keys
- **[EDGAR Audit](docs/EDGAR_DATA_AUDIT.md)** - SEC data coverage analysis
- **[Research Mapping](docs/CHATGPT_RESEARCH_MAPPING.md)** - Research → implementation tracking

## Vision

Democratize alternative data trading by building a signal-agnostic platform that can ingest 100+ signal types for ANY public company, giving solo traders the same data edge as hedge funds.

## Architecture

### Core Principles

- **Signal-type agnostic** - Easy to add new signal types via plugin architecture
- **Company agnostic** - Works for any public company
- **Normalized output** - All signals use standard schema (-100 to +100 score)
- **Time-series native** - Historical analysis built-in
- **Backtest-first** - Validate signals before trading

### Platform Layers

```
Layer 1: Signal Type Registry (100+ signal processors)
Layer 2: Data Ingestion Framework (plugin-based)
Layer 3: Orchestration Engine (parallel async processing)
Layer 4: Storage & Query (TimescaleDB time-series)
Layer 5: Analysis & Intelligence (anomaly detection, backtesting)
```

### Signal Categories

- **Regulatory** - SEC filings (8-K, 10-K, Form 4, etc.), patents, FDA approvals
- **Workforce** - Job postings, Glassdoor sentiment, LinkedIn growth
- **Web/Digital** - App rankings, reviews, Google Trends, web traffic
- **Geospatial** - Satellite imagery, parking lots, shipping, night lights
- **Product** - Amazon reviews, app ratings, sentiment
- **Government** - Import/export, grants, clinical trials
- **Financial** - Crypto on-chain, commodity prices, competitor proxies
- **Alternative** - Earnings call tone, social media, forums, citations

## POC: Uber

Initial implementation focuses on Uber Technologies (UBER) to validate the methodology with maximum applicable signal types before scaling to other companies.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL + TimescaleDB
- **AI/ML:** OpenAI, Anthropic Claude, scikit-learn
- **Queue:** Redis, Celery
- **Deployment:** Docker, Docker Compose

## Project Structure

```
src/
├── core/               # Core abstractions (SignalProcessor, Company, Signal)
├── signal_types/       # Signal processor plugins
│   ├── regulatory/
│   ├── workforce/
│   ├── web_digital/
│   ├── geospatial/
│   ├── product/
│   ├── government_data/
│   ├── financial/
│   └── alternative/
├── api/                # FastAPI application
├── db/                 # Database schemas and migrations
├── models/             # SQLAlchemy models
├── utils/              # Utilities (logging, config, etc.)
└── backtest/           # Backtesting framework

tests/
├── unit/
└── integration/

scripts/                # Utility scripts
config/                 # Configuration files
data/                   # Raw and processed data
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with TimescaleDB extension
- Redis 7+

### Installation

```bash
# Clone repository
git clone https://github.com/pauljump/cousin-eddie.git
cd cousin-eddie

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys and database credentials

# Setup database
docker-compose up -d postgres redis
python scripts/init_db.py

# Run migrations
alembic upgrade head
```

### Running the Platform

```bash
# Initialize database
python scripts/init_db.py

# Backfill historical data (dry run)
python scripts/backfill_signals.py --company UBER --dry-run

# Backfill historical data (real)
python scripts/backfill_signals.py --company UBER

# Backfill specific signals
python scripts/backfill_signals.py --company UBER --signals twitter_sentiment,news_sentiment

# Start continuous updates (daemon mode)
python scripts/update_signals.py --daemon

# One-time update
python scripts/update_signals.py --company UBER

# Verify processors loaded
python3 -c "from src.core.registry import get_processor_registry; r = get_processor_registry(); print(f'Loaded {len(r._processors)} processors')"
```

### Setting API Keys

```bash
# Required for some processors (all free tiers)
export TWITTER_BEARER_TOKEN="your_token"      # Get at: developer.twitter.com
export NEWS_API_KEY="your_key"                # Get at: newsapi.org/register
export YOUTUBE_API_KEY="your_key"             # Get at: console.cloud.google.com
export ALPHA_VANTAGE_API_KEY="your_key"       # Get at: alphavantage.co
export STACKEXCHANGE_API_KEY="your_key"       # Get at: stackapps.com

# Or use .env file
cat > .env << EOF
TWITTER_BEARER_TOKEN=your_token
NEWS_API_KEY=your_key
YOUTUBE_API_KEY=your_key
EOF
```

See `docs/FREE_API_SETUP.md` for detailed signup instructions.

## Current Status

### ✅ Completed (Phase 1-2)

- ✅ **41 Signal Processors Implemented** - 100% coverage of research
  - 9 SEC/Regulatory processors (Form 4, 10-K/Q, 8-K, 13F, 13D/13G, etc.)
  - 4 Workforce processors (Job postings, Glassdoor, LinkedIn)
  - 5 Web/Digital processors (App Store, Google Trends, Reddit, Wikipedia)
  - 23 Alternative data processors (Earnings tone, domains, satellites, etc.)
- ✅ **SignalProcessor Interface** - Plugin architecture complete
- ✅ **Database Schema** - PostgreSQL + TimescaleDB hypertables
- ✅ **Company Registry** - Uber Technologies configured
- ✅ **Backfill Pipeline** - Historical data seeding (`scripts/backfill_signals.py`)
- ✅ **Update Orchestration** - Continuous updates with daemon mode (`scripts/update_signals.py`)
- ✅ **Signal Normalization** - -100 to +100 scoring system

### 📊 Implementation Status

**Real Data (17 processors):**
- All SEC EDGAR processors using real APIs
- Google Trends, Reddit, GitHub, Wikipedia, LinkedIn
- Job postings, patents, App Store ratings, social media

**Need Free API Keys (6 processors):**
- Twitter, News, YouTube, Earnings Transcripts, Reviews, StackOverflow
- See `docs/FREE_API_SETUP.md` for signup links (all $0/month)

**Stubs/Prototypes (18 processors):**
- All 13 new research processors (need implementation)
- Some web scrapers need real implementation
- See `docs/SESSION_LOG.md` for detailed breakdown

### 🚀 Next Steps

**Immediate:**
- [ ] Get free API keys (Twitter, News - see `docs/FREE_API_SETUP.md`)
- [ ] Implement no-key APIs (Archive.org, ClinicalTrials.gov, NIH)
- [ ] Fix SEC Comment Letters + Footnote Analysis stubs
- [ ] Test backfill with real APIs

**Short Term:**
- [ ] Build API layer (FastAPI endpoints)
- [ ] Add backtesting framework
- [ ] Create signal aggregation system
- [ ] Add more EDGAR processors (DEF 14A, Form 3)

**Medium Term:**
- [ ] Multi-company support
- [ ] Dashboard/visualization
- [ ] Paper trading integration
- [ ] Data quality monitoring

## Signal Processor Interface

Each signal type implements:

```python
class SignalProcessor(ABC):
    @abstractmethod
    def is_applicable(self, company: Company) -> bool:
        """Can this signal apply to this company?"""

    @abstractmethod
    async def fetch(self, company: Company, start: datetime, end: datetime):
        """Fetch raw data from source"""

    @abstractmethod
    def process(self, raw_data) -> List[Signal]:
        """Convert raw data to normalized signals"""

    @abstractmethod
    def score(self, signal: Signal) -> float:
        """Score signal -100 (bearish) to +100 (bullish)"""
```

## Contributing

This is a solo project for now, but the architecture is designed to make adding new signal types trivial. See `docs/adding_signals.md` for details.

## License

MIT

## Acknowledgments

Research based on comprehensive alternative data intelligence report covering 100+ signal types used by quantitative hedge funds.

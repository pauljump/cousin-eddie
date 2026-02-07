# cousin-eddie

**Alternative Data Intelligence Platform for Quantitative Trading**

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
# Start API server
uvicorn src.api.main:app --reload

# Start Celery worker (for async signal processing)
celery -A src.core.tasks worker --loglevel=info

# Run signal ingestion for Uber
python scripts/ingest_signals.py --company UBER
```

## Development Roadmap

### Phase 1: Foundation (Week 1-2)
- [x] Project structure and dependencies
- [ ] SignalProcessor interface
- [ ] Database schema
- [ ] Company registry
- [ ] First signal processor (SEC Form 4)

### Phase 2: Core Signals (Week 3-4)
- [ ] 5 signal types implemented
- [ ] Orchestration pipeline
- [ ] API endpoints
- [ ] Basic dashboard

### Phase 3: Analysis (Week 5-6)
- [ ] Backtest framework
- [ ] Anomaly detection
- [ ] Signal correlation analysis
- [ ] Uber POC validation

### Phase 4: Scale (Week 7-8)
- [ ] Add 10 more signal types
- [ ] Multi-company support
- [ ] Advanced alerting
- [ ] Performance optimization

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

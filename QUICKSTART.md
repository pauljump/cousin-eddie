># Quick Start Guide

## What We've Built

✅ **Platform foundation** - Signal-agnostic architecture
✅ **Core abstractions** - SignalProcessor interface, Company registry, Signal model
✅ **Database schema** - PostgreSQL + TimescaleDB for time-series
✅ **First signal processor** - SEC Form 4 (insider trading)
✅ **Company registry** - Uber pre-loaded as POC

## Next Steps

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env and add:
# - Your email for SEC user agent
# - API keys (OpenAI/Anthropic) if using LLM processors
```

### 2. Start Database

```bash
# Start PostgreSQL + TimescaleDB
docker-compose up -d postgres redis

# Wait for services to be healthy
docker-compose ps

# Initialize database
python scripts/init_db.py
```

### 3. Test SEC Form 4 Processor

```bash
# Test the signal processor on Uber
python scripts/test_form4.py
```

This will:
- Fetch last 90 days of Form 4 filings for Uber
- Process them into signals
- Display the results

### 4. Build More Signal Processors

To add a new signal type, create a file like:

```python
# src/signal_types/workforce/job_postings.py

from ...core.signal_processor import SignalProcessor
from ...core.company import Company
from ...core.signal import Signal

class JobPostingsProcessor(SignalProcessor):
    @property
    def metadata(self):
        return SignalProcessorMetadata(
            signal_type="job_postings",
            category=SignalCategory.WORKFORCE,
            description="Hiring velocity from career pages",
            update_frequency=UpdateFrequency.DAILY,
            data_source="Company careers page + Indeed",
            cost=DataCost.FREE,
            difficulty=Difficulty.MEDIUM
        )

    def is_applicable(self, company: Company) -> bool:
        return True  # All companies hire

    async def fetch(self, company, start, end):
        # Scrape job postings
        pass

    def process(self, company, raw_data) -> List[Signal]:
        # Convert to signals
        pass
```

## What to Build Next

### Priority 1: More Signal Processors
1. **Job Postings** (workforce) - Career page scraping
2. **App Store Ratings** (web_digital) - iOS/Android app data
3. **Google Trends** (web_digital) - Search volume
4. **Glassdoor Sentiment** (workforce) - Employee reviews
5. **Earnings Call Tone** (alternative) - LLM sentiment analysis

### Priority 2: Orchestration
Create `src/core/orchestrator.py` to:
- Run multiple signal processors in parallel
- Store signals to database
- Handle rate limiting and errors
- Schedule periodic updates

### Priority 3: API Layer
Build FastAPI endpoints in `src/api/`:
- `GET /companies` - List companies
- `GET /companies/{id}/signals` - Get signals for a company
- `GET /signals/summary` - Aggregated signal view
- `POST /signals/ingest` - Trigger signal ingestion

### Priority 4: Backtest Framework
Create `src/backtest/engine.py` to:
- Correlate signals with price movements
- Calculate signal alpha (outperformance)
- Identify which signals actually work
- Generate performance reports

### Priority 5: Dashboard
Simple web UI showing:
- Signal timeline for a company
- Aggregated signal score
- Anomaly detection alerts
- Backtest results

## Current Limitations

The SEC Form 4 processor currently:
- ❌ Does NOT parse XML to extract transaction details
- ❌ Cannot determine if it's a buy or sell
- ❌ Cannot identify insider role or transaction size
- ✅ DOES detect that Form 4 was filed (timing signal)

**To make it fully functional:**
1. Fetch the XML from `primaryDocument` URL
2. Parse `<nonDerivativeTransaction>` elements
3. Extract transaction code, shares, price, insider info
4. Implement the scoring function (already drafted in code)

This applies to most signal processors - there's an MVP version (detect signal exists) and a full version (extract all details).

## Adding Uber-Specific Signals

For the POC, focus on signals where Uber has the most data:

**High Priority:**
- Driver forum sentiment (uberpeople.net, Reddit r/uberdrivers)
- App store ratings/reviews (Uber + Uber Eats)
- Competitor signals (Lyft, DoorDash as proxies)
- Weather correlation (rain = more rides)
- Gas price correlation (driver economics)

**Medium Priority:**
- City regulatory news (scrape council meetings)
- Airport traffic data (business travel proxy)
- Earnings call tone analysis

## Architecture Reminder

```
Your job: Build signal processors (easy, pluggable)
Platform's job: Orchestrate, store, analyze (reusable)

Add a signal type:
1. Create processor class
2. Implement 4 methods
3. Register it
4. Done - runs automatically for all applicable companies
```

## Questions?

Read the code:
- `src/core/signal_processor.py` - The interface
- `src/signal_types/regulatory/sec_form4.py` - Example implementation
- `src/core/company.py` - How companies work
- `src/core/signal.py` - The normalized signal format

The architecture is designed to make building new signal types as easy as possible. Focus on the data fetching and processing logic - the platform handles the rest.

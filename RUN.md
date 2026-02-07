# Running cousin-eddie

## Setup (One Time)

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Start database
docker-compose up -d postgres redis

# 3. Initialize database
python scripts/init_db.py
```

## Ingest Data

### Ingest Uber (all signals, last 30 days)
```bash
python scripts/ingest_signals.py --company UBER --days 30
```

### Ingest specific signals only
```bash
python scripts/ingest_signals.py --company UBER --days 7 --processors sec_form_4 app_store_ratings
```

### List available processors
```bash
python scripts/ingest_signals.py --list-processors
```

## Query Data

### View all signals for Uber
```bash
python scripts/query_signals.py --company UBER
```

### View specific signal type
```bash
python scripts/query_signals.py --company UBER --type app_store_ratings
```

### View last 7 days only
```bash
python scripts/query_signals.py --company UBER --days 7
```

### Summary statistics
```bash
python scripts/query_signals.py --summary
```

## What Gets Ingested

**For Uber, we collect:**

1. **SEC Form 4** - Insider trading filings (real-time)
2. **Job Postings** - Hiring velocity from Indeed + career page (daily)
3. **App Store Ratings** - Uber + Uber Eats app ratings/reviews (daily)
4. **Google Trends** - Search volume for "uber", "uber eats", "rideshare" (daily)

**Each signal includes:**
- Score: -100 (bearish) to +100 (bullish)
- Confidence: 0.0 to 1.0
- Raw data: Original source data
- Metadata: Source URL, processing notes, etc.
- Description: Human-readable summary

## Expected Output

**SEC Form 4:**
```
Signal: sec_form_4
Score: 0 (neutral until XML parsing implemented)
Description: Form 4 filing on 2026-01-15
```

**Job Postings:**
```
Signal: job_postings
Score: +75 (high hiring = expansion)
Description: High hiring activity: 1,234 open positions (expansion signal)
```

**App Store Ratings:**
```
Signal: app_store_ratings
Score: +50 (4.0/5 stars)
Description: uber: Good rating 4.2/5 (1,500,000 reviews)
```

**Google Trends:**
```
Signal: google_trends
Score: +20 (growing interest)
Description: uber: Growing interest (+15%)
```

## Troubleshooting

**"No signals found"**
- Check that database is running: `docker-compose ps`
- Check that processors are registered: `python scripts/ingest_signals.py --list-processors`
- Check logs for errors

**Rate limiting errors**
- SEC EDGAR: Limit to 10 requests/second (built-in)
- Google Trends: May throttle after many requests (wait 5 minutes)
- Indeed: May block scraping (use VPN or wait)

**Missing data**
- SEC Form 4: Only shows if there were actual filings in the time range
- App Store: Only works if app IDs are configured (Uber is pre-configured)
- Google Trends: Requires recent search volume data

## Next Steps

1. **Run ingestion** - Get real data flowing
2. **Check database** - Verify signals are stored
3. **Build more processors** - Add Glassdoor, earnings calls, etc.
4. **Add backtesting** - Correlate signals with price movements
5. **Build API** - Expose data via REST endpoints

# Signal Update System

Comprehensive documentation for backfilling and updating signals.

## Overview

The Cousin Eddie platform has two complementary update mechanisms:

1. **Historical Backfill** (`scripts/backfill_signals.py`)
   - One-time exhaustive seeding of historical data
   - Fetches maximum available history for each signal type
   - Used when first adding a company or signal type

2. **Incremental Updates** (`scripts/update_signals.py`)
   - Ongoing updates that fetch only new data since last update
   - Respects update frequencies (hourly, daily, weekly, etc.)
   - Can run as daemon for continuous updates

---

## Historical Data Backfill

### Purpose

Load all available historical data for signals to create a comprehensive baseline.

### Usage

```bash
# Backfill all signals for all companies (recommended for first setup)
python scripts/backfill_signals.py

# Backfill specific company
python scripts/backfill_signals.py --company UBER

# Backfill specific signal types
python scripts/backfill_signals.py --signals sec_financials,google_trends,twitter_sentiment

# Backfill custom date range
python scripts/backfill_signals.py --start 2020-01-01 --end 2026-02-07

# Dry run (see what would be fetched without saving)
python scripts/backfill_signals.py --dry-run

# Custom database URL
python scripts/backfill_signals.py --database-url postgresql://user:pass@host:5432/db
```

### Backfill Strategy by Signal Type

Different signal types have different historical data availability:

| Signal Type | Historical Depth | Notes |
|-------------|-----------------|-------|
| **SEC Filings** | Unlimited | All filings since company went public |
| - Form 4 (Insider Trading) | 10+ years | High-value signals |
| - 10-K/10-Q Financials | 10+ years | Quarterly data |
| - 8-K (Events) | 10+ years | Material events |
| - Risk Factors | 10+ years | From 10-K/10-Q |
| - MD&A | 10+ years | Management discussion |
| **Job Postings** | Current only | No historical API |
| **App Store Ratings** | Current only | No historical data |
| **Play Store Ratings** | Current only | No historical data |
| **Google Trends** | 5 years | API limit |
| **News Sentiment** | 1 month | NewsAPI free tier |
| **Twitter Sentiment** | 7 days | Twitter API free tier |
| **Reddit Sentiment** | Current | No historical API |
| **Glassdoor Reviews** | Current only | Sample data |
| **LinkedIn Employee Growth** | 6 months | Manual snapshots |
| **GitHub Activity** | Current only | No historical metrics |
| **Website Traffic** | Current only | SimilarWeb limitation |
| **Customer Reviews** | Current only | Platform limitations |
| **Earnings Transcripts** | Varies | Sample data |
| **Patents** | Varies | USPTO API |

### Recommended Backfill Order

For best results, backfill in this order:

1. **SEC Data First** (most historical depth)
   ```bash
   python scripts/backfill_signals.py --signals sec_form_4,sec_financials,sec_mda,sec_8k,sec_risk_factors,sec_13f --start 2020-01-01
   ```

2. **Alternative Data** (limited history)
   ```bash
   python scripts/backfill_signals.py --signals google_trends --start 2021-01-01
   ```

3. **Current Data Only** (no history available)
   ```bash
   python scripts/backfill_signals.py --signals job_postings,app_store_ratings,play_store_ratings,twitter_sentiment,reddit_sentiment
   ```

### Performance

- Backfilling all signals for one company: ~5-10 minutes
- SEC filings are the slowest (rate limits)
- Alternative data sources are fast (mostly sample data in POC)

---

## Incremental Updates

### Purpose

Continuously update signals by fetching only new data since the last update.

### Update Frequencies

Each signal processor has a defined update frequency:

| Frequency | Signal Types | Update Interval |
|-----------|-------------|-----------------|
| **Realtime** | - | Every 5 minutes |
| **Hourly** | `twitter_sentiment` | Every hour |
| **Daily** | `github_activity`, `job_postings` | Every day |
| **Weekly** | `customer_reviews`, `news_sentiment` | Every week |
| **Monthly** | `linkedin_employee_growth`, `website_traffic`, `app_store_ratings`, `play_store_ratings`, `google_trends`, `glassdoor_reviews` | Every month |
| **Quarterly** | `sec_financials`, `sec_mda`, `sec_8k`, `sec_risk_factors`, `sec_13f`, `earnings_call_transcripts` | Every quarter |

### Usage

```bash
# One-time update (updates all signals that are due)
python scripts/update_signals.py

# Update specific company
python scripts/update_signals.py --company UBER

# Update specific signal types
python scripts/update_signals.py --signals twitter_sentiment,job_postings,github_activity

# Force update (ignore last_updated, fetch new data anyway)
python scripts/update_signals.py --force

# Dry run
python scripts/update_signals.py --dry-run

# DAEMON MODE (continuous updates)
python scripts/update_signals.py --daemon

# Daemon with custom check interval (default: 300 seconds = 5 minutes)
python scripts/update_signals.py --daemon --interval 600
```

### Daemon Mode

Daemon mode runs continuously, checking for updates on schedule:

```bash
# Run as background daemon
nohup python scripts/update_signals.py --daemon > logs/updates.log 2>&1 &

# Or use screen/tmux
screen -S signal-updates
python scripts/update_signals.py --daemon
# Ctrl+A, D to detach
```

**How it works:**

1. Every `--interval` seconds (default: 300 = 5 min), check all signals
2. For each signal, calculate if update is due based on:
   - Update frequency (hourly, daily, weekly, etc.)
   - Last update timestamp from database
3. If due, fetch only new data since last update
4. Process and save new signals
5. Sleep until next check

**Example:**

- **twitter_sentiment** (hourly frequency)
  - Last update: 2026-02-07 14:00
  - Current time: 2026-02-07 15:10
  - Time since update: 70 minutes > 60 minutes
  - **→ Update triggered**

- **sec_financials** (quarterly frequency)
  - Last update: 2026-01-15
  - Current time: 2026-02-07
  - Time since update: 23 days < 90 days
  - **→ Skip (not due yet)**

---

## Production Deployment

### Recommended Setup

For production, run both systems:

1. **Initial Backfill** (one-time)
   ```bash
   # Seed all historical data
   python scripts/backfill_signals.py --company UBER
   ```

2. **Continuous Updates** (daemon)
   ```bash
   # Keep signals up-to-date
   python scripts/update_signals.py --daemon
   ```

### Using Cron (Alternative to Daemon)

Instead of daemon mode, you can use cron for scheduled updates:

```bash
# Edit crontab
crontab -e

# Add these lines:

# Update high-frequency signals every hour
0 * * * * cd /path/to/cousin-eddie && python scripts/update_signals.py --signals twitter_sentiment,github_activity

# Update daily signals at 2 AM
0 2 * * * cd /path/to/cousin-eddie && python scripts/update_signals.py --signals job_postings,news_sentiment

# Update weekly signals on Mondays at 3 AM
0 3 * * 1 cd /path/to/cousin-eddie && python scripts/update_signals.py --signals customer_reviews

# Update monthly signals on the 1st at 4 AM
0 4 1 * * cd /path/to/cousin-eddie && python scripts/update_signals.py --signals linkedin_employee_growth,website_traffic,app_store_ratings

# Update quarterly signals on first day of quarter at 5 AM
0 5 1 1,4,7,10 * cd /path/to/cousin-eddie && python scripts/update_signals.py --signals sec_financials,sec_mda,sec_8k
```

### Using Systemd (Linux)

Create a systemd service for daemon mode:

```ini
# /etc/systemd/system/cousin-eddie-updates.service

[Unit]
Description=Cousin Eddie Signal Update Daemon
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/cousin-eddie
Environment="DATABASE_URL=postgresql://user:pass@localhost:5432/cousin_eddie"
ExecStart=/usr/bin/python3 scripts/update_signals.py --daemon --interval 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable cousin-eddie-updates
sudo systemctl start cousin-eddie-updates
sudo systemctl status cousin-eddie-updates

# View logs
sudo journalctl -u cousin-eddie-updates -f
```

---

## Monitoring & Logging

### Check Update Status

Query database to see last updates:

```sql
-- Last update time for each signal type
SELECT
    signal_type,
    MAX(timestamp) as last_update,
    COUNT(*) as total_signals,
    AVG(score) as avg_score
FROM signals
WHERE company_id = 'UBER'
GROUP BY signal_type
ORDER BY last_update DESC;

-- Signals added in last 24 hours
SELECT
    signal_type,
    COUNT(*) as new_signals,
    AVG(score) as avg_score
FROM signals
WHERE company_id = 'UBER'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY signal_type;
```

### Logs

The scripts use `loguru` for structured logging:

```bash
# View daemon logs
tail -f logs/updates.log

# Search for errors
grep "ERROR" logs/updates.log

# Count signals created today
grep "Saved.*signals" logs/updates.log | grep "$(date +%Y-%m-%d)"
```

---

## Troubleshooting

### Backfill Issues

**Problem:** "No data returned for signal_type"

**Solutions:**
- Check if signal type is applicable to company
- Verify API keys are configured (for paid sources)
- Check date range (some APIs have limits)
- Run with `--dry-run` to see debug output

**Problem:** Rate limits exceeded

**Solutions:**
- Add delays between processors
- Use `--signals` to backfill one at a time
- Spread backfill over multiple days
- Get API keys with higher rate limits

### Update Issues

**Problem:** Daemon keeps updating same signal

**Solutions:**
- Check database connection (signals not saving?)
- Verify `last_updated` tracking is working
- Use `--force` flag sparingly (bypasses tracking)

**Problem:** Updates taking too long

**Solutions:**
- Reduce `--interval` check frequency
- Split high-frequency signals into separate daemon
- Use cron instead of daemon for infrequent signals

---

## Examples

### First-Time Setup

```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Backfill all historical data
python scripts/backfill_signals.py --company UBER

# 3. Start continuous updates
python scripts/update_signals.py --daemon
```

### Adding New Company

```bash
# Backfill all signals for new company
python scripts/backfill_signals.py --company LYFT
```

### Adding New Signal Type

```bash
# After registering new processor in registry.py:

# 1. Backfill historical data
python scripts/backfill_signals.py --signals new_signal_type

# 2. Updates will automatically include new type (daemon picks it up)
```

### Testing New Processor

```bash
# Dry run to test without saving to database
python scripts/backfill_signals.py --signals new_signal_type --dry-run

# Test incremental update
python scripts/update_signals.py --signals new_signal_type --dry-run --force
```

---

## API Rate Limits

Track usage to avoid hitting limits:

| Data Source | Free Tier Limit | Notes |
|-------------|-----------------|-------|
| SEC EDGAR | 10 req/sec | Use User-Agent header |
| Twitter API | 500k tweets/month | 7-day search window |
| NewsAPI | 100 req/day | 1-month history |
| GitHub API | 5000 req/hour (authed) | Higher with token |
| Yelp API | 5000 calls/day | Generous |
| Google Trends | No official limit | Rate limited |
| PatentsView | 30 req/min | Unofficial limit |

For high-frequency updates, consider:
- Caching responses
- Batching requests
- Upgrading to paid tiers
- Using alternative data providers

---

## Next Steps

1. **Set up monitoring** - Add Datadog/Prometheus metrics
2. **Add alerting** - Email/Slack when updates fail
3. **Scale horizontally** - Multiple daemon instances per signal type
4. **Add API rate limit tracking** - Auto-throttle requests
5. **Implement retry logic** - Exponential backoff on failures
6. **Add signal deduplication** - Prevent duplicate signals
7. **Build admin dashboard** - View update status, trigger manual updates

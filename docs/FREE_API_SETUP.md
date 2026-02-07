# Free API Setup Guide

This document lists all FREE data sources and APIs for the cousin-eddie platform.

## ✅ Already Working (No API Key Needed)

These processors are fully implemented and working:

1. **SEC EDGAR** - All SEC filings (Form 4, 10-K, 10-Q, 8-K, etc.)
   - Source: https://www.sec.gov/edgar
   - Limits: 10 requests/second
   - Status: ✅ Working
   - No signup needed

2. **Google Trends** - Search interest over time
   - Source: pytrends library (unofficial API)
   - Limits: Rate limited but generous
   - Status: ✅ Working
   - No signup needed

3. **App Store Ratings** - iOS app ratings and reviews
   - Source: Apple iTunes API
   - Limits: None (public data)
   - Status: ✅ Working
   - No signup needed

4. **Reddit Sentiment** - Subreddit mentions and sentiment
   - Source: Reddit API
   - Limits: 60 requests/minute (no auth)
   - Status: ✅ Working
   - No signup needed

5. **GitHub Activity** - Repository stars, commits, issues
   - Source: GitHub API
   - Limits: 60 requests/hour (no auth), 5000/hour (with auth)
   - Status: ✅ Working
   - Optional: Get token at https://github.com/settings/tokens

6. **Wikipedia Pageviews** - Article view counts
   - Source: Wikimedia Pageviews API
   - Limits: 5000 requests/hour
   - Status: ✅ Working
   - No signup needed

7. **LinkedIn Employee Growth** - Company headcount tracking
   - Source: LinkedIn public company pages (scraping)
   - Limits: Scraping-based
   - Status: ✅ Working
   - No signup needed

8. **Job Postings** - Indeed, LinkedIn job listings
   - Source: Web scraping
   - Limits: Scraping-based
   - Status: ✅ Working
   - No signup needed

9. **Patent Filings** - USPTO patents
   - Source: USPTO API
   - Limits: None
   - Status: ✅ Working
   - No signup needed

10. **Social Media Followers** - Twitter, Instagram follower counts
    - Source: Public pages (scraping)
    - Limits: Scraping-based
    - Status: ✅ Working
    - No signup needed

11. **Pricing Intelligence** - Product pricing tracking
    - Source: Web scraping
    - Limits: Scraping-based
    - Status: ✅ Working
    - No signup needed

---

## 🆓 Free APIs to Set Up

These require free API keys but have generous limits:

### 1. **Twitter/X API v2** (Essential Plan)
- **What**: Twitter mentions and sentiment
- **Signup**: https://developer.twitter.com/en/portal/dashboard
- **Free Tier**:
  - 1,500 tweets/month (search)
  - 50,000 tweets/month (read)
  - 7-day search history
- **Setup**:
  1. Create Twitter Developer Account
  2. Create a "Project" and "App"
  3. Get your "Bearer Token"
  4. Set env var: `export TWITTER_BEARER_TOKEN="your_token"`
- **Priority**: HIGH (real-time sentiment is valuable)

### 2. **News API**
- **What**: News articles and headlines
- **Signup**: https://newsapi.org/register
- **Free Tier**:
  - 100 requests/day
  - 1,000 requests/month
  - Articles up to 1 month old
- **Setup**:
  1. Sign up (just email, no credit card)
  2. Get your API key
  3. Set env var: `export NEWS_API_KEY="your_key"`
- **Priority**: HIGH (news sentiment is important)

### 3. **YouTube Data API v3**
- **What**: Channel stats, video metrics
- **Signup**: https://console.cloud.google.com/
- **Free Tier**:
  - 10,000 quota units/day
  - ~100 requests/day for basic stats
- **Setup**:
  1. Go to Google Cloud Console
  2. Create a project
  3. Enable "YouTube Data API v3"
  4. Create credentials (API Key)
  5. Set env var: `export YOUTUBE_API_KEY="your_key"`
- **Priority**: MEDIUM

### 4. **Alpha Vantage** (For Earnings Transcripts)
- **What**: Stock data, earnings call transcripts (limited)
- **Signup**: https://www.alphavantage.co/support/#api-key
- **Free Tier**:
  - 25 requests/day
  - 500 requests/month
- **Setup**:
  1. Sign up (just email)
  2. Get API key
  3. Set env var: `export ALPHA_VANTAGE_API_KEY="your_key"`
- **Priority**: MEDIUM
- **Note**: Limited transcript access, may need alternative source

### 5. **StackExchange API** (For StackOverflow)
- **What**: StackOverflow questions, tags, activity
- **Signup**: https://api.stackexchange.com/
- **Free Tier**:
  - 10,000 requests/day (with key)
  - 300 requests/day (without key)
- **Setup**:
  1. Register app at https://stackapps.com/apps/oauth/register
  2. Get API key
  3. Set env var: `export STACKEXCHANGE_API_KEY="your_key"`
- **Priority**: LOW

### 6. **ClinicalTrials.gov API**
- **What**: Clinical trial data for pharma/biotech
- **Signup**: Not needed! Public API
- **Free Tier**: Unlimited
- **Setup**: None needed, just implement
- **Priority**: MEDIUM (only for pharma companies)

### 7. **NIH RePORTER API** (For Academic Research)
- **What**: Federal research grants
- **Signup**: Not needed! Public API
- **Free Tier**: Unlimited
- **Setup**: None needed, just implement
- **API**: https://api.reporter.nih.gov/
- **Priority**: LOW

### 8. **Archive.org Wayback Machine API** (For Website Changes)
- **What**: Historical website snapshots
- **Signup**: Not needed! Public API
- **Free Tier**: Generous
- **Setup**: None needed, just implement
- **API**: https://archive.org/help/wayback_api.php
- **Priority**: MEDIUM

---

## 🔄 Scraping-Based (Free but Need Implementation)

These don't have APIs but can be scraped:

### 9. **Play Store Ratings**
- **What**: Android app ratings/reviews
- **Method**: Scrape Google Play Store pages or use google-play-scraper library
- **Library**: `pip install google-play-scraper`
- **Priority**: HIGH (complement to App Store)

### 10. **Glassdoor Reviews**
- **What**: Employee reviews and ratings
- **Method**: Web scraping (careful with rate limits)
- **Note**: Glassdoor actively blocks scrapers, may need headless browser
- **Priority**: MEDIUM

### 11. **Yelp Reviews**
- **What**: Customer reviews for retail/restaurants
- **Method**: Yelp Fusion API (requires signup but free)
- **Signup**: https://www.yelp.com/developers
- **Free Tier**: 500 calls/day
- **Priority**: MEDIUM

### 12. **Similarweb** (Website Traffic)
- **What**: Website traffic estimates
- **Method**: No free API - would need paid plan ($200/month+)
- **Alternative**: Use public Alexa rank (discontinued) or Tranco list
- **Priority**: LOW (expensive)

---

## 📊 Recommended Setup Priority

### Week 1 - High Priority (Essential for POC):
1. ✅ Twitter API - Real-time sentiment
2. ✅ News API - News sentiment
3. ✅ Play Store Scraper - App ratings
4. ✅ Archive.org API - Website changes

### Week 2 - Medium Priority:
5. YouTube API - Video content tracking
6. ClinicalTrials.gov - Pharma signals
7. Alpha Vantage - Earnings transcripts

### Week 3 - Nice to Have:
8. StackExchange API - Developer sentiment
9. NIH RePORTER - Research grants
10. Yelp API - Customer reviews

---

## 🚀 Quick Start Commands

Once you have the API keys:

```bash
# Set up environment variables
export TWITTER_BEARER_TOKEN="your_twitter_token"
export NEWS_API_KEY="your_news_api_key"
export YOUTUBE_API_KEY="your_youtube_key"
export ALPHA_VANTAGE_API_KEY="your_alphavantage_key"
export STACKEXCHANGE_API_KEY="your_stackexchange_key"

# Or add to .env file
cat > .env << EOF
TWITTER_BEARER_TOKEN=your_twitter_token
NEWS_API_KEY=your_news_api_key
YOUTUBE_API_KEY=your_youtube_key
ALPHA_VANTAGE_API_KEY=your_alphavantage_key
STACKEXCHANGE_API_KEY=your_stackexchange_key
EOF

# Run backfill with real APIs
python scripts/backfill_signals.py --company UBER

# Start continuous updates
python scripts/update_signals.py --daemon
```

---

## 💰 Cost Summary

**Total Monthly Cost: $0**

All APIs listed are completely free with the usage limits shown. For production at scale, you may eventually need:
- Twitter API Pro ($100/month) for more volume
- News API paid tier ($449/month) for unlimited
- Premium data providers for: foot traffic (SafeGraph), satellite imagery (Planet), credit card transactions

But for POC and initial trading strategy, **all free tiers are sufficient**.

---

## 📝 Implementation Status

| Signal Type | API/Source | Status | Setup Required |
|------------|------------|--------|----------------|
| SEC Filings | SEC EDGAR | ✅ Working | None |
| Google Trends | pytrends | ✅ Working | None |
| Twitter | Twitter API v2 | 🔑 Need Key | Register at developer.twitter.com |
| News | News API | 🔑 Need Key | Register at newsapi.org |
| YouTube | YouTube API v3 | 🔑 Need Key | Google Cloud Console |
| Play Store | google-play-scraper | 📝 Need Implementation | pip install only |
| Archive.org | Wayback Machine | 📝 Need Implementation | None |
| ClinicalTrials | NIH API | 📝 Need Implementation | None |
| Stack Overflow | StackExchange API | 🔑 Optional Key | stackapps.com |

**Next Steps**: Get Twitter and News API keys first (highest priority), then I'll implement the integrations.

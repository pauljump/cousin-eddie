# Signal Processor Inventory

**Last Updated:** 2026-02-07

## Currently Implemented (6 Active + 1 Built but Not Registered)

### ✅ REGULATORY (3 active + 1 inactive)
1. **SEC Form 4** (Insider Trading) - ✅ ACTIVE
   - Status: Working, ingesting real data
   - Confidence: 0.80
   - Updates: Real-time (filed within 2 days of transaction)

2. **SEC Financials** (10-K/10-Q Financial Statements) - ✅ ACTIVE
   - Status: Working, 95 historical signals for Uber
   - Confidence: 0.95
   - Updates: Quarterly
   - Extracts: Revenue, margins, cash flow, balance sheet
   - Source: SEC Company Facts API (XBRL)

3. **SEC MD&A** (Management Discussion & Analysis) - ⚠️ BUILT BUT NOT REGISTERED
   - Status: Code complete, not in registry
   - Confidence: 0.75
   - Updates: Quarterly (with 10-K/10-Q)
   - Extracts: Sentiment, topics, forward guidance
   - **TODO:** Add to registry.py

4. **SEC Form 4 XML Enhancement** - ✅ ACTIVE
   - Full XML parsing with insider roles
   - Transaction type detection
   - Filtering tax withholdings and awards

### ✅ WEB/DIGITAL (2)
5. **App Store Ratings** - ✅ ACTIVE
   - Status: Working, real data
   - Confidence: 0.80
   - Updates: Daily
   - Coverage: iOS App Store
   - Extracts: Rating, review count, version

6. **Google Trends** - ✅ ACTIVE
   - Status: Working, real data
   - Confidence: 0.65
   - Updates: Daily
   - Tracks: Brand keywords, product keywords, category terms

### ✅ ALTERNATIVE (1)
7. **Reddit Sentiment** - ✅ ACTIVE
   - Status: Working, real data
   - Confidence: 0.60
   - Updates: Daily
   - Source: Reddit API (PRAW)
   - Extracts: Mentions, sentiment, engagement

### ✅ WORKFORCE (1)
8. **Job Postings** - ✅ ACTIVE (with Greenhouse API)
   - Status: Working for Greenhouse companies (Lyft = 152 jobs)
   - Confidence: 0.85 (Greenhouse) / 0.60 (scraped)
   - Updates: Daily
   - Source: Greenhouse API (primary), career pages (fallback)
   - **Issue:** Uber doesn't use Greenhouse, scraping blocked
   - Extracts: Job count, categories, locations

---

## Planned - High Priority (EDGAR Coverage)

### 🔴 REGULATORY - Missing Critical Filings

9. **Risk Factors Extractor** - NOT STARTED
   - Priority: HIGH
   - Extract risk disclosures from 10-K/10-Q
   - Track changes (new risks, removed risks, severity)
   - Sentiment analysis on risk language

10. **8-K Processor** (Material Events) - NOT STARTED
    - Priority: HIGH
    - Real-time material event detection
    - Key items:
      - Item 2.02: Earnings announcements
      - Item 5.02: Executive changes (CEO/CFO departures)
      - Item 1.01: M&A activity
      - Item 8.01: Other material events
    - Updates: Real-time (filed within 4 days)

11. **13F Processor** (Institutional Holdings) - NOT STARTED
    - Priority: HIGH
    - Smart money tracking
    - Position changes by major funds
    - New positions, exits, increases, decreases
    - Updates: Quarterly (45 days after quarter end)

12. **DEF 14A** (Proxy Statements) - NOT STARTED
    - Priority: MEDIUM
    - Executive compensation changes
    - Board composition
    - Shareholder proposals
    - Updates: Annual

13. **13D/13G** (>5% Ownership) - NOT STARTED
    - Priority: MEDIUM
    - Activist investors
    - Strategic buyers
    - Updates: Event-driven

14. **S-1/S-3/424B** (Capital Raises) - NOT STARTED
    - Priority: LOW
    - Dilution risk
    - Why do they need capital?
    - Updates: Event-driven

---

## Planned - Alternative Signals

### 🟡 WEB/DIGITAL - Expanded Coverage

15. **Twitter/X Sentiment** - NOT STARTED
    - Priority: MEDIUM
    - Brand mentions, sentiment
    - Influencer activity
    - Viral events

16. **News Sentiment** - NOT STARTED
    - Priority: HIGH
    - Major news sources (Reuters, Bloomberg, WSJ)
    - Sentiment analysis
    - Topic extraction
    - **Potential sources:** NewsAPI, GDELT, Common Crawl

17. **Web Traffic** - NOT STARTED
    - Priority: MEDIUM
    - SimilarWeb API (paid)
    - Alexa (deprecated)
    - Cloudflare Radar (limited)

18. **YouTube Activity** - NOT STARTED
    - Priority: LOW
    - Channel growth
    - Video performance
    - Sentiment in comments

19. **TikTok Mentions** - NOT STARTED
    - Priority: LOW (but growing importance)
    - Brand mentions
    - Viral trends

### 🟡 PRODUCT/CUSTOMER

20. **Play Store Ratings** (Android) - NOT STARTED
    - Priority: MEDIUM
    - Complement iOS App Store data
    - Google Play API

21. **Trustpilot/Yelp Reviews** - NOT STARTED
    - Priority: MEDIUM
    - Service quality sentiment
    - Complaint tracking

22. **Customer Support Metrics** - NOT STARTED
    - Priority: LOW
    - Response times
    - Resolution rates
    - **Hard to get:** Not publicly available for most companies

### 🟡 COMPETITIVE

23. **Competitor Analysis** - NOT STARTED
    - Priority: MEDIUM
    - Relative performance
    - Market share shifts
    - **Challenge:** Need competitor data pipelines first

24. **Market Share Data** - NOT STARTED
    - Priority: MEDIUM
    - Industry reports
    - Third-party estimates

### 🟡 OPERATIONAL

25. **Website Changes** - NOT STARTED
    - Priority: LOW
    - Product launches (new pages)
    - Pricing changes
    - Feature additions
    - **Method:** Archive.org API, custom scraping

26. **GitHub Activity** (for tech companies) - NOT STARTED
    - Priority: LOW
    - Open source contributions
    - Developer hiring signals
    - Technology adoption

27. **Patent Filings** - NOT STARTED
    - Priority: LOW
    - Innovation signals
    - USPTO database

### 🟡 GEOSPATIAL (for companies with physical presence)

28. **Foot Traffic** - NOT STARTED
    - Priority: MEDIUM (for retail/restaurant companies)
    - SafeGraph (paid)
    - Placer.ai (paid)
    - **Not applicable to Uber/Lyft POC**

29. **Store Openings/Closures** - NOT STARTED
    - Priority: LOW
    - Expansion/contraction signals
    - **Method:** Scrape store locators

### 🟡 FINANCIAL MARKETS

30. **Options Flow** - NOT STARTED
    - Priority: LOW
    - Unusual options activity
    - Put/call ratio
    - **Source:** Paid data providers

31. **Short Interest** - NOT STARTED
    - Priority: MEDIUM
    - Borrowing costs
    - Days to cover
    - **Source:** FINRA, exchanges

32. **Analyst Ratings** - NOT STARTED
    - Priority: MEDIUM
    - Upgrades/downgrades
    - Price target changes
    - **Source:** Scrape financial sites

---

## Signal Synthesis (Built)

### ✅ SYNTHESIS LAYER
33. **Correlation Engine** - ✅ COMPLETE
    - Discovers lead-lag relationships
    - Statistical significance testing
    - Leading indicator identification

34. **LLM Thesis Generator** - ✅ COMPLETE
    - OpenAI GPT-4 integration
    - Synthesizes all signals into investment thesis
    - Structured output: verdict, conviction, bull/bear case

35. **Signal Analysis Tool** - ✅ COMPLETE
    - Works without API
    - Category aggregation
    - Validation/contradiction detection
    - Weighted scoring

---

## Summary

**Total Processors:**
- ✅ Active: 6
- ⚠️ Built but inactive: 1 (MD&A)
- 🔴 High priority missing: 3 (Risk Factors, 8-K, 13F)
- 🟡 Planned: 25+

**EDGAR Coverage:**
- ✅ Complete: Form 4, 10-K/10-Q financials, MD&A (inactive)
- 🔴 Missing Critical: Risk Factors, 8-K, 13F, DEF 14A, 13D/13G

**Alternative Coverage:**
- ✅ Good: App ratings, Google Trends, Reddit, Job postings
- 🟡 Needs: News sentiment, Twitter, web traffic, competitor data

**Data Quality Issues:**
- Job Postings: Works for Greenhouse companies, fails for Uber (HTTP 406)
- Need Uber-specific job scraping solution or alternative source

---

## Immediate Next Steps

1. **Register MD&A Processor** - 5 minutes
2. **Build Risk Factors Extractor** - 2-3 hours
3. **Build 8-K Processor** - 3-4 hours
4. **Build 13F Processor** - 2-3 hours
5. **Add News Sentiment** - 4-6 hours (if using NewsAPI)
6. **Fix Uber Job Postings** - 2-3 hours (find alternative source)

**After that:** Platform will have solid EDGAR coverage + decent alternative signal mix.

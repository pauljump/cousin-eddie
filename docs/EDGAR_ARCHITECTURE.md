# EDGAR Data Architecture

## Philosophy

EDGAR filings are **ground truth** - legally required disclosures by public companies.
All alternative signals (app ratings, Reddit, etc.) are **supplementary** - they help answer questions between quarterly reports and validate/contradict company disclosures.

**Hierarchy:**
1. **EDGAR filings** = THE TRUTH (what company legally discloses)
2. **Alternative signals** = LEADING/REAL-TIME indicators (what's happening now)
3. **Synthesis** = Connecting truth to real-time signals

---

## Critical EDGAR Filings

### Tier 1: Financial Statements (Quarterly/Annual)
- **10-K**: Annual report (full audited financials)
- **10-Q**: Quarterly report (unaudited financials)

**Extract:**
- Income statement (revenue, expenses, net income, EPS)
- Balance sheet (assets, liabilities, equity, debt)
- Cash flow statement (operating, investing, financing activities)
- Key metrics (margins, growth rates, efficiency ratios)
- Segment data (geographic, product-line breakdown)

### Tier 2: Narrative Sections (10-K/10-Q)
- **MD&A** (Management Discussion & Analysis)
  - Business trends
  - Forward-looking statements
  - Risks and uncertainties
  - Sentiment analysis (optimistic vs defensive language)
  - Topic extraction (what are they talking about?)

- **Risk Factors**
  - List of disclosed risks
  - Track changes (new risks, removed risks, severity changes)
  - Risk categorization (regulatory, competitive, operational, financial)
  - Risk sentiment (is language more/less severe?)

### Tier 3: Material Events
- **8-K**: Current reports (filed within 4 days of material events)
  - Item 1.01: Business combinations
  - Item 2.02: Earnings announcements
  - Item 5.02: Executive changes (CEO, CFO departures)
  - Item 8.01: Other material events
  - And 6 other item types

### Tier 4: Ownership & Governance
- **13F**: Institutional holdings (quarterly)
  - Who owns the stock (Vanguard, BlackRock, hedge funds)
  - Position changes (buying, selling, new positions)
  - Smart money tracking

- **DEF 14A**: Proxy statements (annual)
  - Executive compensation
  - Board composition
  - Shareholder proposals
  - Say-on-pay votes

- **Form 3/4/5**: Insider transactions
  - Already built (Form 4 done)
  - Need Form 3 (initial ownership) and Form 5 (annual summary)

- **13D/13G**: Large shareholder positions (>5%)
  - Activist investors
  - Strategic buyers
  - Major ownership changes

### Tier 5: Capital Markets Activity
- **S-1/S-3**: New offerings (IPOs, secondary offerings)
  - Dilution risk
  - Capital raises (why do they need money?)

- **424B**: Prospectus supplements
  - Debt offerings
  - Convertible notes

---

## Data Models

### 1. Structured Financial Data

```python
class FinancialStatement(BaseModel):
    """Income Statement, Balance Sheet, Cash Flow"""
    company_id: str
    filing_type: str  # "10-K", "10-Q"
    period_end: date
    fiscal_year: int
    fiscal_quarter: Optional[int]  # Q1, Q2, Q3, Q4 (None for 10-K)

    # Raw XBRL/financial data
    line_items: Dict[str, float]  # {"Revenues": 31500000000, ...}

    # Parsed structured data
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow: CashFlowStatement

    # Metadata
    accession_number: str
    filing_date: date
    period_type: str  # "annual", "quarterly"

class IncomeStatement(BaseModel):
    revenue: float
    cost_of_revenue: float
    gross_profit: float
    operating_expenses: float
    operating_income: float
    net_income: float
    eps_basic: float
    eps_diluted: float
    shares_outstanding: float

    # Calculated metrics
    gross_margin: float
    operating_margin: float
    net_margin: float
    yoy_revenue_growth: Optional[float]
    qoq_revenue_growth: Optional[float]

class BalanceSheet(BaseModel):
    total_assets: float
    total_liabilities: float
    total_equity: float
    cash_and_equivalents: float
    total_debt: float
    current_ratio: float
    debt_to_equity: float

class CashFlowStatement(BaseModel):
    operating_cash_flow: float
    investing_cash_flow: float
    financing_cash_flow: float
    free_cash_flow: float
    capex: float
```

### 2. Textual Data

```python
class MDAnalysis(BaseModel):
    """MD&A section from 10-K/10-Q"""
    company_id: str
    filing_type: str
    period_end: date

    # Raw text
    full_text: str

    # Parsed sections
    sections: Dict[str, str]  # {"Results of Operations": "...", ...}

    # Analysis
    sentiment_score: float  # -1 to +1 (pessimistic to optimistic)
    forward_looking_statements: List[str]
    topics: List[str]  # ["regulatory challenges", "market expansion", ...]

    # Change detection
    new_topics: List[str]  # Topics mentioned this quarter but not last
    removed_topics: List[str]
    sentiment_change: float  # Change from prior period

class RiskFactors(BaseModel):
    """Risk Factors section from 10-K/10-Q"""
    company_id: str
    filing_type: str
    period_end: date

    # Individual risks
    risks: List[Risk]

    # Analysis
    total_risk_count: int
    new_risks: List[Risk]
    removed_risks: List[Risk]
    severity_changes: List[RiskSeverityChange]

class Risk(BaseModel):
    risk_id: str  # Hash of risk text for tracking
    category: str  # "regulatory", "competitive", "operational", etc.
    title: str
    description: str
    severity_score: float  # Estimated severity
    first_disclosed: date
    last_disclosed: date
```

### 3. Material Events

```python
class MaterialEvent(BaseModel):
    """8-K filing - material event"""
    company_id: str
    filing_date: date
    event_date: date

    item_numbers: List[str]  # ["1.01", "5.02"]
    event_types: List[str]  # ["Business Combination", "Executive Change"]

    description: str
    full_text: str

    # Classification
    is_positive: Optional[bool]  # Is this good or bad news?
    materiality_score: float  # How important is this?
```

### 4. Institutional Holdings

```python
class InstitutionalHoldings(BaseModel):
    """13F filing - institutional investor positions"""
    filing_date: date
    period_end: date
    institution_name: str
    institution_cik: str

    positions: List[Position]

class Position(BaseModel):
    company_id: str
    shares: int
    market_value: float

    # Change from prior quarter
    shares_change: int
    shares_change_pct: float
    is_new_position: bool
    is_sold_out: bool
```

---

## Data Storage Strategy

### Option 1: Separate Tables per Filing Type
```sql
-- Financial statements
CREATE TABLE financial_statements (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(10),
    filing_type VARCHAR(10),
    period_end DATE,
    fiscal_year INT,
    fiscal_quarter INT,
    data JSONB,  -- All financial data
    metrics JSONB,  -- Calculated ratios
    accession_number VARCHAR(50),
    filing_date DATE
);

-- Text sections
CREATE TABLE mda_sections (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(10),
    period_end DATE,
    full_text TEXT,
    sentiment_score FLOAT,
    topics JSONB,
    analysis JSONB
);

CREATE TABLE risk_factors (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(10),
    period_end DATE,
    risks JSONB,
    new_risks JSONB,
    removed_risks JSONB
);

-- Events
CREATE TABLE material_events (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(10),
    event_date DATE,
    filing_date DATE,
    item_numbers JSONB,
    description TEXT,
    materiality_score FLOAT
);
```

### Option 2: EDGAR Signals (Normalized into Signal Schema)

Convert EDGAR data into **signals** that fit our existing schema:

```python
# Examples of EDGAR-derived signals:
signals = [
    Signal(
        signal_type="revenue_growth_qoq",
        score=75,  # +15% QoQ growth = bullish
        raw_value={"current_q": 31.5B, "prior_q": 27.4B, "growth": 0.15},
    ),
    Signal(
        signal_type="mda_sentiment",
        score=30,  # Mildly optimistic MD&A
        raw_value={"sentiment": 0.3, "topics": ["expansion", "efficiency"]},
    ),
    Signal(
        signal_type="new_risk_factor",
        score=-40,  # New regulatory risk is bearish
        raw_value={"risk": "Regulatory investigation in EU market"},
    ),
    Signal(
        signal_type="institutional_buying",
        score=60,  # Vanguard increased position 12%
        raw_value={"institution": "Vanguard", "change_pct": 0.12},
    ),
]
```

**Recommendation: Use Option 2** - normalize everything into signals. This keeps the architecture consistent and makes synthesis easier.

---

## Signal Generation from EDGAR

### From 10-Q/10-K Financials:
- **Revenue growth** (QoQ, YoY) → score based on acceleration
- **Margin expansion** → score based on operating leverage
- **Cash flow generation** → score based on FCF yield
- **Balance sheet health** → score based on debt/equity, current ratio
- **EPS surprise** → score based on beat/miss

### From MD&A:
- **Sentiment shift** → score based on optimism vs defensiveness
- **New topics** → score based on positive (expansion) vs negative (challenges)
- **Forward guidance** → score based on raised vs lowered expectations

### From Risk Factors:
- **New risks** → negative score (new uncertainty)
- **Removed risks** → positive score (risk reduced)
- **Severity increase** → negative score (existing risk worsening)

### From 8-K:
- **Executive departure** (CEO/CFO) → negative score
- **Earnings guidance** → score based on direction
- **M&A announcement** → score based on strategic fit

### From 13F:
- **Smart money buying** → positive score (institutions adding)
- **Smart money selling** → negative score (institutions reducing)
- **New hedge fund positions** → positive score (activist interest)

---

## Implementation Plan

### Phase 1: Core Financials (Week 1)
1. Build `SECFinancialsProcessor` for 10-K/10-Q
2. Use SEC EDGAR API to fetch filing URLs
3. Parse XBRL/HTML financial statements
4. Extract income statement, balance sheet, cash flow
5. Calculate key metrics and growth rates
6. Generate signals: revenue_growth, margin_expansion, fcf_yield, etc.

### Phase 2: Text Analysis (Week 2)
1. Build `SECTextAnalysisProcessor` for MD&A and Risk Factors
2. Extract text sections using regex/BeautifulSoup
3. Sentiment analysis (basic NLP or LLM-based)
4. Topic extraction (LDA or LLM-based)
5. Change detection (compare to prior quarter)
6. Generate signals: mda_sentiment, new_risks, risk_severity, etc.

### Phase 3: Material Events (Week 3)
1. Build `SEC8KProcessor` for current reports
2. Parse 8-K item numbers and descriptions
3. Classify events (positive, negative, neutral)
4. Generate signals: exec_departure, guidance_change, m&a_activity, etc.

### Phase 4: Ownership Data (Week 4)
1. Build `SEC13FProcessor` for institutional holdings
2. Track quarterly position changes
3. Identify smart money flows
4. Generate signals: institutional_buying, hedge_fund_activity, etc.

---

## Signal Synthesis Examples

Once we have EDGAR signals, we can connect them to alternative signals:

### Example 1: Revenue Growth Validation
```
EDGAR Signal: Revenue growth +15% QoQ (10-Q)
Alternative Signals:
  - App ratings: 4.90/5 (stable)
  - Reddit sentiment: +30 (bullish)
  - Google Trends: Stable search volume

SYNTHESIS: Revenue growth is VALIDATED by strong product satisfaction
and positive social sentiment. Growth appears organic and sustainable.
```

### Example 2: Risk Factor Warning
```
EDGAR Signal: New risk factor added "Increased competition in core markets"
Alternative Signals:
  - Reddit sentiment: Declining from +30 to +7
  - Job postings: Down 40% (slowing hiring)
  - Insider selling: CLO sold $260k

SYNTHESIS: New competitive risk is CONFIRMED by weakening alternative
signals. Management may be concerned about market share loss.
```

### Example 3: Institutional Confidence
```
EDGAR Signal: Vanguard increased position 12% (13F)
EDGAR Signal: CEO bought $2M shares (Form 4)
Alternative Signals:
  - App ratings: 4.90/5
  - Google Trends: +20% search growth

SYNTHESIS: Smart money (institutions + insiders) are BUYING while
product metrics remain strong. High conviction bullish signal.
```

---

## Success Metrics

We'll know EDGAR integration is successful when:
1. ✅ All major filing types are ingested (10-K, 10-Q, 8-K, 13F)
2. ✅ Financial data is parsed into structured format
3. ✅ Text sections are analyzed for sentiment and topics
4. ✅ Changes over time are automatically tracked
5. ✅ EDGAR signals connect logically to alternative signals
6. ✅ Synthesis produces actionable investment thesis

---

## Next: Start Building

I'll begin with **Phase 1: Core Financials (10-K/10-Q)** since this is the foundation.

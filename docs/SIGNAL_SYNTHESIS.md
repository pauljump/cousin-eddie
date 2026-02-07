# Signal Synthesis Framework

## The Core Problem

With 100+ signals (and growing to hundreds), we can't just sum scores. We need intelligent synthesis that:

1. **Validates**: Do alternative signals confirm EDGAR truth?
2. **Detects Contradictions**: When signals disagree, which to trust?
3. **Discovers Causality**: Does signal A predict signal B?
4. **Generates Insights**: Turn data → actionable investment thesis

---

## Multi-Layer Synthesis Architecture

### Layer 1: EDGAR Ground Truth (Foundation)

**What It Tells Us:**
- Financial performance (revenue, margins, cash flow)
- Legal risks and uncertainties (from filings)
- Management sentiment (from MD&A)
- Ownership changes (institutional, insiders)

**Example (Uber Q3 2025):**
```
Ground Truth:
- Revenue: $13.5B (+6.5% QoQ) → Score: +50
- Net Margin: 49.2% → Score: +85
- OCF Margin: 53.6% → Score: +80
- Insider Activity: CLO sold $260k → Score: -16

EDGAR Aggregate: +199 / 4 signals = +50 avg (Strong Fundamentals)
```

### Layer 2: Alternative Signal Validation

**Connect Alternative → EDGAR:**

| Alternative Signal | EDGAR Validation | Synthesis |
|-------------------|------------------|-----------|
| App Rating 4.90/5 (+80) | Net Margin 49% (+85) | ✅ **CONFIRMED**: Product quality translating to profitability |
| Reddit Sentiment +30 | Revenue Growth +6.5% (+50) | ✅ **CONFIRMED**: Positive buzz matches real growth |
| Google Trends Stable (0) | Revenue Growth +6.5% (+50) | ⚠️ **WATCH**: Growth without search volume increase = existing user monetization |
| Job Postings -20 | OCF Margin 54% (+80) | ✅ **VALIDATED**: Not hiring = operating leverage / efficiency |
| Insider Sell -16 | Strong Financials +85 | ✅ **NEUTRAL**: Likely tax planning, not concern given fundamentals |

**Synthesis Logic:**
```python
if alternative_signal.positive and edgar_financials.positive:
    confidence = "HIGH"  # Mutually reinforcing
    interpretation = "Alternative metrics validate strong fundamentals"

elif alternative_signal.positive and edgar_financials.negative:
    confidence = "LOW"  # Contradiction
    alert = "INVESTIGATE: Why is product improving but financials declining?"

elif alternative_signal.negative and edgar_financials.positive:
    interpretation = "Fundamentals strong despite sentiment weakness = opportunity"
```

### Layer 3: Time-Series Correlation Analysis

**Track Signal Relationships Over Time:**

```python
# Example: Does Reddit sentiment PREDICT revenue growth?
correlation_analysis = {
    'reddit_sentiment': {
        'leads_revenue_growth': {
            'lag': 1,  # Reddit leads by 1 quarter
            'correlation': 0.72,  # Strong correlation
            'p_value': 0.003,  # Statistically significant
        },
        'interpretation': "Rising Reddit sentiment predicts +1Q revenue acceleration"
    },

    'app_ratings': {
        'leads_churn': {
            'lag': 0,  # Contemporaneous
            'correlation': -0.85,  # Declining ratings = rising churn
            'p_value': 0.001,
        },
        'interpretation': "App rating decline is EARLY WARNING of user loss"
    },

    'insider_buying': {
        'leads_earnings_beat': {
            'lag': 1,  # Insiders buy before good quarter
            'correlation': 0.65,
            'p_value': 0.01,
        },
        'interpretation': "Insider buying forecasts earnings beats"
    }
}
```

**Use Cases:**
1. **Leading Indicators**: If Reddit sentiment spiking → expect revenue growth next quarter
2. **Early Warnings**: If app ratings declining → expect churn increase
3. **Confirmation Signals**: If insiders buying AND app ratings improving → high conviction

### Layer 4: Contradiction Detection & Resolution

**When Signals Conflict:**

```python
class SignalContradiction:
    def __init__(self, signal_a, signal_b):
        self.signal_a = signal_a  # e.g., "Revenue Declining"
        self.signal_b = signal_b  # e.g., "App Ratings Improving"
        self.severity = self._calculate_severity()

    def _calculate_severity(self):
        # EDGAR truth contradicts alternative = HIGH severity
        if signal_a.category == "REGULATORY" and signal_a.score < 0:
            if signal_b.category == "ALTERNATIVE" and signal_b.score > 0:
                return "HIGH"  # Fundamentals bad, sentiment good = WARNING

        return "MEDIUM"

    def resolve(self):
        """
        Resolution priority:
        1. EDGAR > Alternative (ground truth wins)
        2. Recent > Old (newer data preferred)
        3. High confidence > Low confidence
        """
        if self.signal_a.category == "REGULATORY":
            return {
                'winner': self.signal_a,
                'interpretation': f"""
                EDGAR shows {self.signal_a.description}.
                Alternative signal ({self.signal_b.description}) contradicts.

                LIKELY CAUSE: Lagging alternative data OR market inefficiency.
                ACTION: Trust EDGAR, monitor if alternative catches up.
                """
            }
```

**Example Contradiction:**
```
Signal A (EDGAR): Revenue declining -5% QoQ (Score: -20)
Signal B (Reddit): Bullish sentiment +40 (Score: +40)

RESOLUTION:
- Trust EDGAR (ground truth)
- Interpretation: "Retail investors bullish but fundamentals weakening"
- Action: SHORT opportunity - sentiment will catch down to reality
```

### Layer 5: Causal Graph & Bayesian Updates

**Model Causal Relationships:**

```
                    ┌─────────────────┐
                    │  Product Quality│
                    │ (App Ratings)   │
                    └────────┬────────┘
                             │ causes
                             ↓
              ┌──────────────────────────┐
              │   User Satisfaction      │
              │ (Reddit Sentiment)       │
              └──────────┬───────────────┘
                         │ causes
                         ↓
         ┌───────────────────────────────┐
         │    Revenue Growth             │
         │  (EDGAR 10-Q)                 │
         └──────────┬────────────────────┘
                    │ causes
                    ↓
      ┌─────────────────────────────────┐
      │      Profitability               │
      │   (EDGAR Net Margin)             │
      └─────────────┬───────────────────┘
                    │ attracts
                    ↓
        ┌───────────────────────────────┐
        │   Institutional Buying        │
        │   (13F Holdings)              │
        └───────────────────────────────┘
```

**Bayesian Belief Updates:**

```python
# Prior belief about Uber bullishness
prior = 0.50  # Neutral

# Update based on incoming signals
def bayesian_update(prior, signal, evidence_strength):
    """
    Update belief based on new signal evidence.

    Args:
        prior: Current belief (0-1)
        signal: New signal data
        evidence_strength: How reliable is this signal type?
    """
    if signal.category == "REGULATORY":  # EDGAR = high strength
        evidence_strength = 0.95
    elif signal.category == "ALTERNATIVE":  # Lower strength
        evidence_strength = 0.60

    # Bayes rule (simplified)
    likelihood = (signal.score + 100) / 200  # Normalize to 0-1
    posterior = (likelihood * evidence_strength * prior) / (
        (likelihood * evidence_strength * prior) +
        ((1 - likelihood) * (1 - evidence_strength) * (1 - prior))
    )

    return posterior

# Process signals sequentially
belief = prior
belief = bayesian_update(belief, edgar_revenue_growth, 0.95)  # High trust
belief = bayesian_update(belief, reddit_sentiment, 0.60)      # Medium trust
belief = bayesian_update(belief, app_ratings, 0.70)           # Medium-high trust

final_conviction = belief  # 0.85 = bullish with high conviction
```

### Layer 6: LLM-Based Synthesis (Natural Language Thesis)

**Use Language Model to Synthesize Everything:**

```python
async def generate_investment_thesis(company_id: str, signals: List[Signal]):
    """
    Use LLM to synthesize all signals into coherent investment thesis.

    LLM has access to:
    - All 100+ signals with scores, descriptions, timestamps
    - Historical correlation patterns
    - Identified contradictions
    - Causal graph structure
    """

    prompt = f"""
    You are a quantitative analyst synthesizing alternative data for {company_id}.

    EDGAR GROUND TRUTH (Last Quarter):
    - Revenue: {edgar_revenue} (Growth: {revenue_growth}%)
    - Net Margin: {net_margin}%
    - Operating Cash Flow: {ocf} (Margin: {ocf_margin}%)
    - Insider Activity: {insider_summary}

    ALTERNATIVE SIGNALS:
    - App Ratings: {app_ratings}/5 ({app_reviews:,} reviews)
    - Social Sentiment: {reddit_score} (Reddit: {reddit_mentions} mentions)
    - Search Trends: {google_trends_change}% change
    - Hiring Velocity: {job_postings_change}% change

    SIGNAL CORRELATIONS:
    - Reddit sentiment has 72% correlation with +1Q revenue (p<0.01)
    - App rating decline predicts churn increase (r=-0.85)
    - Insider buying precedes earnings beats 65% of the time

    CONTRADICTIONS DETECTED:
    {list_of_contradictions}

    Generate investment thesis covering:
    1. **Overall Verdict**: Bullish / Bearish / Neutral + Conviction (0-100)
    2. **Bull Case**: 3 strongest arguments supported by data
    3. **Bear Case**: 3 biggest risks/concerns
    4. **Key Catalysts**: What events/signals to monitor
    5. **Synthesis**: How alternative signals validate/contradict EDGAR truth
    6. **Recommended Action**: Buy / Sell / Hold + Position Size

    Be data-driven, specific, and actionable.
    """

    response = await claude_api.complete(prompt)
    return response
```

**Example Output:**

```markdown
# UBER Investment Thesis - February 2026

## Overall Verdict: BULLISH (Conviction: 85/100)

Uber has fundamentally transformed from unprofitable growth story to
highly profitable cash machine. This is confirmed across all signal types.

## Bull Case

1. **Exceptional Profitability** (EDGAR TRUTH)
   - Q3 2025 net margin: 49.2% (vs -50% in 2020)
   - Operating cash flow margin: 53.6% (vs negative historically)
   - This is not a one-quarter fluke - profitability trend sustained 8 quarters

2. **Product Excellence Validated** (Alternative → EDGAR)
   - App ratings: 4.90/5 (15M reviews) = best-in-class user satisfaction
   - This is TRANSLATING to revenue: +6.5% QoQ growth
   - Reddit sentiment +30 CONFIRMS strong product-market fit

3. **Operating Leverage Kicking In** (Signal Synthesis)
   - Job postings down -20% (not hiring aggressively)
   - YET margins expanding +10pp QoQ
   - This is the Holy Grail: revenue growth + margin expansion + negative hiring

## Bear Case

1. **Growth Deceleration Risk**
   - Revenue growth slowed from +15% YoY (2023) to +6.5% QoQ (2025)
   - Google Trends stable (not growing) = market maturity
   - TAM expansion opportunities limited (already in most markets)

2. **Insider Selling** (Minor Concern)
   - CLO sold $260k recently
   - Given strong fundamentals, likely tax planning not lack of faith
   - BUT worth monitoring if more execs sell

3. **Competition Intensifying** (Need MD&A Risk Factors)
   - [Need to extract from EDGAR Risk Factors section]
   - Lyft, autonomous vehicles, regulation

## Key Catalysts to Monitor

1. **Next Earnings (Q4 2025)**: Can margins sustain >40%?
2. **Autonomous Vehicle Rollout**: Threat or opportunity?
3. **Reddit Sentiment Shift**: Currently bullish - watch for reversal
4. **Institutional Holdings (13F)**: Are smart money buyers increasing positions?

## Signal Synthesis

**Validation Matrix:**
- ✅ App ratings (4.90) → Net margin (49%) = Product quality → Profitability
- ✅ Reddit sentiment (+30) → Revenue growth (+6.5%) = Buzz → Demand
- ✅ Low hiring (-20) → High OCF margin (54%) = Efficiency → Cash generation
- ⚠️ Stable search trends → Revenue growth = Monetizing existing users well

**No Major Contradictions** = High confidence in thesis

## Recommended Action

**BUY** - Target 15% portfolio weight

**Rationale**: Rare combination of strong fundamentals (EDGAR truth)
validated by excellent alternative signals. Transformation from
unprofitable to 49% margins is real and sustainable. Alternative
data confirms this is not accounting gimmick.

**Entry**: Current levels
**Stop Loss**: If net margin falls below 30% (2 quarters in a row)
**Take Profit**: 25% gain or if insider selling accelerates

**Position Sizing**: High conviction (85/100) → Larger position acceptable
```

---

## Implementation Roadmap

### Phase 1: Correlation Engine (Week 1)
- Build time-series correlation calculator
- Identify which signals lead/lag others
- Statistical significance testing (p-values)
- Visualize correlation matrix

### Phase 2: Contradiction Detector (Week 2)
- Detect when signals disagree
- Priority resolution (EDGAR > Alternative)
- Alert system for high-severity contradictions
- Track contradiction frequency (signal reliability)

### Phase 3: Causal Graph (Week 3)
- Model causal relationships between signals
- Bayesian belief network
- Probabilistic reasoning
- Scenario simulation ("What if app ratings decline 10%?")

### Phase 4: LLM Thesis Generator (Week 4)
- Integrate Claude API
- Natural language thesis generation
- Bull/bear case construction
- Actionable recommendations

---

## Success Metrics

We'll know synthesis works when:

1. ✅ Thesis is **data-driven** (cites specific signals with numbers)
2. ✅ Thesis is **coherent** (no contradictions, logical flow)
3. ✅ Thesis is **actionable** (clear buy/sell/hold + conviction level)
4. ✅ Contradictions are **identified and resolved** explicitly
5. ✅ Alternative signals **connect to EDGAR truth** (validation shown)
6. ✅ Predictions are **testable** ("If X happens, expect Y")

---

## Next Steps

1. Build correlation engine to find signal relationships
2. Complete EDGAR coverage (MD&A, Risk Factors, 8-K, 13F)
3. Implement LLM-based synthesis
4. Backtest: Can we predict next quarter's EDGAR results from alternative signals?

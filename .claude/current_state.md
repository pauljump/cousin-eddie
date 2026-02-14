# cousin-eddie - Current State

**Last updated:** 2026-02-14
**Sessions:** 3
**Readiness:** 90%

## Goal
**NEW STRATEGIC DIRECTION:** cousin-eddie is now the validation infrastructure for /borg (question-driven intelligence engine with closed-loop learning).

Purpose: Backtest SEC filing signals against multi-year price data to discover which signals actually predict moves. These validated patterns become borg's initial strategy weights for stock prediction domain.

## Status
**Backtesting complete across 4 tickers.** Two SEC signal types validated as statistically significant predictors. Investment strategy synthesized.

## Key Findings (Session 3)

### Validated Predictive Signals

**SEC Form 144 (proposed insider sales) — contrarian buy signal across ALL 4 tickers:**
- UBER: +5.9% avg 60d return, p=0.0062, n=57
- LYFT: +9.9% avg 60d return, p=0.0250, n=42
- DASH: +11.9% avg 60d return, p=0.0000, Sharpe=0.646, n=156
- META: +9.9% avg 60d return, p=0.0000, Sharpe=0.537, n=377
- **Key insight:** Despite being a notice of planned selling, stocks go UP afterward. Contrarian signal.

**SEC Form 4 (insider trades) — predictive for 3 of 4 tickers:**
- UBER: +4.7% avg 60d return, p=0.0000, IC=0.132, n=925
- DASH: +3.5% avg 20d return, p=0.0000, IC=0.150, n=983
- META: +7.3% avg 60d return, p=0.0000, IC=0.123, n=1514
- LYFT: NOT significant (secular decline overwhelms signal)

### Optimal holding period: 60 trading days (~3 months)

## Data Coverage

| Ticker | Signals | Prices | Date Range |
|--------|---------|--------|------------|
| UBER | 1,222 | 1,701 | May 2019 - Feb 2026 |
| LYFT | 488 | 1,730 | Mar 2019 - Feb 2026 |
| DASH | 1,176 | 1,301 | Dec 2020 - Feb 2026 |
| META | 1,973 | 1,708 | May 2019 - Feb 2026 |

## Active Decisions
1. **cousin-eddie → borg bootstrap** - Use backtesting results to seed borg's strategy weights
2. **Form 144 is strongest signal** - Contrarian buy, consistent across all tickers
3. **Form 4 confirms** - Insider buys are bullish at 60-day horizon
4. **60-day holding period** - Statistical significance peaks at this window
5. **LYFT is an outlier** - Secular decline overwhelms insider signals

## Open Blockers
1. **8-K HTML parsing broken** - `_extract_8k_items` finds filings but generates 0 signals (SEC HTML format changed). Fixing would add another signal dimension.
2. **Alternative data too sparse** - Most non-SEC signal types have < 3 observations, insufficient for backtesting.

## Unvalidated Assumptions
1. ~~SEC EDGAR API is sufficient for real-time filing monitoring~~ **VALIDATED** - Full historical backfill working
2. ~~Time-series correlation between signals and price movements will be statistically significant~~ **VALIDATED** - Form 4 and Form 144 both significant
3. Free data sources provide enough signal strength (vs paid alternatives) — partially validated
4. The Form 144 contrarian effect persists (may be well-known and arbitraged away)
5. Survivorship bias — only tested on companies that remain public

## Next Actions
1. Fix 8-K HTML parser to unlock material event signals
2. Build borg integration — export validated strategy weights
3. Add more tickers to test cross-sector generalization
4. Consider paid data sources for alternative signals (currently too sparse)
5. Paper trade the Form 144 contrarian strategy for out-of-sample validation

## Recent Progress
- Session 1: Foundation — architecture, 4 processors, orchestration, first data flowing
- Session 2: Scale — 45 signal types, 332 signals, market data infrastructure, options chain
- Session 3: **BACKTESTING + STRATEGY**
  - Built shared EdgarClient to fetch ALL filings (recent + archived batches)
  - Refactored 3 SEC processors (Form 4, 8-K, Form 144) to use EdgarClient
  - Added LYFT, DASH, META to company registry with CIKs
  - Fixed backfill script to use registry for CIK lookup + correct SignalModel mapping
  - Ingested market data: LYFT (1,730), DASH (1,301), META (1,708) price records
  - Backfilled SEC signals: UBER (890), LYFT (488), DASH (1,176), META (1,973)
  - Ran backtests across all 4 tickers — 4,859 total signals tested
  - **Discovered Form 144 contrarian buy signal** — strongest finding, p<0.05 on all tickers
  - **Validated Form 4 insider trades** — predictive at 60d horizon for 3/4 tickers
  - Synthesized investment strategy with current readings for each ticker

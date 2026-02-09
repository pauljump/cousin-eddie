# cousin-eddie - Current State

**Last updated:** 2026-02-08
**Sessions:** 2
**Readiness:** 85%

## Goal
**NEW STRATEGIC DIRECTION:** cousin-eddie is now the validation infrastructure for /borg (question-driven intelligence engine with closed-loop learning).

Purpose: Backtest 332 signals against 6.7 years of price data to discover which signals actually predict moves. These validated patterns become borg's initial strategy weights for stock prediction domain. Once validated on stocks (fast feedback), patterns transfer to other domains (real estate, jobs, etc.).

## Status
Ready to backtest - Data collection complete, moving to analysis

## Active Decisions
1. **cousin-eddie → borg bootstrap** - Use backtesting results to seed borg's strategy weights
2. **Stock prediction as borg's first domain** - Fast feedback cycles (days vs months), objective outcomes
3. **Signal validation is critical** - Need ground truth on which signals predict moves before building borg
4. **Plugin architecture** - Each signal type is independent processor (becomes borg connector)
5. **Normalized signal schema** - All signals output to same format (-100 to +100 score)
6. **Backtest-first** - Validate signals against historical price data, patterns transfer to borg

## Open Blockers
None yet

## Unvalidated Assumptions
1. SEC EDGAR API is sufficient for real-time filing monitoring
2. Free data sources provide enough signal strength (vs paid alternatives)
3. LLM-based sentiment analysis is accurate enough for trading decisions
4. Single developer + Claude can build and maintain 100+ signal processors
5. Time-series correlation between signals and price movements will be statistically significant

## Next Actions (Backtesting Phase)
1. Add Lyft + SPY/QQQ for comparison
2. Build backtesting framework - correlate signals with forward returns
3. Statistical validation:
   - Which signals predict moves? (correlation, p-values)
   - What's the lag time? (signal → price reaction in X days)
   - What's the edge? (expected return after signal fires)
4. Extract patterns → These become borg's initial strategy templates
5. Document validated strategies for borg bootstrap

## Recent Progress
- Session 1: Project defined - Alternative data intelligence platform
- Session 1: Architecture designed - Plugin-based signal processing
- Session 1: Research analyzed - 100+ signal types identified
- Session 1: Uber selected as POC company
- Session 1: Foundation built - Core abstractions, DB schema, SEC Form 4 processor
- Session 1: Built 3 more signal processors (Job Postings, App Store, Google Trends)
- Session 1: Built orchestration pipeline - parallel async execution
- Session 1: Fixed database issues - metadata conflicts, serialization, IPv6
- Session 1: **REAL DATA FLOWING** - 4 signals ingested for Uber from App Store + Job sites
- Session 1: Query tool working - rich table formatting
- Session 1: All committed and pushed to GitHub (73acef7)
- Session 2: **COMPLETE EDGAR COVERAGE** - 10 SEC processors, 258 regulatory signals
- Session 2: Added Form 144 processor - leading indicator for insider selling (16 signals)
- Session 2: Ran all 42 processors on Uber - **332 total signals across 45 signal types**
- Session 2: Built market data infrastructure - stock prices, intraday, options chain
- Session 2: Ingested **1,696 daily prices** (May 2019-Feb 2026, full IPO history)
- Session 2: Ingested **980 option contracts** across 17 expirations with greeks/IV
- Session 2: Options metrics: P/C ratio 0.49 (bullish), 30-day IV 46.6%
- Session 2: **READY FOR BACKTESTING** - signals + prices + options all in database
- Session 2: All committed and pushed to GitHub (53f4d51)

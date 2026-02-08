# cousin-eddie - Current State

**Last updated:** 2026-02-08
**Sessions:** 2
**Readiness:** 85%

## Goal
Build a signal-agnostic alternative data intelligence platform that can analyze ANY public company using 100+ signal types. Uber is the POC to prove methodology.

## Status
Ready to backtest - Data collection complete, moving to analysis

## Active Decisions
1. **Platform over point solution** - Build reusable platform, not just Uber tracker
2. **Plugin architecture** - Each signal type is independent processor with standard interface
3. **Normalized signal schema** - All signals output to same format (-100 to +100 score)
4. **Uber as POC** - Prove out methodology on one company first, then scale
5. **Exhaustive signal coverage** - Target all 100+ signal types from research
6. **Backtest-first** - Validate signals against historical price data before trading

## Open Blockers
None yet

## Unvalidated Assumptions
1. SEC EDGAR API is sufficient for real-time filing monitoring
2. Free data sources provide enough signal strength (vs paid alternatives)
3. LLM-based sentiment analysis is accurate enough for trading decisions
4. Single developer + Claude can build and maintain 100+ signal processors
5. Time-series correlation between signals and price movements will be statistically significant

## Next Actions
1. Add Lyft signals for comparison (isolate Uber vs industry trends)
2. Add SPY/QQQ benchmark indices
3. Start backtesting - correlate signals with price movements
4. Identify which signals actually predict moves
5. Measure signal lag time (when does price react?)

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

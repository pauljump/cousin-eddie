# cousin-eddie - Current State

**Last updated:** 2026-02-07
**Sessions:** 1
**Readiness:** 43%

## Goal
Build a signal-agnostic alternative data intelligence platform that can analyze ANY public company using 100+ signal types. Uber is the POC to prove methodology.

## Status
Designing - Architecture defined, ready to build

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
1. Update readiness.json with new checklist status
2. Create project structure (signal_types/, core/, api/)
3. Define SignalProcessor interface
4. Setup database schema
5. Build first signal processor (SEC Form 4)

## Recent Progress
- Session 1: Project defined - Alternative data intelligence platform
- Session 1: Architecture designed - Plugin-based signal processing
- Session 1: Research analyzed - 100+ signal types identified
- Session 1: Uber selected as POC company

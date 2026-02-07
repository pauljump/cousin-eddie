---
id: IDEA-164
collection: concepts
directory: cousin-eddie
title: Cousin Eddie
type: Personal Tool
status: active
confidence: Very High
one_liner: Personal SEC filing delta detector - your friend giving you tips on what changed
primary_user: Me (personal investing research)
buyer: N/A (personal use)
distribution_wedge: N/A (personal use)
revenue_model: N/A (personal use)
time_to_signal_days: 14
related:
- IDEA-157_edgar-delta-tracker
- IDEA-158_uber-intelligence-engine
- IDEA-013_easyedgar-sec-aggregator
---

# Cousin Eddie

**What changed in that 300-page SEC filing? Your buddy Eddie tells you.**

---

## Core Thesis

**Personal Use Case:** I want to track companies I'm interested in without manually reading 300-page filings. I need to know:
1. What actually changed between filings
2. What new risks were added/removed
3. What material changes happened in financials or legal proceedings

**The Solution:** Automated delta detection that alerts me to changes I should pay attention to.

**Matt Levine Insight:** "Everything is securities fraud" = everything is about what companies hoped you wouldn't notice. Cousin Eddie tells me exactly that.

---

## Product

### Core Features
- **Daily Delta Detection:** Compare filings N vs N-1 across all public companies
- **Section-Level Analysis:** Risk Factors, MD&A, Financial Statements, Legal Proceedings
- **Severity Scoring:** Low/Medium/High impact classification
- **Pattern Recognition:** "Risk factor added," "Revenue recognition changed," "Lawsuit disclosed"
- **Delivery:** CSV, API, Webhooks

### Technical Implementation
```
Week 1: SEC EDGAR scraper (watched companies only)
Week 2: Parser for 10-K, 10-Q, 8-K filings
Week 3: Diff engine (section-by-section comparison)
Week 4: Notification system + simple web dashboard
```

**Build Approach:** Iterative, build for personal use first

---

## Personal Workflow

### Daily Use
- Check dashboard for watched companies' new filings
- Review delta highlights (what changed)
- Drill into specific sections if needed
- Export notes/highlights for investment journal

### Watchlist
- Track 10-20 companies I'm researching
- Monitor for 10-K, 10-Q, 8-K filings
- Set priority levels (high/medium/low attention)

### Delivery
- Daily email digest (or Slack notification)
- Web dashboard for deep dives
- Local CSV export for archival

---

## Success Metrics

**Week 1:** Successfully tracking 5 companies with delta detection working
**Month 1:** Caught at least one material change I would have missed manually
**Month 3:** Using it daily, tracking 15+ companies reliably
**Month 6:** Has influenced at least one investment decision

---

## Why This Works (Personal Use)

1. **Solves real personal pain** (I hate reading 300-page filings)
2. **No customers to please** (just build for myself)
3. **Can iterate quickly** (immediate feedback loop)
4. **Clear utility** (better investment research)
5. **Learning experience** (understanding SEC data deeply)

---

**Status:** Active development
**First Signal:** Week 1 (first delta detection working)
**Confidence:** Very High (scratching my own itch)

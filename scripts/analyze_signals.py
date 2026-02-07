#!/usr/bin/env python
"""
Signal Analysis Tool

Analyzes signal relationships, correlations, and generates summary statistics.
Does NOT require API - pure data analysis.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from src.models.base import SessionLocal
from src.models.signal import SignalModel
from src.core.company import get_registry


console = Console()


def analyze_company(company_ticker: str, lookback_days: int = 90):
    """Analyze all signals for a company"""

    registry = get_registry()
    company = registry.get(company_ticker)

    if not company:
        console.print(f"[red]Company {company_ticker} not found[/red]")
        return

    console.print(f"\n[bold cyan]Signal Analysis: {company.name} ({company.ticker})[/bold cyan]\n")

    session = SessionLocal()

    try:
        # Fetch signals
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        signals = session.query(SignalModel).filter(
            SignalModel.company_id == company_ticker,
            SignalModel.timestamp >= cutoff
        ).all()

        if not signals:
            console.print("[yellow]No signals found[/yellow]")
            return

        console.print(f"[green]Analyzing {len(signals)} signals from last {lookback_days} days[/green]\n")

        # Group by category
        by_category = defaultdict(list)
        by_type = defaultdict(list)

        for sig in signals:
            by_category[sig.category].append(sig)
            by_type[sig.signal_type].append(sig)

        # ============================================
        # 1. CATEGORY SUMMARY
        # ============================================
        console.print("[bold]1. SIGNAL CATEGORIES[/bold]\n")

        cat_table = Table(show_header=True, header_style="bold magenta")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Signals", justify="right")
        cat_table.add_column("Avg Score", justify="right")
        cat_table.add_column("Sentiment", justify="center")

        for category in sorted(by_category.keys()):
            cat_signals = by_category[category]
            scores = [s.score for s in cat_signals if s.score is not None]

            if scores:
                avg_score = statistics.mean(scores)

                if avg_score > 30:
                    sentiment = "[green]BULLISH[/green]"
                elif avg_score < -30:
                    sentiment = "[red]BEARISH[/red]"
                else:
                    sentiment = "[yellow]NEUTRAL[/yellow]"

                cat_table.add_row(
                    category.upper(),
                    str(len(cat_signals)),
                    f"{avg_score:+.0f}",
                    sentiment
                )

        console.print(cat_table)
        console.print()

        # ============================================
        # 2. EDGAR GROUND TRUTH
        # ============================================
        console.print("[bold]2. EDGAR GROUND TRUTH (Financial Statements)[/bold]\n")

        edgar_signals = by_category.get('regulatory', [])
        edgar_latest = sorted(edgar_signals, key=lambda s: s.timestamp, reverse=True)[:10]

        if edgar_latest:
            edgar_table = Table(show_header=True, header_style="bold green")
            edgar_table.add_column("Signal Type", style="green")
            edgar_table.add_column("Date")
            edgar_table.add_column("Score", justify="right")
            edgar_table.add_column("Description")

            for sig in edgar_latest:
                edgar_table.add_row(
                    sig.signal_type,
                    sig.timestamp.strftime('%Y-%m-%d'),
                    f"{sig.score:+d}" if sig.score else "0",
                    sig.description[:60] + "..." if len(sig.description) > 60 else sig.description
                )

            console.print(edgar_table)
        else:
            console.print("[yellow]No EDGAR signals found[/yellow]")

        console.print()

        # ============================================
        # 3. ALTERNATIVE SIGNALS
        # ============================================
        console.print("[bold]3. ALTERNATIVE SIGNALS (Real-Time Indicators)[/bold]\n")

        alt_signals = []
        for cat in ['web_digital', 'alternative', 'workforce']:
            alt_signals.extend(by_category.get(cat, []))

        alt_latest = sorted(alt_signals, key=lambda s: s.timestamp, reverse=True)[:10]

        if alt_latest:
            alt_table = Table(show_header=True, header_style="bold blue")
            alt_table.add_column("Signal Type", style="blue")
            alt_table.add_column("Date")
            alt_table.add_column("Score", justify="right")
            alt_table.add_column("Description")

            for sig in alt_latest:
                alt_table.add_row(
                    sig.signal_type,
                    sig.timestamp.strftime('%Y-%m-%d'),
                    f"{sig.score:+d}" if sig.score else "0",
                    sig.description[:60] + "..." if len(sig.description) > 60 else sig.description
                )

            console.print(alt_table)
        else:
            console.print("[yellow]No alternative signals found[/yellow]")

        console.print()

        # ============================================
        # 4. SIGNAL SYNTHESIS
        # ============================================
        console.print("[bold]4. SIGNAL SYNTHESIS (EDGAR Truth vs Alternative)[/bold]\n")

        # Get most recent signals by type
        latest_by_type = {}
        for signal_type, type_signals in by_type.items():
            latest_by_type[signal_type] = max(type_signals, key=lambda s: s.timestamp)

        # Look for validation/contradiction patterns
        synthesis_points = []

        # Example: Financial performance vs Product quality
        profit_margin = latest_by_type.get('profit_margin')
        app_ratings = latest_by_type.get('app_store_ratings')

        if profit_margin and app_ratings:
            if profit_margin.score > 50 and app_ratings.score > 60:
                synthesis_points.append(
                    f"✅ **VALIDATED**: App ratings ({app_ratings.score:+d}) confirm strong profitability "
                    f"(margin score: {profit_margin.score:+d}). Product quality → Financial performance."
                )
            elif profit_margin.score < 0 and app_ratings.score > 60:
                synthesis_points.append(
                    f"⚠️ **CONTRADICTION**: App ratings high ({app_ratings.score:+d}) but profitability "
                    f"low ({profit_margin.score:+d}). Investigate: Product good but not monetizing?"
                )

        # Example: Revenue growth vs Sentiment
        revenue_growth = latest_by_type.get('revenue_growth_qoq')
        reddit_sent = latest_by_type.get('reddit_sentiment')

        if revenue_growth and reddit_sent:
            if revenue_growth.score > 30 and reddit_sent.score > 20:
                synthesis_points.append(
                    f"✅ **VALIDATED**: Reddit sentiment ({reddit_sent.score:+d}) confirms revenue "
                    f"growth ({revenue_growth.score:+d}). Social buzz → Real demand."
                )

        # Example: Cash flow vs Hiring
        ocf = latest_by_type.get('operating_cash_flow')
        jobs = latest_by_type.get('job_postings')

        if ocf and jobs:
            if ocf.score > 50 and jobs.score < 0:
                synthesis_points.append(
                    f"✅ **VALIDATED**: Low hiring ({jobs.score:+d}) with strong cash flow "
                    f"({ocf.score:+d}) = Operating leverage. Efficiency improving."
                )

        if synthesis_points:
            for point in synthesis_points:
                console.print(Markdown(point))
        else:
            console.print("[yellow]Not enough signals to synthesize relationships[/yellow]")

        console.print()

        # ============================================
        # 5. AGGREGATE VERDICT
        # ============================================
        console.print("[bold]5. AGGREGATE VERDICT[/bold]\n")

        # Calculate weighted average score
        all_scores = [s.score for s in signals if s.score is not None]

        if all_scores:
            avg_score = statistics.mean(all_scores)
            median_score = statistics.median(all_scores)

            # Weight EDGAR signals higher
            edgar_scores = [s.score for s in edgar_signals if s.score is not None]
            alt_scores = [s.score for s in alt_signals if s.score is not None]

            if edgar_scores and alt_scores:
                weighted_score = (statistics.mean(edgar_scores) * 0.70 +
                                  statistics.mean(alt_scores) * 0.30)
            else:
                weighted_score = avg_score

            # Determine verdict
            if weighted_score > 40:
                verdict = "BULLISH"
                color = "green"
            elif weighted_score < -40:
                verdict = "BEARISH"
                color = "red"
            else:
                verdict = "NEUTRAL"
                color = "yellow"

            verdict_text = f"""
**Overall Score:** {weighted_score:+.0f} (EDGAR: 70%, Alternative: 30%)
**Verdict:** [{color}]{verdict}[/{color}]

**Score Breakdown:**
- EDGAR Fundamentals: {statistics.mean(edgar_scores):+.0f} ({len(edgar_scores)} signals)
- Alternative Signals: {statistics.mean(alt_scores):+.0f} ({len(alt_scores)} signals)
- Combined Average: {avg_score:+.0f}

**Interpretation:**
"""

            if verdict == "BULLISH":
                verdict_text += "Strong fundamentals (EDGAR truth) validated by positive alternative signals. "
                verdict_text += "High confidence in positive outlook."
            elif verdict == "BEARISH":
                verdict_text += "Weak fundamentals (EDGAR truth) confirmed by negative alternative signals. "
                verdict_text += "High confidence in negative outlook."
            else:
                verdict_text += "Mixed signals or neutral fundamentals. No clear directional bias. "
                verdict_text += "More data needed for conviction."

            console.print(Panel(verdict_text, title=f"[bold]{company.ticker} Investment Verdict[/bold]", border_style=color))

        console.print()

    finally:
        session.close()


def main():
    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python scripts/analyze_signals.py <TICKER> [LOOKBACK_DAYS][/yellow]")
        console.print("\nExample:")
        console.print("  python scripts/analyze_signals.py UBER")
        console.print("  python scripts/analyze_signals.py UBER 180")
        console.print("  python scripts/analyze_signals.py LYFT")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    lookback_days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    analyze_company(ticker, lookback_days=lookback_days)


if __name__ == "__main__":
    main()

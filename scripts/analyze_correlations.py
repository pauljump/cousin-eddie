#!/usr/bin/env python
"""
Signal Correlation Analyzer

Discovers relationships between signals:
- Which signals predict others (lead-lag analysis)
- Which signals move together (correlation matrix)
- Leading indicators for key metrics
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.synthesis.correlation_engine import CorrelationEngine
from src.core.company import get_registry


console = Console()


def main():
    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python scripts/analyze_correlations.py <TICKER> [TARGET_SIGNAL][/yellow]")
        console.print("\nExamples:")
        console.print("  python scripts/analyze_correlations.py UBER")
        console.print("  python scripts/analyze_correlations.py UBER revenue_growth_qoq")
        console.print("\nFirst form: Show all significant correlations")
        console.print("Second form: Show leading indicators for specific signal")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    target_signal = sys.argv[2] if len(sys.argv) > 2 else None

    # Get company from registry
    registry = get_registry()
    company = registry.get(ticker)

    if not company:
        console.print(f"[red]Company {ticker} not found[/red]")
        return

    console.print(f"\n[bold cyan]Signal Correlation Analysis: {company.name} ({company.ticker})[/bold cyan]\n")

    with CorrelationEngine() as engine:
        if target_signal:
            # Find leading indicators for specific signal
            analyze_leading_indicators(engine, company, target_signal)
        else:
            # Show all significant correlations
            analyze_all_correlations(engine, company)


def analyze_all_correlations(engine: CorrelationEngine, company):
    """Analyze all signal correlations"""

    console.print("[bold]Analyzing all signal pair correlations...[/bold]\n")

    results = engine.analyze_company(company, max_lag=4, min_observations=5)

    if not results:
        console.print("[yellow]No significant correlations found[/yellow]")
        return

    console.print(f"[green]Found {len(results)} significant correlations (p < 0.05)[/green]\n")

    # Group by strength
    strong = [r for r in results if abs(r.correlation) > 0.7]
    moderate = [r for r in results if 0.4 < abs(r.correlation) <= 0.7]
    weak = [r for r in results if 0.2 < abs(r.correlation) <= 0.4]

    # ============================================
    # 1. STRONG CORRELATIONS
    # ============================================
    if strong:
        console.print("[bold]1. STRONG CORRELATIONS (|r| > 0.7)[/bold]\n")

        table = Table(show_header=True, header_style="bold green")
        table.add_column("Signal A", style="cyan")
        table.add_column("Signal B", style="cyan")
        table.add_column("r", justify="right")
        table.add_column("Lag", justify="right")
        table.add_column("p-value", justify="right")
        table.add_column("Interpretation")

        for r in strong[:15]:  # Top 15
            lag_str = f"+{r.lag}Q" if r.lag > 0 else "0Q"
            interpretation = _interpret_correlation(r)

            table.add_row(
                r.signal_a,
                r.signal_b,
                f"{r.correlation:+.3f}",
                lag_str,
                f"{r.p_value:.4f}",
                interpretation
            )

        console.print(table)
        console.print()

    # ============================================
    # 2. MODERATE CORRELATIONS
    # ============================================
    if moderate:
        console.print("[bold]2. MODERATE CORRELATIONS (0.4 < |r| ≤ 0.7)[/bold]\n")

        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Signal A", style="cyan")
        table.add_column("Signal B", style="cyan")
        table.add_column("r", justify="right")
        table.add_column("Lag", justify="right")
        table.add_column("Interpretation")

        for r in moderate[:10]:  # Top 10
            lag_str = f"+{r.lag}Q" if r.lag > 0 else "0Q"
            interpretation = _interpret_correlation(r)

            table.add_row(
                r.signal_a,
                r.signal_b,
                f"{r.correlation:+.3f}",
                lag_str,
                interpretation
            )

        console.print(table)
        console.print()

    # ============================================
    # 3. LEADING INDICATORS
    # ============================================
    console.print("[bold]3. LEADING INDICATORS (Lag > 0)[/bold]\n")

    leading = [r for r in results if r.lag > 0]

    if leading:
        # Group by what they predict
        by_target = defaultdict(list)
        for r in leading:
            by_target[r.signal_b].append(r)

        for target, predictors in sorted(by_target.items()):
            console.print(f"[cyan]Signals that predict {target}:[/cyan]")

            for r in sorted(predictors, key=lambda x: abs(x.correlation), reverse=True)[:5]:
                console.print(
                    f"  • {r.signal_a} leads by {r.lag}Q: r={r.correlation:+.3f} "
                    f"(p={r.p_value:.4f})"
                )

            console.print()
    else:
        console.print("[yellow]No leading indicators found (need more historical data)[/yellow]\n")


def analyze_leading_indicators(engine: CorrelationEngine, company, target_signal: str):
    """Find signals that predict a target signal"""

    console.print(f"[bold]Finding leading indicators for: [cyan]{target_signal}[/cyan][/bold]\n")

    leading = engine.find_leading_indicators(
        company,
        target_signal,
        max_lag=4,
        min_correlation=0.3,
    )

    if not leading:
        console.print(f"[yellow]No leading indicators found for {target_signal}[/yellow]")
        console.print("\nPossible reasons:")
        console.print("  • Not enough historical data")
        console.print("  • No signals correlate with this metric")
        console.print("  • Try a different target signal")
        return

    console.print(f"[green]Found {len(leading)} leading indicators[/green]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Leading Signal", style="cyan")
    table.add_column("Correlation", justify="right")
    table.add_column("Lead Time", justify="right")
    table.add_column("p-value", justify="right")
    table.add_column("Strength")
    table.add_column("Interpretation")

    for r in leading:
        interpretation = _interpret_leading_indicator(r)

        table.add_row(
            r.signal_a,
            f"{r.correlation:+.3f}",
            f"{r.lag} quarters",
            f"{r.p_value:.4f}",
            r.strength.upper(),
            interpretation
        )

    console.print(table)
    console.print()

    # Summary
    summary = f"""
**KEY INSIGHTS:**

The signals above are **leading indicators** for {target_signal}.

**How to use:**
1. Monitor these signals closely - changes predict future {target_signal}
2. Stronger correlations (|r| > 0.7) are more reliable predictors
3. Lead time shows how far in advance the signal predicts
4. Low p-values (< 0.05) indicate statistical significance

**Example:**
If "app_store_ratings" leads "{target_signal}" by 1 quarter with r=+0.85,
then improving app ratings NOW predict higher {target_signal} NEXT quarter.
"""

    console.print(Panel(summary, title="[bold]How to Interpret[/bold]", border_style="blue"))


def _interpret_correlation(r) -> str:
    """Generate interpretation of correlation"""
    if r.lag > 0:
        return f"{r.signal_a} predicts {r.signal_b} {r.lag}Q ahead"
    else:
        return f"Move together ({r.direction})"


def _interpret_leading_indicator(r) -> str:
    """Generate interpretation of leading indicator"""
    direction = "rises" if r.correlation > 0 else "falls"
    target_direction = "rise" if r.correlation > 0 else "fall"

    return f"When {r.signal_a} {direction} → {r.signal_b} will {target_direction}"


if __name__ == "__main__":
    main()

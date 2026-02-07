#!/usr/bin/env python3
"""
Query signals from database.

Usage:
    python scripts/query_signals.py --company UBER
    python scripts/query_signals.py --company UBER --type sec_form_4
    python scripts/query_signals.py --company UBER --days 7
    python scripts/query_signals.py --summary
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import func, desc
from rich.console import Console
from rich.table import Table

from src.models.base import SessionLocal
from src.models.signal import SignalModel
from src.core.signal import SignalCategory


def query_signals(
    company_id: str = None,
    signal_type: str = None,
    days: int = 30,
    limit: int = 50
):
    """Query signals from database"""

    db = SessionLocal()
    try:
        query = db.query(SignalModel)

        # Filters
        if company_id:
            query = query.filter(SignalModel.company_id == company_id)

        if signal_type:
            query = query.filter(SignalModel.signal_type == signal_type)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(SignalModel.timestamp >= cutoff)

        # Order by timestamp descending
        query = query.order_by(desc(SignalModel.timestamp))

        # Limit
        if limit:
            query = query.limit(limit)

        signals = query.all()
        return signals

    finally:
        db.close()


def get_summary():
    """Get summary statistics"""

    db = SessionLocal()
    try:
        # Total signals
        total = db.query(func.count(SignalModel.id)).scalar()

        # By company
        by_company = db.query(
            SignalModel.company_id,
            func.count(SignalModel.id).label('count')
        ).group_by(SignalModel.company_id).all()

        # By signal type
        by_type = db.query(
            SignalModel.signal_type,
            func.count(SignalModel.id).label('count')
        ).group_by(SignalModel.signal_type).all()

        # By category
        by_category = db.query(
            SignalModel.category,
            func.count(SignalModel.id).label('count')
        ).group_by(SignalModel.category).all()

        # Latest signal
        latest = db.query(SignalModel).order_by(
            desc(SignalModel.ingested_at)
        ).first()

        return {
            'total': total,
            'by_company': by_company,
            'by_type': by_type,
            'by_category': by_category,
            'latest': latest
        }

    finally:
        db.close()


def display_signals(signals):
    """Display signals in a table"""

    console = Console()

    if not signals:
        console.print("[yellow]No signals found[/yellow]")
        return

    table = Table(title=f"Signals ({len(signals)} results)")

    table.add_column("Company", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Timestamp", style="green")
    table.add_column("Score", style="yellow", justify="right")
    table.add_column("Confidence", style="blue", justify="right")
    table.add_column("Description", style="white")

    for signal in signals:
        # Color code score
        score = signal.score
        if score > 50:
            score_str = f"[bold green]+{score}[/bold green]"
        elif score > 0:
            score_str = f"[green]+{score}[/green]"
        elif score < -50:
            score_str = f"[bold red]{score}[/bold red]"
        elif score < 0:
            score_str = f"[red]{score}[/red]"
        else:
            score_str = f"[dim]{score}[/dim]"

        table.add_row(
            signal.company_id,
            signal.signal_type,
            signal.timestamp.strftime("%Y-%m-%d %H:%M"),
            score_str,
            f"{signal.confidence:.2f}",
            signal.description[:60] + "..." if signal.description and len(signal.description) > 60 else signal.description or ""
        )

    console.print(table)


def display_summary(summary):
    """Display summary statistics"""

    console = Console()

    console.print(f"\n[bold cyan]Database Summary[/bold cyan]\n")
    console.print(f"Total signals: [bold]{summary['total']}[/bold]")

    if summary['latest']:
        console.print(f"Latest ingestion: [green]{summary['latest'].ingested_at}[/green]")

    # By company
    console.print(f"\n[bold]By Company:[/bold]")
    table = Table(show_header=False)
    table.add_column("Company", style="cyan")
    table.add_column("Count", style="yellow", justify="right")
    for company_id, count in summary['by_company']:
        table.add_row(company_id, str(count))
    console.print(table)

    # By signal type
    console.print(f"\n[bold]By Signal Type:[/bold]")
    table = Table(show_header=False)
    table.add_column("Type", style="magenta")
    table.add_column("Count", style="yellow", justify="right")
    for signal_type, count in summary['by_type']:
        table.add_row(signal_type, str(count))
    console.print(table)

    # By category
    console.print(f"\n[bold]By Category:[/bold]")
    table = Table(show_header=False)
    table.add_column("Category", style="blue")
    table.add_column("Count", style="yellow", justify="right")
    for category, count in summary['by_category']:
        table.add_row(category.value if hasattr(category, 'value') else str(category), str(count))
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="Query alternative data signals")
    parser.add_argument(
        "--company",
        type=str,
        help="Filter by company ID (e.g., UBER)"
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by signal type (e.g., sec_form_4)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Filter to last N days (default: 30)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limit number of results (default: 50)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics"
    )

    args = parser.parse_args()

    if args.summary:
        summary = get_summary()
        display_summary(summary)
    else:
        signals = query_signals(
            company_id=args.company,
            signal_type=args.type,
            days=args.days,
            limit=args.limit
        )
        display_signals(signals)


if __name__ == "__main__":
    main()

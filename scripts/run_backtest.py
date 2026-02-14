#!/usr/bin/env python3
"""
Run backtest for a ticker and display results.

Usage:
    python scripts/run_backtest.py --ticker UBER
    python scripts/run_backtest.py --ticker UBER --windows 1,5,20,60 --min-signals 5
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine


def main():
    parser = argparse.ArgumentParser(description="Run signal backtest")
    parser.add_argument("--ticker", required=True, help="Stock ticker (e.g., UBER)")
    parser.add_argument(
        "--windows",
        default="1,5,20,60",
        help="Forward return windows in trading days (default: 1,5,20,60)",
    )
    parser.add_argument(
        "--min-signals",
        type=int,
        default=3,
        help="Minimum signals per type to include (default: 3)",
    )
    args = parser.parse_args()

    windows = [int(w.strip()) for w in args.windows.split(",")]

    print(f"\n{'='*80}")
    print(f"  BACKTEST: {args.ticker}")
    print(f"  Forward windows: {windows} trading days")
    print(f"  Min signals per type: {args.min_signals}")
    print(f"{'='*80}\n")

    with BacktestEngine() as engine:
        results = engine.run_backtest(
            ticker=args.ticker,
            forward_windows=windows,
            min_signals=args.min_signals,
        )

    # Print baseline
    print("BASELINE (average return for any random day):")
    print(f"  {'Window':<10} {'Avg Return':>12} {'Median':>12} {'Std Dev':>12} {'N':>8}")
    print(f"  {'-'*54}")
    for w in windows:
        b = results.baseline_returns.get(w, {})
        print(
            f"  T+{w:<7} {b.get('avg', 0):>11.4%} {b.get('median', 0):>11.4%} "
            f"{b.get('std', 0):>11.4%} {b.get('n', 0):>8}"
        )
    print()

    # Sort signal types: predictive first (by best p-value), then non-predictive
    all_results = sorted(
        results.signal_results.values(),
        key=lambda r: (
            0 if r.is_predictive else 1,
            min(s.get("p_value", 1.0) for s in r.window_stats.values())
            if r.window_stats
            else 1.0,
        ),
    )

    # Print header
    print(f"SIGNAL RESULTS ({len(all_results)} signal types analyzed):")
    print()

    # For each window, print a compact table
    for w in windows:
        print(f"  --- T+{w} day forward returns ---")
        print(
            f"  {'Signal Type':<40} {'N':>4} {'Hit%':>6} {'AvgRet':>8} "
            f"{'t-stat':>7} {'p-val':>8} {'IC':>6} {'Sharpe':>7}  {'Sig?'}"
        )
        print(f"  {'-'*100}")

        for r in all_results:
            s = r.window_stats.get(w)
            if s is None:
                continue

            sig_marker = " ***" if s["p_value"] < 0.01 else " **" if s["p_value"] < 0.05 else " *" if s["p_value"] < 0.10 else ""
            color_start = "\033[92m" if s["p_value"] < 0.05 else "\033[91m" if s["p_value"] > 0.5 else ""
            color_end = "\033[0m" if color_start else ""

            print(
                f"  {color_start}{r.signal_type:<40} {s['n']:>4} "
                f"{s['hit_rate']:>5.1%} {s['avg_return']:>7.3%} "
                f"{s['t_stat']:>7.2f} {s['p_value']:>8.4f} "
                f"{s['information_coefficient']:>6.3f} {s['sharpe']:>7.3f}"
                f"{sig_marker}{color_end}"
            )
        print()

    # Summary
    predictive = results.predictive_signals()
    noise = [r for r in all_results if not r.is_predictive]

    print(f"{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  Total signals analyzed: {results.total_signals}")
    print(f"  Signal types analyzed:  {len(all_results)}")
    print(f"  Predictive (p<0.05):    {len(predictive)}")
    print(f"  Noise:                  {len(noise)}")
    print(f"  Price date range:       {results.date_range[0]} to {results.date_range[1]}")
    print()

    if predictive:
        print("  TOP PREDICTIVE SIGNALS:")
        for r in predictive[:10]:
            best_w = r.best_window
            best_s = r.window_stats.get(best_w, {})
            print(
                f"    \033[92m{r.signal_type:<40}\033[0m "
                f"best@T+{best_w}: p={best_s.get('p_value', 1.0):.4f}, "
                f"avg={best_s.get('avg_return', 0):.3%}, "
                f"IC={best_s.get('information_coefficient', 0):.3f}, "
                f"n={best_s.get('n', 0)}"
            )
        print()

    # Save results
    output_dir = Path("data/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{args.ticker}_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results.to_dict(), f, indent=2, default=str)

    print(f"  Results saved to: {output_file}")
    print()


if __name__ == "__main__":
    main()

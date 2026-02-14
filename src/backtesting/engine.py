"""
Backtesting Engine

For each signal type, calculates forward returns after the signal fired
and determines statistical significance of predictive power.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats

from ..models.base import SessionLocal
from ..models.market_data import StockPrice
from ..models.signal import SignalModel


@dataclass
class SignalTypeResult:
    """Backtest results for a single signal type across all forward windows."""

    signal_type: str
    category: str
    n_signals: int
    window_stats: Dict[int, dict] = field(default_factory=dict)
    # window_stats[window] = {hit_rate, avg_return, median_return, std_return,
    #                          t_stat, p_value, information_coefficient, ic_p_value}
    best_window: Optional[int] = None
    is_predictive: bool = False  # Any window with p < 0.05

    def summary_for_window(self, window: int) -> Optional[dict]:
        return self.window_stats.get(window)

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "category": self.category,
            "n_signals": self.n_signals,
            "window_stats": self.window_stats,
            "best_window": self.best_window,
            "is_predictive": self.is_predictive,
        }


@dataclass
class BacktestResults:
    """Complete backtest results for a ticker."""

    ticker: str
    date_range: Tuple[date, date]
    total_signals: int
    forward_windows: List[int]
    signal_results: Dict[str, SignalTypeResult]
    baseline_returns: Dict[int, dict]  # window -> {avg, median, std}

    def predictive_signals(self) -> List[SignalTypeResult]:
        return sorted(
            [r for r in self.signal_results.values() if r.is_predictive],
            key=lambda r: min(
                s.get("p_value", 1.0) for s in r.window_stats.values()
            ),
        )

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "date_range": [str(self.date_range[0]), str(self.date_range[1])],
            "total_signals": self.total_signals,
            "forward_windows": self.forward_windows,
            "signal_results": {k: v.to_dict() for k, v in self.signal_results.items()},
            "baseline_returns": self.baseline_returns,
        }


class BacktestEngine:
    """Backtests signal predictive power against forward stock returns."""

    def __init__(self):
        self.session = SessionLocal()

    def run_backtest(
        self,
        ticker: str,
        forward_windows: List[int] = None,
        min_signals: int = 3,
    ) -> BacktestResults:
        if forward_windows is None:
            forward_windows = [1, 5, 20, 60]

        logger.info(f"Running backtest for {ticker}, windows={forward_windows}")

        # Load signals
        signals = (
            self.session.query(SignalModel)
            .filter(SignalModel.company_id == ticker)
            .order_by(SignalModel.timestamp)
            .all()
        )
        logger.info(f"Loaded {len(signals)} signals for {ticker}")

        # Load prices
        prices = (
            self.session.query(StockPrice)
            .filter(StockPrice.ticker == ticker)
            .order_by(StockPrice.date)
            .all()
        )
        logger.info(f"Loaded {len(prices)} daily prices for {ticker}")

        if not signals or not prices:
            raise ValueError(f"No data found for {ticker}")

        # Build price DataFrame indexed by date
        price_df = pd.DataFrame(
            [
                {
                    "date": p.date,
                    "close": p.adj_close if p.adj_close is not None else p.close,
                }
                for p in prices
            ]
        )
        price_df = price_df.sort_values("date").set_index("date")

        # Build signal DataFrame
        signal_records = []
        for s in signals:
            sig_date = s.timestamp.date() if hasattr(s.timestamp, "date") else s.timestamp
            signal_records.append(
                {
                    "date": sig_date,
                    "signal_type": s.signal_type,
                    "category": s.category,
                    "score": s.score,
                }
            )
        signal_df = pd.DataFrame(signal_records)

        # Calculate baseline returns
        baseline = self._calculate_baseline(price_df, forward_windows)
        logger.info(f"Baseline returns calculated")

        # Group signals by type and calculate stats
        signal_results = {}
        grouped = signal_df.groupby("signal_type")

        for signal_type, group in grouped:
            if len(group) < min_signals:
                logger.debug(
                    f"Skipping {signal_type}: only {len(group)} signals (min={min_signals})"
                )
                continue

            category = group["category"].iloc[0]
            result = self._analyze_signal_type(
                signal_type, category, group, price_df, forward_windows
            )
            if result is not None:
                signal_results[signal_type] = result

        date_range = (price_df.index.min(), price_df.index.max())

        logger.info(
            f"Backtest complete: {len(signal_results)} signal types analyzed, "
            f"{sum(1 for r in signal_results.values() if r.is_predictive)} predictive"
        )

        return BacktestResults(
            ticker=ticker,
            date_range=date_range,
            total_signals=len(signals),
            forward_windows=forward_windows,
            signal_results=signal_results,
            baseline_returns=baseline,
        )

    def _calculate_baseline(
        self, price_df: pd.DataFrame, forward_windows: List[int]
    ) -> Dict[int, dict]:
        """Calculate average forward returns for any random day."""
        baseline = {}
        closes = price_df["close"].values
        dates = price_df.index.values

        for window in forward_windows:
            returns = []
            for i in range(len(closes) - window):
                ret = (closes[i + window] - closes[i]) / closes[i]
                returns.append(ret)

            if returns:
                arr = np.array(returns)
                baseline[window] = {
                    "avg": float(np.mean(arr)),
                    "median": float(np.median(arr)),
                    "std": float(np.std(arr)),
                    "n": len(returns),
                }
            else:
                baseline[window] = {"avg": 0.0, "median": 0.0, "std": 0.0, "n": 0}

        return baseline

    def _analyze_signal_type(
        self,
        signal_type: str,
        category: str,
        group: pd.DataFrame,
        price_df: pd.DataFrame,
        forward_windows: List[int],
    ) -> Optional[SignalTypeResult]:
        """Analyze a single signal type's predictive power."""
        price_dates = price_df.index
        window_stats = {}
        any_predictive = False
        best_window = None
        best_p = 1.0

        for window in forward_windows:
            forward_returns = []
            scores = []

            for _, row in group.iterrows():
                sig_date = row["date"]

                # Find the closest trading day on or after signal date
                entry_idx = price_dates.searchsorted(sig_date, side="left")
                if entry_idx >= len(price_dates):
                    continue

                exit_idx = entry_idx + window
                if exit_idx >= len(price_dates):
                    continue

                entry_price = price_df.iloc[entry_idx]["close"]
                exit_price = price_df.iloc[exit_idx]["close"]
                ret = (exit_price - entry_price) / entry_price

                forward_returns.append(ret)
                scores.append(row["score"])

            if len(forward_returns) < 2:
                continue

            returns_arr = np.array(forward_returns)
            scores_arr = np.array(scores)

            # Basic stats
            avg_ret = float(np.mean(returns_arr))
            median_ret = float(np.median(returns_arr))
            std_ret = float(np.std(returns_arr, ddof=1)) if len(returns_arr) > 1 else 0.0

            # Hit rate: % of positive returns (signal assumed bullish if score > 0)
            # For negative scores, flip the expected direction
            hits = 0
            for ret, score in zip(forward_returns, scores):
                if score > 0 and ret > 0:
                    hits += 1
                elif score < 0 and ret < 0:
                    hits += 1
                elif score == 0:
                    pass  # neutral, don't count
            non_neutral = sum(1 for s in scores if s != 0)
            hit_rate = hits / non_neutral if non_neutral > 0 else 0.0

            # t-test: are returns significantly different from zero?
            t_stat, p_value = stats.ttest_1samp(returns_arr, 0.0)
            t_stat = float(t_stat)
            p_value = float(p_value)

            # Information coefficient: Spearman rank correlation between score and return
            ic, ic_p = stats.spearmanr(scores_arr, returns_arr)
            ic = float(ic) if not np.isnan(ic) else 0.0
            ic_p = float(ic_p) if not np.isnan(ic_p) else 1.0

            # Sharpe-like ratio
            sharpe = avg_ret / std_ret if std_ret > 0 else 0.0

            stat = {
                "n": len(forward_returns),
                "hit_rate": round(hit_rate, 4),
                "avg_return": round(avg_ret, 6),
                "median_return": round(median_ret, 6),
                "std_return": round(std_ret, 6),
                "t_stat": round(t_stat, 4),
                "p_value": round(p_value, 6),
                "information_coefficient": round(ic, 4),
                "ic_p_value": round(ic_p, 6),
                "sharpe": round(sharpe, 4),
            }
            window_stats[window] = stat

            if p_value < 0.05:
                any_predictive = True
            if p_value < best_p:
                best_p = p_value
                best_window = window

        if not window_stats:
            return None

        return SignalTypeResult(
            signal_type=signal_type,
            category=category,
            n_signals=len(group),
            window_stats=window_stats,
            best_window=best_window,
            is_predictive=any_predictive,
        )

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

"""
Correlation Engine

Discovers relationships between signals:
1. Which signals predict others (lead-lag analysis)
2. Which signals move together (correlation)
3. Statistical significance testing
4. Leading indicator identification
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

import numpy as np
from scipy import stats
from loguru import logger

from ..models.base import SessionLocal
from ..models.signal import SignalModel
from ..core.company import Company


class CorrelationResult:
    """Result of correlation analysis between two signals"""

    def __init__(
        self,
        signal_a: str,
        signal_b: str,
        correlation: float,
        p_value: float,
        lag: int,  # Number of periods signal_a leads signal_b
        n_observations: int,
    ):
        self.signal_a = signal_a
        self.signal_b = signal_b
        self.correlation = correlation
        self.p_value = p_value
        self.lag = lag
        self.n_observations = n_observations

    @property
    def is_significant(self) -> bool:
        """Is correlation statistically significant? (p < 0.05)"""
        return self.p_value < 0.05

    @property
    def strength(self) -> str:
        """Describe correlation strength"""
        abs_corr = abs(self.correlation)
        if abs_corr > 0.7:
            return "strong"
        elif abs_corr > 0.4:
            return "moderate"
        elif abs_corr > 0.2:
            return "weak"
        else:
            return "negligible"

    @property
    def direction(self) -> str:
        """Positive or negative correlation"""
        return "positive" if self.correlation > 0 else "negative"

    def __str__(self):
        lag_str = f"leads by {self.lag} periods" if self.lag > 0 else "contemporaneous"
        sig_str = "SIGNIFICANT" if self.is_significant else "not significant"

        return (
            f"{self.signal_a} → {self.signal_b}: "
            f"{self.correlation:+.3f} ({self.strength} {self.direction}, {lag_str}) "
            f"[{sig_str}, p={self.p_value:.4f}, n={self.n_observations}]"
        )


class CorrelationEngine:
    """Analyze correlations and lead-lag relationships between signals"""

    def __init__(self):
        self.session = SessionLocal()

    def analyze_company(
        self,
        company: Company,
        max_lag: int = 4,  # Test up to 4 quarters lag
        min_observations: int = 8,  # Need at least 8 data points
    ) -> List[CorrelationResult]:
        """
        Analyze all signal correlations for a company.

        Args:
            company: Company to analyze
            max_lag: Maximum number of periods to test for lead-lag
            min_observations: Minimum number of overlapping observations required

        Returns:
            List of significant correlation results
        """
        logger.info(f"Analyzing signal correlations for {company.ticker}")

        # Fetch all signals for this company
        signals = self.session.query(SignalModel).filter(
            SignalModel.company_id == company.id
        ).order_by(SignalModel.timestamp).all()

        logger.info(f"Fetched {len(signals)} total signals")

        # Group signals by type into time series
        signal_series = self._create_time_series(signals)

        # Analyze all pairs
        results = []
        signal_types = list(signal_series.keys())

        for i, signal_a in enumerate(signal_types):
            for signal_b in signal_types[i+1:]:  # Avoid duplicate pairs
                # Test different lags
                for lag in range(0, max_lag + 1):
                    result = self._test_correlation(
                        signal_a,
                        signal_b,
                        signal_series[signal_a],
                        signal_series[signal_b],
                        lag=lag,
                        min_observations=min_observations,
                    )

                    if result and result.is_significant:
                        results.append(result)

        # Sort by correlation strength (absolute value)
        results.sort(key=lambda r: abs(r.correlation), reverse=True)

        logger.info(f"Found {len(results)} significant correlations")

        return results

    def _create_time_series(self, signals: List[SignalModel]) -> Dict[str, List[Tuple[datetime, float]]]:
        """
        Convert signals into time series by signal type.

        Returns:
            Dict mapping signal_type -> [(timestamp, score), ...]
        """
        series = defaultdict(list)

        for signal in signals:
            if signal.score is not None:
                series[signal.signal_type].append((signal.timestamp, signal.score))

        # Sort each series by timestamp
        for signal_type in series:
            series[signal_type].sort(key=lambda x: x[0])

        return dict(series)

    def _test_correlation(
        self,
        signal_a_name: str,
        signal_b_name: str,
        series_a: List[Tuple[datetime, float]],
        series_b: List[Tuple[datetime, float]],
        lag: int = 0,
        min_observations: int = 8,
    ) -> Optional[CorrelationResult]:
        """
        Test correlation between two time series with optional lag.

        Args:
            signal_a_name: Name of first signal
            signal_b_name: Name of second signal
            series_a: Time series [(timestamp, value), ...]
            series_b: Time series [(timestamp, value), ...]
            lag: Number of periods signal_a leads signal_b (0 = contemporaneous)
            min_observations: Minimum overlapping observations required

        Returns:
            CorrelationResult if enough observations, else None
        """
        # Align time series with lag
        aligned_a, aligned_b = self._align_series(series_a, series_b, lag=lag)

        if len(aligned_a) < min_observations:
            return None

        # Calculate Pearson correlation
        correlation, p_value = stats.pearsonr(aligned_a, aligned_b)

        return CorrelationResult(
            signal_a=signal_a_name,
            signal_b=signal_b_name,
            correlation=correlation,
            p_value=p_value,
            lag=lag,
            n_observations=len(aligned_a),
        )

    def _align_series(
        self,
        series_a: List[Tuple[datetime, float]],
        series_b: List[Tuple[datetime, float]],
        lag: int = 0,
    ) -> Tuple[List[float], List[float]]:
        """
        Align two time series with optional lag.

        Args:
            series_a: First time series
            series_b: Second time series
            lag: Number of periods to shift series_a forward (positive = series_a leads)

        Returns:
            (aligned_values_a, aligned_values_b)
        """
        # Create dictionaries for easier lookup
        dict_a = {ts: val for ts, val in series_a}
        dict_b = {ts: val for ts, val in series_b}

        # Get all unique timestamps
        timestamps_a = sorted(dict_a.keys())
        timestamps_b = sorted(dict_b.keys())

        aligned_a = []
        aligned_b = []

        # For each timestamp in series_a, find matching timestamp in series_b with lag
        for i, ts_a in enumerate(timestamps_a):
            # Apply lag: if lag=1, we want ts_a to match with the NEXT timestamp in series_b
            if lag > 0:
                # series_a leads, so look ahead in series_b
                target_idx = i + lag
                if target_idx < len(timestamps_b):
                    ts_b = timestamps_b[target_idx]
                    if ts_b in dict_b:
                        aligned_a.append(dict_a[ts_a])
                        aligned_b.append(dict_b[ts_b])
            elif lag < 0:
                # series_b leads, so look behind in series_b
                target_idx = i + lag
                if 0 <= target_idx < len(timestamps_b):
                    ts_b = timestamps_b[target_idx]
                    if ts_b in dict_b:
                        aligned_a.append(dict_a[ts_a])
                        aligned_b.append(dict_b[ts_b])
            else:
                # Contemporaneous (lag=0)
                if ts_a in dict_b:
                    aligned_a.append(dict_a[ts_a])
                    aligned_b.append(dict_b[ts_a])

        return aligned_a, aligned_b

    def find_leading_indicators(
        self,
        company: Company,
        target_signal: str,
        max_lag: int = 4,
        min_correlation: float = 0.5,
    ) -> List[CorrelationResult]:
        """
        Find signals that predict a target signal.

        Args:
            company: Company to analyze
            target_signal: Signal type to predict (e.g., "revenue_growth_qoq")
            max_lag: Maximum lead time to test
            min_correlation: Minimum correlation strength

        Returns:
            List of leading indicators sorted by correlation strength
        """
        logger.info(f"Finding leading indicators for {target_signal}")

        results = self.analyze_company(company, max_lag=max_lag)

        # Filter for signals that predict target
        leading = [
            r for r in results
            if r.signal_b == target_signal
            and r.lag > 0  # Must lead (not contemporaneous)
            and abs(r.correlation) >= min_correlation
        ]

        return leading

    def generate_correlation_matrix(
        self,
        company: Company,
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate correlation matrix for all signal types.

        Returns:
            Dict of dict: matrix[signal_a][signal_b] = correlation coefficient
        """
        results = self.analyze_company(company, max_lag=0)  # Contemporaneous only

        # Build matrix
        matrix = defaultdict(dict)

        for result in results:
            matrix[result.signal_a][result.signal_b] = result.correlation
            matrix[result.signal_b][result.signal_a] = result.correlation  # Symmetric

        return dict(matrix)

    def close(self):
        """Close database session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Quick test
    from ..core.company import get_registry

    registry = get_registry()
    uber = registry.get("UBER")

    with CorrelationEngine() as engine:
        results = engine.analyze_company(uber, max_lag=2)

        print(f"\nFound {len(results)} significant correlations:\n")
        for result in results[:10]:  # Top 10
            print(result)

        # Find leading indicators for revenue growth
        print(f"\n\nLeading indicators for revenue_growth_qoq:\n")
        leading = engine.find_leading_indicators(uber, "revenue_growth_qoq")
        for result in leading:
            print(result)

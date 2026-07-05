"""
Crypto pair correlation matrix — rolling correlation + portfolio overlap.

Purpose
-------
Crypto pairs are correlated regimes, not independent bets. When the batch
runner enters positions on BTC, ETH, and SOL simultaneously, those are not
three independent trades — they're three expressions of the same macro move.
This module quantifies that overlap so the risk layer can compress position
sizes or skip redundant entries.

Output
------
``CorrelationResult`` with an N×N matrix (pair × pair, Pearson r on
close-to-close returns over a rolling window), plus a ``portfolio_overlap()``
check that flags concentrated positions above a configurable threshold.

Usage
-----
    from backtesting.engine.correlation import (
        CorrelationConfig, CorrelationMatrix,
    )

    engine = CorrelationMatrix(CorrelationConfig(tf="60", lookback_bars=720))
    result = engine.compute(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    result.matrix               # 3×3 DataFrame
    result.avg_correlation      # float
    result.high_corr_pairs      # list of (a, b, r) tuples

    overlap = engine.portfolio_overlap(["BTCUSDT", "ETHUSDT"], result.matrix)
    overlap["mean_correlation"] # float
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data


@dataclass
class CorrelationConfig:
    """Configuration for correlation computation.

    Defaults tuned for 1h crypto data. Adjust ``lookback_bars`` and ``tf``
    to the strategy's holding period.
    """

    # Timeframe to align all pairs on
    tf: str = "60"  # 1h candles

    # Rolling window (in bars on ``tf``)
    lookback_bars: int = 720  # 30 days at 1h

    # Minimum valid bars after alignment for a pair to appear in the matrix
    min_bars: int = 100

    # Pairs with |r| above this are flagged as high-correlation
    high_corr_threshold: float = 0.70

    # Exchange to load data from
    exchange: str = "binance"


@dataclass
class CorrelationResult:
    """Output from ``CorrelationMatrix.compute()``."""
    matrix: pd.DataFrame        # N×N correlation matrix (pair × pair)
    returns: pd.DataFrame       # T×N aligned returns (timestamp × pair)
    n_bars: int                 # number of bars used in the matrix
    pair_info: dict[str, dict]  # per-pair metadata
    avg_correlation: float      # mean absolute off-diagonal correlation
    high_corr_pairs: list[tuple[str, str, float]]  # pairs above threshold


class CorrelationMatrix:
    """Rolling pairwise correlation engine for crypto pairs.

    Stateless: call ``compute()`` with a list of symbols and get a matrix.
    Safe to call multiple times with different sets of pairs.

    The ``portfolio_overlap()`` helper takes a list of active positions and
    a correlation matrix, returning summary stats for that subset.
    """

    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or CorrelationConfig()

    def compute(
        self,
        pairs: list[str],
        exchange: Optional[str] = None,
    ) -> CorrelationResult:
        """Compute rolling correlation matrix for a set of pairs.

        Parameters
        ----------
        pairs : list of str
            Crypto symbols (e.g. ``["BTCUSDT", "ETHUSDT"]``).
        exchange : str or None
            Override config exchange if provided.

        Returns
        -------
        CorrelationResult
        """
        ex = exchange or self.config.exchange
        lookback = self.config.lookback_bars
        tf = self.config.tf

        # ── Load and align close prices ──
        aligned_closes: dict[str, pd.Series] = {}
        pair_info: dict[str, dict] = {}

        for pair in pairs:
            df = load_data(pair, tf=tf, exchange=ex)
            if df.empty:
                pair_info[pair] = {"bars": 0, "min_ts": None, "max_ts": None,
                                   "status": "no_data"}
                continue

            ts = pd.to_datetime(df["ts"], utc=True)
            aligned_closes[pair] = pd.Series(
                df["close"].values, index=ts, name=pair,
            ).sort_index()
            pair_info[pair] = {
                "bars": len(df),
                "min_ts": str(ts.min()),
                "max_ts": str(ts.max()),
                "status": "loaded",
            }

        if not aligned_closes:
            raise ValueError(f"No data loaded for any pair in {pairs} on {ex}")

        # ── Align to common timestamp grid (inner join) ──
        close_df: pd.DataFrame = pd.concat(
            aligned_closes.values(), axis=1, join="inner",
        )
        close_df.columns = list(aligned_closes.keys())

        if close_df.empty or len(close_df) < self.config.min_bars:
            min_available = len(close_df)
            raise ValueError(
                f"Insufficient aligned bars ({min_available}) for pairs {pairs}. "
                f"Need >= {self.config.min_bars}. Try a lower tf or longer date range."
            )

        n_bars = len(close_df)

        # ── Compute close-to-close returns ──
        returns = close_df.pct_change().dropna(how="all")
        returns = returns.replace([np.inf, -np.inf], np.nan)

        # ── Check bars after computing returns ──
        if len(returns) < lookback:
            # Not enough data for the full rolling window — use all available
            lookback = len(returns)
        if lookback < self.config.min_bars:
            raise ValueError(
                f"Returns series too short ({len(returns)} bars) for "
                f"lookback_bars={self.config.lookback_bars}. "
                f"Need at least {self.config.min_bars} bars after pct_change."
            )

        # ── Rolling correlation (last ``lookback`` bars) ──
        recent = returns.iloc[-lookback:]
        matrix = recent.corr()

        # Pair-level stats
        dropped: list[str] = []
        for pair in pairs:
            if pair not in matrix.columns:
                dropped.append(pair)

        # ── Summary statistics ──
        n_pairs = len(matrix)
        if n_pairs < 2:
            avg_corr = 0.0
        else:
            off_diag = matrix.where(
                ~np.eye(n_pairs, dtype=bool), other=np.nan,
            )
            vals = off_diag.stack().dropna()
            avg_corr = float(vals.mean()) if not vals.empty else 0.0

        high_corr = []
        for i, pair_a in enumerate(matrix.columns):
            for pair_b in matrix.columns[i + 1:]:
                r = matrix.loc[pair_a, pair_b]
                if not np.isnan(r) and abs(r) >= self.config.high_corr_threshold:
                    high_corr.append((pair_a, pair_b, float(r)))

        return CorrelationResult(
            matrix=matrix,
            returns=returns,
            n_bars=n_bars,
            pair_info=pair_info,
            avg_correlation=avg_corr,
            high_corr_pairs=high_corr,
        )

    # ── Portfolio overlap ──────────────────────────────────────────────

    def portfolio_overlap(
        self,
        active_positions: list[str],
        matrix: pd.DataFrame,
    ) -> dict:
        """Analyze correlation within a set of active positions.

        Parameters
        ----------
        active_positions : list of str
            Symbols currently held.
        matrix : pd.DataFrame
            Correlation matrix from ``compute()``.

        Returns
        -------
        dict with keys:
            - pairs: list of active pairs found in the matrix
            - missing: pairs not found in the matrix
            - mean_correlation: mean off-diagonal |r| for the subset
            - max_correlation: maximum off-diagonal |r|
            - high_corr_pairs: list of (a, b, r) tuples above threshold
            - effective_count: diversification-adjusted count
              (1 + n_pairs * (1 - mean_correlation))
        """
        found = [p for p in active_positions if p in matrix.columns]
        missing = [p for p in active_positions if p not in matrix.columns]

        if len(found) < 2:
            return {
                "pairs": found,
                "missing": missing,
                "mean_correlation": 0.0,
                "max_correlation": 0.0,
                "high_corr_pairs": [],
                "effective_count": float(len(found)),
            }

        subset = matrix.loc[found, found]
        off_diag = subset.where(
            ~np.eye(len(subset), dtype=bool), other=np.nan,
        )
        vals = off_diag.stack().dropna().abs()
        mean_corr = float(vals.mean()) if not vals.empty else 0.0
        max_corr = float(vals.max()) if not vals.empty else 0.0

        high = []
        for i, a in enumerate(found):
            for b in found[i + 1:]:
                r = subset.loc[a, b]
                if not np.isnan(r) and abs(r) >= self.config.high_corr_threshold:
                    high.append((a, b, float(r)))

        # Effective count: how many "independent" bets in the active set
        # Range: 1 (perfect correlation) to n_pairs (zero correlation)
        eff = 1.0 + len(found) * (1.0 - mean_corr)

        return {
            "pairs": found,
            "missing": missing,
            "mean_correlation": mean_corr,
            "max_correlation": max_corr,
            "high_corr_pairs": high,
            "effective_count": round(eff, 2),
        }

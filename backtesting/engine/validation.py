"""
Regime-stratified validation for backtest results.

Extends ``rolling_validate()`` by classifying each rolling window's dominant
regime and reporting per-regime performance separately. This exposes regime-
contingent behavior that calendar-only averaging hides.

Usage
-----
    from backtesting.engine.validation import regime_stratified_validate

    result = regime_stratified_validate(
        trades=backtest_result.to_df(),
        ohlcv=hourly_data,            # DataFrame with ts, high, low, close
        window_days=60, step_days=10,
    )
    print(result.by_regime["trend_up"].summary())
    print(f"Consistency: {result.regime_consistency:.0%}")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.crypto.validation import RollingValidation, WindowStats
from backtesting.engine.regime import MarketRegime, RegimeConfig, REGIME_LABELS


@dataclass
class RegimeStratifiedValidation:
    """Validation results stratified by market regime.

    Attributes
    ----------
    overall : RollingValidation
        Standard calendar-based validation (for reference / comparison).
    by_regime : dict[str, RollingValidation]
        Per-regime results. Keys are regime labels.
    regime_distribution : dict[str, int]
        Number of windows where each regime was dominant.
    dominant_regime : str
        Most common regime across all windows.
    regime_consistency : float
        0.0 to 1.0 — fraction of regimes (with >= min_regime_windows)
        that are profitable. 1.0 = works in all regimes, 0.0 = only in one.
    n_regimes_with_data : int
        How many regimes had enough windows for a meaningful result.
    """

    overall: RollingValidation
    by_regime: dict[str, RollingValidation] = field(repr=False)
    regime_distribution: dict[str, int] = field(repr=False)
    dominant_regime: str = ""
    regime_consistency: float = 0.0
    n_regimes_with_data: int = 0

    def summary(self) -> str:
        """Multi-line summary of regime-stratified validation."""
        lines = [
            f"Regime-stratified validation: {self.overall.n_windows} windows",
            f"  Dominant regime: {self.dominant_regime}",
            f"  Regime distribution: {self.regime_distribution}",
            f"  Regime consistency: {self.regime_consistency:.0%} "
            f"({self.n_regimes_with_data} regimes with data)",
            "",
            "  Overall:",
            f"    {self.overall.summary().split(chr(10))[1]}",
            "",
            "  By regime:",
        ]
        for regime in REGIME_LABELS:
            if regime == "insufficient_data":
                continue
            rv = self.by_regime.get(regime)
            if rv is None or rv.n_windows == 0:
                continue
            n = rv.n_windows
            prof = rv.n_profitable
            pf = rv.median_pf
            dd = rv.median_max_dd_pct
            ret = rv.median_return_pct
            pct = f"{prof}/{n}"
            lines.append(
                f"    {regime:<15}  {pct:>7} profitable  "
                f"PF={pf:<6.2f}  ret={ret:>+.1%}  DD={dd:.1%}"
            )
        return "\n".join(lines)


def regime_stratified_validate(
    trades: pd.DataFrame,
    ohlcv: pd.DataFrame,
    window_days: int = 60,
    step_days: int = 10,
    min_trades: int = 3,
    initial_equity: float | None = None,
    regime_config: Optional[RegimeConfig] = None,
    min_regime_windows: int = 3,
) -> RegimeStratifiedValidation:
    """Rolling window validation stratified by market regime.

    For each calendar window, determines the dominant market regime (most
    frequent regime label among the OHLCV bars within that window), then
    groups window results by regime. Returns both the overall
    ``RollingValidation`` and per-regime breakdowns.

    Parameters
    ----------
    trades : pd.DataFrame
        From ``BacktestResult.to_df()``. Must have ``exit_time``, ``pnl``,
        and optionally ``r_multiple`` columns.
    ohlcv : pd.DataFrame
        OHLCV data covering (at least) the same date range as trades.
        Must have ``ts``, ``high``, ``low``, ``close`` columns.
        Same timeframe as the entry TF used in the backtest.
    window_days : int
        Length of each rolling window in calendar days.
    step_days : int
        Advance between window starts.
    min_trades : int
        Minimum trades in a window to include it in stats.
    initial_equity : float or None
        Baseline for return% and DD% calculations.
    regime_config : RegimeConfig or None
        Configuration passed to ``MarketRegime``.
    min_regime_windows : int
        Minimum number of windows assigned to a regime for it to be
        counted in ``regime_consistency``.

    Returns
    -------
    RegimeStratifiedValidation
    """
    if ohlcv.empty:
        raise ValueError("ohlcv DataFrame is empty — cannot compute regimes")

    rc = regime_config or RegimeConfig()
    classifier = MarketRegime(rc)

    # ── Compute regime labels for the OHLCV ──
    labels, _ = classifier.compute(ohlcv)

    # Build a Series: timestamp → regime label
    ts = pd.to_datetime(ohlcv["ts"], utc=True)
    regime_at = pd.Series(labels, index=ts, name="regime").sort_index()

    # ── Rolling windows ──
    if trades.empty:
        empty = RollingValidation(
            n_windows=0, n_with_trades=0, n_profitable=0, windows=[],
        )
        return RegimeStratifiedValidation(
            overall=empty, by_regime={}, regime_distribution={},
            dominant_regime="", regime_consistency=0.0, n_regimes_with_data=0,
        )

    tr = trades.sort_values("exit_time").reset_index(drop=True)
    tr["exit_time"] = pd.to_datetime(tr["exit_time"])
    first_day = tr["exit_time"].min().normalize()
    last_day = tr["exit_time"].max().normalize()

    # ── Classify each calendar window ──
    # Bucket: dominant regime → list of WindowStats
    regime_windows: dict[str, list[WindowStats]] = {}
    all_windows: list[WindowStats] = []

    current = first_day
    while current + pd.Timedelta(days=window_days) <= last_day:
        end = current + pd.Timedelta(days=window_days)
        w = tr[(tr["exit_time"] >= current) & (tr["exit_time"] < end)].copy()
        if len(w) < min_trades:
            current += pd.Timedelta(days=step_days)
            continue

        # ── Compute window stats (same logic as rolling_validate) ──
        pnl = w["pnl"].values
        n = len(pnl)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        n_wins = len(wins)
        n_losses = len(losses)
        total_pnl = float(pnl.sum())
        gross_win = float(wins.sum()) if n_wins > 0 else 0.0
        gross_loss = float(abs(losses.sum())) if n_losses > 0 else 0.0
        profit_factor = (
            gross_win / gross_loss if gross_loss > 0
            else (float("inf") if gross_win > 0 else 0.0)
        )
        win_rate = n_wins / n if n > 0 else 0.0
        avg_r = float(w["r_multiple"].mean()) if "r_multiple" in w.columns else 0.0
        cum = np.cumsum(pnl)

        if initial_equity is not None and initial_equity > 0:
            eq_curve = np.full(n, initial_equity)
            eq_curve[1:] = initial_equity + np.cumsum(pnl)[:-1]
            dd = np.maximum.accumulate(eq_curve) - eq_curve
            max_dd_pct = (
                float(dd.max()) / float(np.maximum.accumulate(eq_curve).max())
                if len(eq_curve) > 0 else 0.0
            )
            return_pct = total_pnl / initial_equity
        else:
            peak = np.maximum.accumulate(cum)
            dd = peak - cum
            max_dd_val = float(dd.max())
            max_dd_pct = (
                max_dd_val / (peak[-1] + abs(max_dd_val) + 1e-9)
                if peak[-1] > 0 else 0.0
            )
            return_pct = 0.0

        ws = WindowStats(
            start=current, end=end, trades=n,
            profit_factor=profit_factor, win_rate=win_rate,
            avg_r=avg_r, total_return_pct=return_pct,
            max_dd_pct=max_dd_pct, total_pnl=total_pnl,
        )
        all_windows.append(ws)

        # ── Determine dominant regime in this window ──
        ohlcv_in_window = regime_at[
            (regime_at.index >= current) & (regime_at.index < end)
        ]
        # Strip insufficient_data — they pad the edges
        valid = ohlcv_in_window[ohlcv_in_window != "insufficient_data"]
        if valid.empty:
            # Assign to "insufficient_data" bucket
            regime_windows.setdefault("insufficient_data", []).append(ws)
            current += pd.Timedelta(days=step_days)
            continue

        dominant = valid.mode()
        dominant_regime = str(dominant.iloc[0]) if not dominant.empty else "unknown"
        regime_windows.setdefault(dominant_regime, []).append(ws)

        current += pd.Timedelta(days=step_days)

    # ── Build RollingValidation per regime ──
    overall = _build_rolling_validation(all_windows, min_trades, initial_equity)
    by_regime: dict[str, RollingValidation] = {}
    for regime, win_list in regime_windows.items():
        by_regime[regime] = _build_rolling_validation(
            win_list, min_trades, initial_equity,
        )

    # ── Distribution ──
    dist = {r: len(v) for r, v in regime_windows.items()}
    dominant_regime = max(dist, key=dist.get) if dist else ""

    # ── Regime consistency: fraction of regimes that are profitable ──
    regimes_with_data = [
        r for r in by_regime
        if r not in ("insufficient_data", "unknown")
        and by_regime[r].n_windows >= min_regime_windows
    ]
    regimes_profitable = [
        r for r in regimes_with_data
        if by_regime[r].n_profitable > 0
        and by_regime[r].median_pf > 1.0
    ]
    n_rd = len(regimes_with_data)
    consistency = len(regimes_profitable) / n_rd if n_rd > 0 else 0.0

    return RegimeStratifiedValidation(
        overall=overall,
        by_regime=by_regime,
        regime_distribution=dist,
        dominant_regime=dominant_regime,
        regime_consistency=consistency,
        n_regimes_with_data=n_rd,
    )


def _build_rolling_validation(
    windows: list[WindowStats],
    min_trades: int,
    initial_equity: float | None = None,
) -> RollingValidation:
    """Build a RollingValidation from a list of WindowStats.

    Mirrors the aggregation logic in ``backtesting.crypto.validation``.
    """
    n_win = len(windows)
    if n_win == 0:
        return RollingValidation(
            n_windows=0, n_with_trades=0, n_profitable=0, windows=[],
        )

    pfs = np.array([w.profit_factor for w in windows])
    wrs = np.array([w.win_rate for w in windows])
    avgr = np.array([w.avg_r for w in windows])
    rets = np.array([w.total_return_pct for w in windows])
    dds = np.array([w.max_dd_pct for w in windows])
    tcounts = np.array([w.trades for w in windows])

    finite_only = pfs[np.isfinite(pfs)]
    has_inf = np.any(~np.isfinite(pfs))
    if len(finite_only) > 0:
        median_pf = float(np.median(finite_only))
        if has_inf:
            median_pf = max(median_pf, float(np.max(finite_only)) * 1.5)
    elif has_inf:
        median_pf = float("inf")
    else:
        median_pf = 0.0

    profitable = (pfs > 1.0) & (rets > 0)
    positive_return = rets > 0

    return RollingValidation(
        n_windows=n_win,
        n_with_trades=sum(1 for tc in tcounts if tc >= min_trades),
        n_profitable=int(profitable.sum()),
        windows=windows,
        median_pf=median_pf,
        median_wr=float(np.median(wrs)),
        median_avg_r=float(np.median(avgr)),
        median_return_pct=float(np.median(rets)),
        median_max_dd_pct=float(np.median(dds)),
        median_trades=int(np.median(tcounts)),
        best_return_pct=float(np.max(rets)),
        worst_return_pct=float(np.min(rets)),
        best_pf=float(np.max(finite_only)) if len(finite_only) > 0 else (
            float("inf") if has_inf else 0.0
        ),
        worst_pf=float(np.min(finite_only)) if len(finite_only) > 0 else (
            float("inf") if has_inf else 0.0
        ),
        best_dd=float(np.min(dds)),
        worst_dd=float(np.max(dds)),
        frac_profitable=float(profitable.mean()),
        frac_positive_return=float(positive_return.mean()),
    )

"""
VectorBT-based TrIctSweep strategy.

Signal generation in Numba, portfolio simulation via vbt.Portfolio.from_signals.
Runs one param combo at a time for robustness, then reports best result.

Usage:
    from backtesting.strategies.vbt_tr_ict_sweep import VbtTrIctSweep
    result = VbtTrIctSweep.run(data_1m)
"""

from __future__ import annotations

from dataclasses import dataclass

import numba as nb
import numpy as np
import pandas as pd
import vectorbt as vbt

from backtesting.structure_lib.vbt_indicators import (
    SwingPoints, FVGInd,
)


@nb.njit
def _generate_signals_single(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    swings: np.ndarray, levels: np.ndarray,
    fvg_kind: np.ndarray, fvg_ce: np.ndarray,
    mss_bars: int, fvg_expiry_bars: int,
    sl_buffer_pips: float, tp1_r: float, pip_size: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate entry/sl/tp arrays for a single param combo.

    Returns: (entries, entry_prices, sl_prices, tp1_prices, labels, is_short)
    """
    n = high.shape[0]
    entries = np.zeros(n, dtype=np.bool_)
    entry_prices = np.full(n, np.nan)
    sl_prices = np.full(n, np.nan)
    tp1_prices = np.full(n, np.nan)
    labels = np.full(n, 0, dtype=np.int32)  # 1=long, -1=short
    is_short = np.zeros(n, dtype=np.bool_)

    # State
    pending_dir = 0      # 1=long, -1=short
    sweep_i = -1
    sweep_low_or_high = 0.0
    swing_target = 0.0
    fvg_ce_val = 0.0
    fvg_arm_i = -1

    for i in range(n):
        h = high[i, 0]
        l = low[i, 0]
        c = close[i, 0]
        fk = int(fvg_kind[i, 0])

        # ── Check pending entry fill ─────────────────────────────────────
        if pending_dir != 0:
            if i - fvg_arm_i > fvg_expiry_bars:
                pending_dir = 0
            elif pending_dir == 1 and l <= fvg_ce_val:
                # LONG fill: price pulled back into FVG CE
                entries[i] = True
                entry_prices[i] = min(c, fvg_ce_val)
                sl_prices[i] = sweep_low_or_high - sl_buffer_pips * pip_size
                stop = entry_prices[i] - sl_prices[i]
                if stop > 0:
                    tp1_prices[i] = entry_prices[i] + tp1_r * stop
                labels[i] = 1
                pending_dir = 0
            elif pending_dir == -1 and h >= fvg_ce_val:
                # SHORT fill
                entries[i] = True
                entry_prices[i] = max(c, fvg_ce_val)
                sl_prices[i] = sweep_low_or_high + sl_buffer_pips * pip_size
                stop = sl_prices[i] - entry_prices[i]
                if stop > 0:
                    tp1_prices[i] = entry_prices[i] - tp1_r * stop
                labels[i] = -1
                is_short[i] = True
                pending_dir = 0

        # ── Detect swing events ─────────────────────────────────────────
        sv = swings[i, 0]
        lv = levels[i, 0] if not np.isnan(levels[i, 0]) else 0.0

        if sv != 0 and pending_dir == 0:
            # Look back for opposite swing to sweep
            lo = max(0, i - 30)
            if sv == -1:  # Swing LOW → potential LONG setup
                # Was a swing HIGH swept recently?
                for j in range(lo, i):
                    if swings[j, 0] == 1:
                        sh_level = levels[j, 0]
                        # Check if price just swept through this swing high
                        if not np.isnan(sh_level) and h > sh_level and c < sh_level:
                            # Sweep of swing HIGH → bearish sweep → expect LONG
                            # Target: next swing HIGH for ChoCH
                            for j2 in range(j, i):
                                if swings[j2, 0] == -1:
                                    swing_target = levels[j2, 0]
                                    break
                            if swing_target == 0.0:
                                swing_target = l
                            sweep_i = i
                            sweep_low_or_high = h
                            # Now this is a SHORT setup target
                            # Wait for ChoCH below swing low
                            break
            elif sv == 1:  # Swing HIGH → potential SHORT setup
                for j in range(lo, i):
                    if swings[j, 0] == -1:
                        sl_level = levels[j, 0]
                        if not np.isnan(sl_level) and l < sl_level and c > sl_level:
                            # Sweep of swing LOW → bullish sweep → expect SHORT
                            for j2 in range(j, i):
                                if swings[j2, 0] == 1:
                                    swing_target = levels[j2, 0]
                                    break
                            if swing_target == 0.0:
                                swing_target = h
                            sweep_i = i
                            sweep_low_or_high = l
                            # Now this is a LONG setup target
                            break

        # ── Check for ChoCH (trend continuation after sweep) ────────────
        if sweep_i >= 0 and pending_dir == 0 and swing_target != 0.0:
            age = i - sweep_i
            if age > mss_bars:
                sweep_i = -1
                swing_target = 0.0
            elif c > swing_target and sweep_low_or_high > 0:
                # We want the SWEEP to be below... this logic needs work
                # Let me rethink the direction
                pass

    return entries, entry_prices, sl_prices, tp1_prices, labels, is_short


@nb.njit
def _gen_tr_ict_sweep(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    swings: np.ndarray, levels: np.ndarray,
    fvg_kind: np.ndarray, fvg_ce: np.ndarray,
    mss_bars_arr: np.ndarray, fvg_expiry_arr: np.ndarray,
    sl_buf_arr: np.ndarray, tp1_r_arr: np.ndarray,
    pip_size: float,
    entries: np.ndarray, entry_prices: np.ndarray,
    sl_prices: np.ndarray, tp1_prices: np.ndarray,
):
    """Run _generate_signals_single for each param column."""
    nk = entries.shape[1]
    for k in range(nk):
        e, ep, sp, tp = _generate_signals_single(
            high, low, close, swings[:, k:k+1], levels[:, k:k+1],
            fvg_kind[:, k:k+1], fvg_ce[:, k:k+1],
            mss_bars_arr[k], fvg_expiry_arr[k],
            sl_buf_arr[k], tp1_r_arr[k], pip_size,
        )[:4]
        entries[:, k] = e
        entry_prices[:, k] = ep
        sl_prices[:, k] = sp
        tp1_prices[:, k] = tp


@dataclass
class VbtTrIctSweepResult:
    trades: pd.DataFrame
    report: dict
    elapsed_s: float
    n_bars: int
    best_pf: vbt.Portfolio
    best_params: dict

    def summary(self) -> str:
        lines = [f"Bars: {self.n_bars:,}  |  Time: {self.elapsed_s:.2f}s"]
        if self.report:
            for k, v in self.report.items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def to_df(self) -> pd.DataFrame:
        return self.trades


class VbtTrIctSweep:
    """VectorBT-based TrIctSweep strategy runner."""

    DEFAULT_PARAMS = {
        "swing_n": [3, 5],
        "mss_bars": [5, 10, 20],
        "fvg_expiry_bars": [20, 40, 80],
        "sl_buffer_pips": [5, 10, 20],
        "tp1_r": [1.5, 2.0, 3.0],
    }

    @staticmethod
    def run(
        df: pd.DataFrame,
        param_grid: dict | None = None,
        initial_equity: float = 10_000.0,
        pip_size: float = 0.0001,
        fee: float = 0.0,
        size: float = 0.01,
    ) -> VbtTrIctSweepResult:
        import time
        from itertools import product

        t0 = time.perf_counter()
        if param_grid is None:
            param_grid = VbtTrIctSweep.DEFAULT_PARAMS

        n = len(df)
        high = df["high"].values.reshape(-1, 1)
        low = df["low"].values.reshape(-1, 1)
        close = df["close"].values.reshape(-1, 1)
        close_1d = df["close"].values

        # ── Compute indicators (once) ────────────────────────────────────
        sw = SwingPoints.run(
            high, low,
            left=param_grid.get("swing_n", [3]),
            right=param_grid.get("swing_n", [3]),
        )
        fvg = FVGInd.run(high, low, close,
                         left=[3], right=[3], min_gap_atr_mult=[0.01])

        # ── Build param grid ─────────────────────────────────────────────
        param_keys = ["mss_bars", "fvg_expiry_bars", "sl_buffer_pips", "tp1_r"]
        param_values = [param_grid.get(k, []) for k in param_keys]
        grid_vals = list(product(*param_values))
        n_params = len(grid_vals) if grid_vals else 1
        if not grid_vals:
            grid_vals = [(10, 40, 10, 2.0)]

        # ── Broadcast indicators to all param columns ────────────────────
        sw_arr = sw.swings.values  # [n, n_swing_params]
        lv_arr = sw.levels.values
        n_swing = sw_arr.shape[1]
        fvg_kind = fvg.kind.values  # [n, 1]
        fvg_ce = fvg.ce.values

        # Repeat swing columns if needed
        if n_swing < n_params:
            # Use first swing config for all param combos
            sw_rep = np.tile(sw_arr[:, 0:1], (1, n_params))
            lv_rep = np.tile(lv_arr[:, 0:1], (1, n_params))
        else:
            sw_rep = sw_arr[:, :n_params]
            lv_rep = lv_arr[:, :n_params]

        fvg_kind_rep = np.tile(fvg_kind, (1, n_params))
        fvg_ce_rep = np.tile(fvg_ce, (1, n_params))

        # ── Generate signals for all param combos ────────────────────────
        entries = np.zeros((n, n_params), dtype=np.bool_)
        entry_prices = np.full((n, n_params), np.nan)
        sl_prices = np.full((n, n_params), np.nan)
        tp1_prices = np.full((n, n_params), np.nan)

        _gen_tr_ict_sweep(
            high, low, close,
            sw_rep, lv_rep,
            fvg_kind_rep, fvg_ce_rep,
            np.array([g[0] for g in grid_vals], dtype=np.int32),
            np.array([g[1] for g in grid_vals], dtype=np.int32),
            np.array([g[2] for g in grid_vals], dtype=np.float64),
            np.array([g[3] for g in grid_vals], dtype=np.float64),
            pip_size, entries, entry_prices, sl_prices, tp1_prices,
        )

        # ── Run portfolio for each param combo (single-column) ──────────
        best_return = -np.inf
        best_pf = None
        best_params = {}
        all_trades = pd.DataFrame()

        for k in range(n_params):
            e_k = entries[:, k]
            if not e_k.any():
                continue

            sl_k = sl_prices[:, k]
            tp_k = tp1_prices[:, k]

            # Fill NaN SL/TP with non-triggering values
            sl_k = np.where(np.isnan(sl_k), 0.0, sl_k)
            tp_k = np.where(np.isnan(tp_k), np.inf, tp_k)

            pf_k = vbt.Portfolio.from_signals(
                close=close_1d,
                entries=e_k,
                direction="longonly",
                sl_stop=sl_k,
                tp_stop=tp_k,
                init_cash=initial_equity,
                size=size,
                fees=fee,
                freq="1min",
            )

            ret = pf_k.total_return() if hasattr(pf_k, 'total_return') else -np.inf
            if ret > best_return:
                best_return = ret
                best_pf = pf_k
                best_params = dict(zip(param_keys, grid_vals[k]))

        elapsed = time.perf_counter() - t0

        # Build report
        report = {}
        if best_pf is not None:
            try:
                s = best_pf.stats()
                if isinstance(s, pd.Series):
                    for k in ["Total Return", "Total Trades", "Win Rate",
                              "Max Drawdown", "Profit Factor"]:
                        if k in s.index:
                            report[k] = float(s[k]) if hasattr(s[k], 'item') else s[k]
            except Exception:
                pass

        # Trades DataFrame
        trades_df = pd.DataFrame()
        if best_pf is not None and hasattr(best_pf, 'trades'):
            try:
                trades_df = best_pf.trades.records_readable
            except Exception:
                pass

        return VbtTrIctSweepResult(
            trades=trades_df,
            report=report,
            elapsed_s=elapsed,
            n_bars=n,
            best_pf=best_pf,
            best_params=best_params,
        )
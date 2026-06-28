"""
VectorBT IndicatorFactory wrappers for structure_lib components.

All indicators use `from_custom_func` with Numba JIT and broadcast parameter
grids as columns. Manual concatenation to avoid `apply_and_concat_multiple_nb`
tuple compatibility issues.
"""

from __future__ import annotations

import numba as nb
import numpy as np
from vectorbt import IndicatorFactory as IF


# ── Swing Points ────────────────────────────────────────────────────────────────


@nb.njit
def _swing_points_nb(high: np.ndarray, low: np.ndarray, left: int, right: int):
    """Detect swings for one param set. Returns (swings, levels) as 2D [n, 1] arrays."""
    n = high.shape[0]
    swings = np.zeros((n, 1), dtype=np.int8)
    levels = np.full((n, 1), np.nan)

    for i in range(left, n - right):
        if high[i, 0] == np.max(high[i - left:i + right + 1, 0]):
            swings[i, 0] = 1
            levels[i, 0] = high[i, 0]
        elif low[i, 0] == np.min(low[i - left:i + right + 1, 0]):
            swings[i, 0] = -1
            levels[i, 0] = low[i, 0]

    # Resolve consecutive same-type (keep more extreme)
    positions = np.where(swings[:, 0] != 0)[0]
    if len(positions) >= 2:
        changed = True
        while changed:
            changed = False
            positions = np.where(swings[:, 0] != 0)[0]
            for idx in range(len(positions) - 1):
                p0, p1 = positions[idx], positions[idx + 1]
                if swings[p0, 0] == swings[p1, 0] == 1:
                    if high[p0, 0] >= high[p1, 0]:
                        swings[p1, 0] = 0
                        levels[p1, 0] = np.nan
                    else:
                        swings[p0, 0] = 0
                        levels[p0, 0] = np.nan
                    changed = True
                    break
                elif swings[p0, 0] == swings[p1, 0] == -1:
                    if low[p0, 0] <= low[p1, 0]:
                        swings[p1, 0] = 0
                        levels[p1, 0] = np.nan
                    else:
                        swings[p0, 0] = 0
                        levels[p0, 0] = np.nan
                    changed = True
                    break

    return swings, levels


@nb.njit
def _swing_custom(high: np.ndarray, low: np.ndarray, left: np.ndarray, right: np.ndarray):
    """Custom func for SwingPoints. Output shapes: [n, 1*n_params]."""
    n_params = len(left)
    n_bars = high.shape[0]
    out_swings = np.zeros((n_bars, n_params), dtype=np.int8)
    out_levels = np.full((n_bars, n_params), np.nan)

    for k in range(n_params):
        sw, lv = _swing_points_nb(high, low, left[k], right[k])
        out_swings[:, k] = sw[:, 0]
        out_levels[:, k] = lv[:, 0]

    return out_swings, out_levels


SwingPoints = IF(
    class_name="SwingPoints",
    input_names=["high", "low"],
    param_names=["left", "right"],
    output_names=["swings", "levels"],
).from_custom_func(_swing_custom)


# ── ATR helper ──────────────────────────────────────────────────────────────────


@nb.njit
def _atr_nb(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14):
    """ATR in Numba. Returns 2D [n, 1]."""
    n = high.shape[0]
    atr = np.full((n, 1), np.nan)
    if n < 2:
        return atr
    tr = np.zeros(n)
    for i in range(1, n):
        hl = high[i, 0] - low[i, 0]
        hc = abs(high[i, 0] - close[i - 1, 0])
        lc = abs(low[i, 0] - close[i - 1, 0])
        tr[i] = max(hl, hc, lc)
    atr[14 - 1, 0] = np.mean(tr[:14])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i, 0] = atr[i - 1, 0] * (1 - alpha) + tr[i] * alpha
    return atr


# ── FVG Detection ───────────────────────────────────────────────────────────────


@nb.njit
def _fvg_nb(high: np.ndarray, low: np.ndarray, atr: np.ndarray, min_gap_mult: float):
    """Detect FVGs for one param set. Returns (kind, top, bottom, ce) as [n,1] arrays."""
    n = high.shape[0]
    kind = np.zeros((n, 1), dtype=np.int8)
    top = np.full((n, 1), np.nan)
    bottom = np.full((n, 1), np.nan)
    ce_val = np.full((n, 1), np.nan)

    for i in range(2, n):
        min_gap = atr[i, 0] * min_gap_mult if atr[i, 0] > 0 else 0.0
        c1_h = high[i - 2, 0]; c1_l = low[i - 2, 0]
        c3_h = high[i, 0]; c3_l = low[i, 0]

        if c3_l > c1_h:
            gap = c3_l - c1_h
            if gap >= min_gap:
                kind[i, 0] = 1
                top[i, 0] = c3_l
                bottom[i, 0] = c1_h
                ce_val[i, 0] = (c3_l + c1_h) / 2.0
        elif c3_h < c1_l:
            gap = c1_l - c3_h
            if gap >= min_gap:
                kind[i, 0] = -1
                top[i, 0] = c1_l
                bottom[i, 0] = c3_h
                ce_val[i, 0] = (c1_l + c3_h) / 2.0

    return kind, top, bottom, ce_val


@nb.njit
def _fvg_custom(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                left: np.ndarray, right: np.ndarray, min_gap_atr_mult: np.ndarray):
    """Custom func for FVG."""
    n_params = len(left)
    n_bars = high.shape[0]
    out_kind = np.zeros((n_bars, n_params), dtype=np.int8)
    out_top = np.full((n_bars, n_params), np.nan)
    out_bottom = np.full((n_bars, n_params), np.nan)
    out_ce = np.full((n_bars, n_params), np.nan)

    atr = _atr_nb(high, low, close)

    for k in range(n_params):
        ki, tp, bt, cev = _fvg_nb(high, low, atr, min_gap_atr_mult[k])
        out_kind[:, k] = ki[:, 0]
        out_top[:, k] = tp[:, 0]
        out_bottom[:, k] = bt[:, 0]
        out_ce[:, k] = cev[:, 0]

    return out_kind, out_top, out_bottom, out_ce


FVGInd = IF(
    class_name="FVG",
    input_names=["high", "low", "close"],
    param_names=["left", "right", "min_gap_atr_mult"],
    output_names=["kind", "top", "bottom", "ce"],
).from_custom_func(_fvg_custom)


# ── Structure Labels (HH/HL/LH/LL + BOS/CHoCH) ──────────────────────────────────


@nb.njit
def _label_nb(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              swings: np.ndarray, levels: np.ndarray):
    """ICT labels for one param set. Returns 12 arrays of shape [n, 1]."""
    n = high.shape[0]
    label = np.zeros((n, 1), dtype=np.int8)
    trend = np.zeros((n, 1), dtype=np.int8)
    last_hh = np.full((n, 1), np.nan)
    last_hl = np.full((n, 1), np.nan)
    last_lh = np.full((n, 1), np.nan)
    last_ll = np.full((n, 1), np.nan)
    bull_bos = np.zeros((n, 1), dtype=np.bool_)
    bear_bos = np.zeros((n, 1), dtype=np.bool_)
    bull_choch = np.zeros((n, 1), dtype=np.bool_)
    bear_choch = np.zeros((n, 1), dtype=np.bool_)

    prev_sh = np.nan; prev_sl = np.nan
    _hh = np.nan; _hl = np.nan; _lh = np.nan; _ll = np.nan
    _trend = 0; bullish_count = 0; bearish_count = 0
    hh_broken = False; hl_broken = False; lh_broken = False; ll_broken = False

    for i in range(n):
        if i > 0:
            trend[i, 0] = trend[i - 1, 0]
            last_hh[i, 0] = last_hh[i - 1, 0]
            last_hl[i, 0] = last_hl[i - 1, 0]
            last_lh[i, 0] = last_lh[i - 1, 0]
            last_ll[i, 0] = last_ll[i - 1, 0]

        sv = swings[i, 0]; did_choch = False
        is_bear_choch = False; is_bull_choch = False

        if sv != 0:
            lv = levels[i, 0]
            if sv == 1:
                label[i, 0] = 1 if (np.isnan(prev_sh) or lv > prev_sh) else 3
                prev_sh = lv
            else:
                label[i, 0] = 2 if (np.isnan(prev_sl) or lv > prev_sl) else 4
                prev_sl = lv

        lbl = label[i, 0]
        if lbl == 1: _hh = lv; hh_broken = False
        elif lbl == 2: _hl = lv; hl_broken = False
        elif lbl == 3 and _trend in (0, -1): _lh = lv; lh_broken = False
        elif lbl == 4 and _trend in (0, -1): _ll = lv; ll_broken = False

        if _trend == 1:
            if not hh_broken and not np.isnan(_hh) and close[i, 0] > _hh:
                bull_bos[i, 0] = True; hh_broken = True
            if not hl_broken and not np.isnan(_hl) and close[i, 0] < _hl:
                bear_choch[i, 0] = True; hl_broken = True; is_bear_choch = True; did_choch = True
        elif _trend == -1:
            if not ll_broken and not np.isnan(_ll) and close[i, 0] < _ll:
                bear_bos[i, 0] = True; ll_broken = True
            if not lh_broken and not np.isnan(_lh) and close[i, 0] > _lh:
                bull_choch[i, 0] = True; lh_broken = True; is_bull_choch = True; did_choch = True
        elif _trend == 0:
            if not lh_broken and not np.isnan(_lh) and close[i, 0] > _lh:
                bull_choch[i, 0] = True; lh_broken = True; is_bull_choch = True; did_choch = True
            if not hl_broken and not np.isnan(_hl) and close[i, 0] < _hl:
                bear_choch[i, 0] = True; hl_broken = True; is_bear_choch = True; did_choch = True
            if not did_choch:
                if not hh_broken and not np.isnan(_hh) and close[i, 0] > _hh:
                    bull_bos[i, 0] = True; hh_broken = True
                if not ll_broken and not np.isnan(_ll) and close[i, 0] < _ll:
                    bear_bos[i, 0] = True; ll_broken = True

        if lbl in (1, 2): bullish_count += 1; bearish_count = 0
        elif lbl in (3, 4): bearish_count += 1; bullish_count = 0

        if did_choch:
            if is_bear_choch: _trend = 0; _hh = np.nan; _hl = np.nan
            elif is_bull_choch: _trend = 0; _lh = np.nan; _ll = np.nan
            bullish_count = 0; bearish_count = 0
        elif _trend == 0:
            if bull_bos[i, 0]: _trend = 1; _lh = np.nan; _ll = np.nan; lh_broken = True; ll_broken = True
            elif bear_bos[i, 0]: _trend = -1; _hh = np.nan; _hl = np.nan; hh_broken = True; hl_broken = True
            elif bullish_count >= 3: _trend = 1; _lh = np.nan; _ll = np.nan; lh_broken = True; ll_broken = True
            elif bearish_count >= 3: _trend = -1; _hh = np.nan; _hl = np.nan; hh_broken = True; hl_broken = True
        else:
            if not np.isnan(_hh) and not np.isnan(_hl): _trend = 1; _lh = np.nan; _ll = np.nan
            elif not np.isnan(_lh) and not np.isnan(_ll): _trend = -1; _hh = np.nan; _hl = np.nan

        trend[i, 0] = _trend
        last_hh[i, 0] = _hh; last_hl[i, 0] = _hl
        last_lh[i, 0] = _lh; last_ll[i, 0] = _ll

    return (label, trend, last_hh, last_hl, last_lh, last_ll,
            bull_bos, bear_bos, bull_choch, bear_choch)


@nb.njit
def _label_custom(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                  swings: np.ndarray, levels: np.ndarray):
    return _label_nb(high, low, close, swings, levels)


StructureLabels = IF(
    class_name="StructureLabels",
    input_names=["high", "low", "close", "swings", "levels"],
    param_names=[],
    output_names=[
        "label", "trend", "last_hh", "last_hl", "last_lh", "last_ll",
        "bullish_bos", "bearish_bos", "bullish_choch", "bearish_choch",
    ],
).from_custom_func(_label_custom)


# ── Liquidity Sweeps ────────────────────────────────────────────────────────────


@nb.njit
def _sweep_nb(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              swing_highs: np.ndarray, swing_lows: np.ndarray,
              lookback: int, reclaim_candles: int):
    """Detect sweeps for one param set. Returns [n,1] arrays."""
    n = high.shape[0]
    pool_level = np.full((n, 1), np.nan)
    direction = np.zeros((n, 1), dtype=np.int8)
    reclaim = np.zeros((n, 1), dtype=np.bool_)
    wick_only = np.zeros((n, 1), dtype=np.bool_)

    # Collect swing levels
    sh_idx = np.where(swing_highs[:, 0] > 0)[0]
    sh_lv = np.empty(len(sh_idx))
    for j in range(len(sh_idx)):
        sh_lv[j] = swing_highs[sh_idx[j], 0]

    sl_idx = np.where(swing_lows[:, 0] < 0)[0]
    sl_lv = np.empty(len(sl_idx))
    for j in range(len(sl_idx)):
        sl_lv[j] = -swing_lows[sl_idx[j], 0]

    for i in range(lookback, n):
        # Swing high sweep (bearish)
        for j in range(len(sh_idx)):
            if sh_idx[j] >= i or i - sh_idx[j] > 100:
                continue
            if high[i, 0] > sh_lv[j]:
                pool_level[i, 0] = sh_lv[j]
                direction[i, 0] = -1
                wick_only[i, 0] = close[i, 0] <= sh_lv[j]
                for kk in range(i + 1, min(i + reclaim_candles + 1, n)):
                    if close[kk, 0] < sh_lv[j]:
                        reclaim[i, 0] = True
                        break
                break

        if direction[i, 0] == 0:
            # Swing low sweep (bullish)
            for j in range(len(sl_idx)):
                if sl_idx[j] >= i or i - sl_idx[j] > 100:
                    continue
                if low[i, 0] < sl_lv[j]:
                    pool_level[i, 0] = sl_lv[j]
                    direction[i, 0] = 1
                    wick_only[i, 0] = close[i, 0] >= sl_lv[j]
                    for kk in range(i + 1, min(i + reclaim_candles + 1, n)):
                        if close[kk, 0] > sl_lv[j]:
                            reclaim[i, 0] = True
                            break
                    break

    return pool_level, direction, reclaim, wick_only


@nb.njit
def _sweep_custom(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                  swing_highs: np.ndarray, swing_lows: np.ndarray,
                  lookback: np.ndarray, reclaim_candles: np.ndarray):
    n_params = len(lookback)
    n_bars = high.shape[0]
    out_pool = np.full((n_bars, n_params), np.nan)
    out_dir = np.zeros((n_bars, n_params), dtype=np.int8)
    out_reclaim = np.zeros((n_bars, n_params), dtype=np.bool_)
    out_wick = np.zeros((n_bars, n_params), dtype=np.bool_)

    for k in range(n_params):
        pl, dr, rc, wk = _sweep_nb(high, low, close, swing_highs, swing_lows,
                                   lookback[k], reclaim_candles[k])
        out_pool[:, k] = pl[:, 0]
        out_dir[:, k] = dr[:, 0]
        out_reclaim[:, k] = rc[:, 0]
        out_wick[:, k] = wk[:, 0]

    return out_pool, out_dir, out_reclaim, out_wick


LiquiditySweeps = IF(
    class_name="LiquiditySweeps",
    input_names=["high", "low", "close", "swing_highs", "swing_lows"],
    param_names=["lookback", "reclaim_candles"],
    output_names=["pool_level", "direction", "reclaim", "wick_only"],
).from_custom_func(_sweep_custom)


# ── Helper: Run all indicators ──────────────────────────────────────────────────


def compute_all(df, swing_left=3, swing_right=3, fvg_min_gap_atr_mult=0.01,
                sweep_lookback=3, sweep_reclaim=3):
    """Compute all structure indicators on a DataFrame.

    Returns dict of indicator objects.
    """
    high = df["high"].values.reshape(-1, 1)
    low = df["low"].values.reshape(-1, 1)
    close = df["close"].values.reshape(-1, 1)

    sw = SwingPoints.run(high, low, left=[swing_left], right=[swing_right])
    fvg = FVGInd.run(high, low, close,
                     left=[swing_left], right=[swing_right],
                     min_gap_atr_mult=[fvg_min_gap_atr_mult])
    struct = StructureLabels.run(high, low, close, sw.swings, sw.levels)

    # For sweeps, pass swing levels as signals:
    # swing_highs = levels where swing==1, else 0
    # swing_lows = -levels where swing==-1, else 0
    sw_vals = sw.swings.values
    lv_vals = sw.levels.values
    sh = np.where(sw_vals == 1, lv_vals, 0).astype(np.float64).reshape(-1, 1)
    sl = np.where(sw_vals == -1, -lv_vals, 0).astype(np.float64).reshape(-1, 1)

    sweeps = LiquiditySweeps.run(high, low, close, sh, sl,
                                 lookback=[sweep_lookback],
                                 reclaim_candles=[sweep_reclaim])

    return {"swings": sw, "fvg": fvg, "structure": struct, "sweeps": sweeps}
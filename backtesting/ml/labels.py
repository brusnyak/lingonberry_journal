"""
Triple-barrier labeling for ICT/SMC strategies.

Labels each bar with 3-class outcome:
    0 → HOLD (no trade / timeout — neither TP nor SL hit within horizon)
    1 → LONG (direction accuracy: bullish signal leads to TP before SL)
    2 → SHORT (bearish signal leads to TP before SL)

Reuses the event_profile logic from ict_direction_accuracy.py but outputs
a complete bar-by-bar label vector instead of event-only samples.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_R = 1.5  # default TP target in R


def triple_barrier_labels(
    ohlc: pd.DataFrame,
    entry_prices: np.ndarray,
    sl_prices: np.ndarray,
    tp_prices: np.ndarray,
    direction: np.ndarray,  # +1 (long), -1 (short), 0 (no signal)
    horizon: int = 24,
    only_signal_bars: bool = True,
) -> np.ndarray:
    """
    Compute 3-class labels for bars where a signal fired.

    Parameters
    ----------
    ohlc : DataFrame
        OHLC data with columns ['high', 'low', 'close'].
    entry_prices : ndarray
        Entry price per bar (NaN if no signal).
    sl_prices : ndarray
        Stop-loss price per bar (NaN if no signal).
    tp_prices : ndarray
        Take-profit price per bar (NaN if no signal).
    direction : ndarray
        +1 (long), -1 (short), 0 (no signal).
    horizon : int
        Max bars to wait for TP/SL hit.
    only_signal_bars : bool
        If True, return labels only for bars with a signal.

    Returns
    -------
    ndarray of int: 0=HOLD, 1=LONG (tp hit), 2=SHORT (tp hit).
        Shape = (n_signals,) if only_signal_bars else (n_bars,).
    """
    high = ohlc["high"].to_numpy(dtype=float)
    low = ohlc["low"].to_numpy(dtype=float)
    n = len(ohlc)

    signal_idx = np.where(direction != 0)[0]
    n_signals = len(signal_idx)

    if n_signals == 0:
        return np.array([], dtype=np.int_)

    labels = np.zeros(n_signals, dtype=np.int_)

    for j, i in enumerate(signal_idx):
        entry = entry_prices[i]
        sl = sl_prices[i]
        tp = tp_prices[i]
        dir_ = direction[i]

        if not np.isfinite(entry) or not np.isfinite(sl) or not np.isfinite(tp):
            labels[j] = 0
            continue

        end = min(n, i + horizon + 1)
        future_high = high[i + 1 : end]
        future_low = low[i + 1 : end]

        if dir_ == 1:  # long
            tp_hit = future_high >= tp
            sl_hit = future_low <= sl
        else:  # short
            tp_hit = future_low <= tp
            sl_hit = future_high >= sl

        tp_idx = int(np.argmax(tp_hit)) if tp_hit.any() else -1
        sl_idx = int(np.argmax(sl_hit)) if sl_hit.any() else -1

        if tp_idx >= 0 and (sl_idx < 0 or tp_idx < sl_idx):
            labels[j] = 1 if dir_ == 1 else 2
        elif sl_idx >= 0 and (tp_idx < 0 or sl_idx <= tp_idx):
            labels[j] = 0  # SL hit = bad trade = HOLD
        else:
            labels[j] = 0  # timeout

    if only_signal_bars:
        return labels

    full_labels = np.zeros(n, dtype=np.int_)
    for j, i in enumerate(signal_idx):
        full_labels[i] = labels[j]
    return full_labels


def triple_barrier_labels_from_events(
    ohlc: pd.DataFrame,
    events: pd.DataFrame,
    horizon: int = 24,
) -> pd.Series:
    """
    Label from event DataFrame (ict_direction_accuracy.py format).

    Events must have: i, dir_sign, entry (close at i), protected_low/high as SL,
    and a defined TP at target_r * risk.
    """
    labels = np.zeros(len(events), dtype=np.int_)

    for j, ev in events.iterrows():
        i = int(ev["i"])
        direction = int(ev["dir_sign"])
        if i + 1 >= len(ohlc):
            labels[j] = 0
            continue

        entry = float(ohlc.iloc[i]["close"])
        if direction > 0:
            sl = float(ev.get("protected_low", np.nan))
            if not np.isfinite(sl) or sl >= entry:
                sl = entry * 0.995
        else:
            sl = float(ev.get("protected_high", np.nan))
            if not np.isfinite(sl) or sl <= entry:
                sl = entry * 1.005

        risk = abs(entry - sl)
        if risk <= 0:
            labels[j] = 0
            continue

        tp = entry + direction * risk * TARGET_R
        end = min(len(ohlc), i + horizon + 1)
        future_high = ohlc.iloc[i + 1 : end]["high"].values.astype(float)
        future_low = ohlc.iloc[i + 1 : end]["low"].values.astype(float)

        if direction > 0:
            tp_hit = future_high >= tp
            sl_hit = future_low <= sl
        else:
            tp_hit = future_low <= tp
            sl_hit = future_high >= sl

        tp_idx = int(np.argmax(tp_hit)) if tp_hit.any() else -1
        sl_idx = int(np.argmax(sl_hit)) if sl_hit.any() else -1

        if tp_idx >= 0 and (sl_idx < 0 or tp_idx < sl_idx):
            labels[j] = 1 if direction > 0 else 2
        else:
            labels[j] = 0

    return pd.Series(labels, index=events.index, name="label")


def class_distribution(labels: np.ndarray) -> dict:
    """Return {class_name: count, pct} for diagnostics."""
    total = len(labels)
    if total == 0:
        return {"HOLD": (0, 0.0), "LONG": (0, 0.0), "SHORT": (0, 0.0)}
    names = {0: "HOLD", 1: "LONG", 2: "SHORT"}
    out = {}
    for k, name in names.items():
        cnt = int((labels == k).sum())
        out[name] = (cnt, cnt / total * 100)
    return out


def balance_classes(y: np.ndarray, strategy: str = "oversample") -> tuple[np.ndarray, np.ndarray]:
    """Balance 3-class labels.

    Returns (indices, new_y) for the balanced subset.
    strategy: 'oversample' (repeat minority), 'undersample' (trim majority).
    """
    classes, counts = np.unique(y, return_counts=True)
    max_count = counts.max()
    indices = []
    new_labels = []

    for cls in [0, 1, 2]:
        cls_idx = np.where(y == cls)[0]
        if len(cls_idx) == 0:
            continue
        if strategy == "oversample":
            repeats = int(np.ceil(max_count / len(cls_idx)))
            sel = np.tile(cls_idx, repeats)[:max_count]
        else:
            sel = cls_idx[:counts.min()]
        indices.extend(sel.tolist())
        new_labels.extend([cls] * len(sel))

    return np.array(indices), np.array(new_labels, dtype=np.int_)

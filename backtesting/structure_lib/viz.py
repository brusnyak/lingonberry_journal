"""
Multi-timeframe visualization for structure engine verification.

TradingView-style: OHLC + swing markers + BOS/CHoCH horizontal lines
at pivot levels + trade overlay (entry/SL/TP).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

# Try to load the project's data loader
try:
    from backtesting.strategies.ict_intraday import load_data as _load_pair_data
except ImportError:
    _load_pair_data = None


def _draw_candles(ax, data: pd.DataFrame, scale: float = 1.0) -> None:
    """Draw OHLC candlesticks on an axis. `data` has open/high/low/close columns."""
    width = 0.6 * scale
    for i in range(len(data)):
        row = data.iloc[i]
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = "#26a69a" if c >= o else "#ef5350"
        ax.plot([i, i], [l, h], color=color, linewidth=1 * scale)
        body_bot = min(o, c)
        body_top = max(o, c)
        ax.add_patch(patches.Rectangle(
            (i - width / 2, body_bot), width, body_top - body_bot,
            facecolor=color, edgecolor=color, linewidth=0.3 * scale,
        ))


def _draw_swings(ax, swings: pd.Series, levels: pd.Series,
                 scale: float = 1.0, labels: pd.DataFrame = None) -> None:
    """Draw swing markers with structure labels and BOS/CHoCH horizontal lines."""
    if swings is None or levels is None:
        return

    sw_vals = swings.values
    lv_vals = levels.values
    n = len(sw_vals)

    high_idx = np.where(sw_vals == 1)[0]
    low_idx = np.where(sw_vals == -1)[0]

    # ── Swing point markers ──
    if len(high_idx):
        ax.scatter(high_idx, lv_vals[high_idx], color="#1565c0",
                   marker="v", s=60 * scale, zorder=5, linewidths=0.5)
    if len(low_idx):
        ax.scatter(low_idx, lv_vals[low_idx], color="#7b1fa2",
                   marker="^", s=60 * scale, zorder=5, linewidths=0.5)

    # ── Structure labels (HH/HL/LH/LL) with level lines ──
    if labels is not None:
        drawn_levels = {}  # (type, level) → color, to avoid redrawing same level
        for i in range(len(labels)):
            lbl = labels.iloc[i]
            lab = lbl.get("structure_label", "")

            if lab in ("HH", "HL", "LH", "LL"):
                level = lv_vals[i]

                # Determine color and line style
                if lab in ("HH", "HL"):
                    color = "#1565c0"  # blue for bullish
                    ls = "--"
                elif lab == "LH":
                    color = "#ff6f00"  # amber for lower high
                    ls = "--"
                else:  # LL
                    color = "#c62828"  # red for lower low
                    ls = "--"

                # Label offset: HH/LH above swing, HL/LL below
                y_off = -14 if lab in ("HH", "LH") else 10
                ax.annotate(lab, (i, level),
                            textcoords="offset points", xytext=(0, y_off),
                            fontsize=7, color=color, ha="center", fontweight="bold")

                # Draw horizontal line at structure level (first occurrence only,
                # since levels repeat across candles)
                level_key = (lab, round(level, 5))
                if level_key not in drawn_levels:
                    drawn_levels[level_key] = color
                    ax.axhline(y=level, color=color, linestyle=ls,
                               alpha=0.3, linewidth=0.8)

    # ── BOS: segment from pivot source to break candle ──
    if labels is not None:
        bos_bull = np.where(labels["bullish_bos"].values)[0]
        for p in bos_bull:
            lvl = labels.iloc[p]["bos_level"]
            if np.isnan(lvl):
                continue
            # Find the last HH swing at this level (source pivot)
            src_idx = _find_level_source(sw_vals, lv_vals, p, 1, lvl)
            if src_idx is not None:
                ax.plot([src_idx, p], [lvl, lvl], color="#2e7d32",
                        linestyle="--", linewidth=1.5, alpha=0.8, zorder=4)
            ax.text(p, lvl, f"  ↑BOS", fontsize=7, color="#2e7d32",
                    fontweight="bold", va="bottom", ha="left")

        bos_bear = np.where(labels["bearish_bos"].values)[0]
        for p in bos_bear:
            lvl = labels.iloc[p]["bos_level"]
            if np.isnan(lvl):
                continue
            src_idx = _find_level_source(sw_vals, lv_vals, p, -1, lvl)
            if src_idx is not None:
                ax.plot([src_idx, p], [lvl, lvl], color="#c62828",
                        linestyle="--", linewidth=1.5, alpha=0.8, zorder=4)
            ax.text(p, lvl, f"  ↓BOS", fontsize=7, color="#c62828",
                    fontweight="bold", va="top", ha="left")

        # CHoCH: segment from pivot source to break candle
        choch_bull = np.where(labels["bullish_choch"].values)[0]
        for p in choch_bull:
            lvl = labels.iloc[p]["choch_level"]
            if np.isnan(lvl):
                continue
            # CHoCH breaks a LH → find last LH (sw_vals==1, level ~ lvl)
            src_idx = _find_level_source(sw_vals, lv_vals, p, 1, lvl)
            if src_idx is not None:
                ax.plot([src_idx, p], [lvl, lvl], color="#e65100",
                        linestyle="--", linewidth=1.5, alpha=0.8, zorder=4)
            ax.text(p, lvl, f"  ↑CHoCH", fontsize=7, color="#e65100",
                    fontweight="bold", va="bottom", ha="left")

        choch_bear = np.where(labels["bearish_choch"].values)[0]
        for p in choch_bear:
            lvl = labels.iloc[p]["choch_level"]
            if np.isnan(lvl):
                continue
            # CHoCH breaks a HL → find last HL (sw_vals==-1, level ~ lvl)
            src_idx = _find_level_source(sw_vals, lv_vals, p, -1, lvl)
            if src_idx is not None:
                ax.plot([src_idx, p], [lvl, lvl], color="#e65100",
                        linestyle="--", linewidth=1.5, alpha=0.8, zorder=4)
            ax.text(p, lvl, f"  ↓CHoCH", fontsize=7, color="#e65100",
                    fontweight="bold", va="top", ha="left")


def _find_level_source(sw_vals, lv_vals, break_idx, swing_type, level, tol=0.0005):
    """Find the index of the source swing that set this BOS/CHoCH level.
    
    Searches backward from break_idx for the last swing of `swing_type`
    (1=high, -1=low) with a level within `tol` of `level`.
    Returns the index or None.
    """
    for i in range(break_idx - 1, -1, -1):
        if not np.isnan(sw_vals[i]) and sw_vals[i] == swing_type:
            if abs(lv_vals[i] - level) <= tol:
                return i
    return None


def _time_labels(data, n_labels=10):
    """Generate evenly spaced time labels for x-axis."""
    step = max(1, len(data) // n_labels)
    pos = list(range(0, len(data), step))
    labels = [data.index[i].strftime("%m/%d %H:%M") if i < len(data) else "" for i in pos]
    return pos, labels


def draw_trade(ax: plt.Axes, entry: float, sl: float, tp: float,
               direction: str = "long", label: str = "") -> None:
    """Draw a trade overlay (entry / SL / TP) on an axis.
    
    Parameters
    ----------
    ax : plt.Axes
        Axis to draw on.
    entry : float
        Entry price.
    sl : float
        Stop loss price.
    tp : float
        Take profit price.
    direction : str
        "long" or "short".
    label : str
        Optional trade label (e.g., "1:3 R:R").
    """
    x_min, x_max = ax.get_xlim()
    x_mid = (x_min + x_max) / 2

    if direction == "long":
        entry_color = "#2e7d32"
        sl_color = "#c62828"
        tp_color = "#2e7d32"
    else:
        entry_color = "#c62828"
        sl_color = "#2e7d32"
        tp_color = "#c62828"

    # Entry line (solid, thick)
    ax.axhline(y=entry, color=entry_color, linestyle="-", linewidth=1.5, alpha=0.9)
    ax.text(x_max, entry, f"  Entry {entry:.5f}", fontsize=8, color=entry_color,
            fontweight="bold", va="center")

    # SL line (dashed red/green)
    rr = abs((tp - entry) / (entry - sl)) if abs(entry - sl) > 1e-8 else 0
    ax.axhline(y=sl, color=sl_color, linestyle=":", linewidth=1.2, alpha=0.8)
    ax.text(x_max, sl, f"  SL {sl:.5f}", fontsize=7, color=sl_color, va="center")

    # TP line (dashed)
    ax.axhline(y=tp, color=tp_color, linestyle="--", linewidth=1.2, alpha=0.8)
    tp_text = f"  TP {tp:.5f}"
    if label:
        tp_text += f" ({label})"
    elif rr > 0:
        tp_text += f" (1:{rr:.1f})"
    ax.text(x_max, tp, tp_text, fontsize=7, color=tp_color,
            fontweight="bold", va="center")

    # Fill zone between entry and TP (green tint for long)
    if direction == "long" and tp > entry:
        ax.axhspan(entry, tp, alpha=0.05, color="#2e7d32")
    elif direction == "short" and tp < entry:
        ax.axhspan(tp, entry, alpha=0.05, color="#c62828")


def plot_mtf(
    data: dict[str, pd.DataFrame],
    symbol: str = "",
    date_str: str = "",
    swing_length: int = 3,
    swing_labels: Optional[dict[str, pd.DataFrame]] = None,
    n_candles_5m: int = 120,
    start_idx_5m: int = 0,
    figsize: tuple = (18, 12),
    save_path: str = "",
    show_killzones: bool = True,
    trade: Optional[dict] = None,
) -> None:
    """
    Multi-timeframe plot: 4H (top), 30m (middle), 5m (bottom).

    Parameters
    ----------
    data : dict
        Keys "4H", "30m", "5m" with corresponding DataFrames.
    symbol : str
        Display name.
    date_str : str
        If set, filter to this date (overrides start_idx).
    swing_length : int
        Passed to swing_point().
    swing_labels : dict
        Optional dict of DataFrames with structure labels per timeframe.
    n_candles_5m : int
        Number of 5m candles to show.
    start_idx_5m : int
        Starting index in the 5m data.
    trade : dict, optional
        Trade overlay: {"entry": float, "sl": float, "tp": float,
                        "direction": "long"|"short", "label": str}
    """
    df_5m = data["5m"]
    df_30m = data["30m"]
    df_4h = data["4H"]

    # Filter to date range if specified
    if date_str:
        day = pd.Timestamp(date_str).date()
        day_mask = df_5m.index.date == day
        if day_mask.any():
            start_idx_5m = int(np.where(day_mask)[0][0])
            n_candles_5m = min(int(day_mask.sum()), n_candles_5m)

    end_idx_5m = min(start_idx_5m + n_candles_5m, len(df_5m))
    start_time = df_5m.index[start_idx_5m]
    end_time = df_5m.index[end_idx_5m - 1]

    # Slice each TF to the same time window
    def _slice(df):
        return df.loc[start_time:end_time].copy()

    slice_5m = _slice(df_5m)
    slice_30m = _slice(df_30m)
    slice_4h = _slice(df_4h)

    if len(slice_5m) == 0:
        print("No data in selected range")
        return

    # Compute swings + structure labels
    from backtesting.struct.swing import swing_points
    from backtesting.struct.labels import label_structure
    sw_5m, lv_5m = swing_points(slice_5m, swing_length)
    sw_30m, lv_30m = swing_points(slice_30m, swing_length)
    sw_4h, lv_4h = swing_points(slice_4h, swing_length)

    lbl_5m = label_structure(slice_5m, sw_5m, lv_5m)
    lbl_30m = label_structure(slice_30m, sw_30m, lv_30m)
    lbl_4h = label_structure(slice_4h, sw_4h, lv_4h)

    fig, axes = plt.subplots(3, 1, figsize=figsize, gridspec_kw={"height_ratios": [1, 1.2, 1.5]})
    fig.suptitle(
        f"{symbol} — {start_time.date()}  {start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')} UTC"
        f"  (swing_len={swing_length})",
        fontsize=13, fontweight="bold",
    )

    # ── 4H panel ──
    ax = axes[0]
    ax.set_title("4H", fontsize=10, loc="left", fontweight="bold")
    _draw_candles(ax, slice_4h, scale=1.5)
    _draw_swings(ax, sw_4h, lv_4h, scale=1.5, labels=lbl_4h)
    pos, lbls = _time_labels(slice_4h)
    ax.set_xticks(pos)
    ax.set_xticklabels(lbls, fontsize=7, rotation=30)
    ax.grid(True, alpha=0.2)
    ax.set_ylabel("Price")

    # ── 30m panel ──
    ax = axes[1]
    ax.set_title("30m", fontsize=10, loc="left", fontweight="bold")
    _draw_candles(ax, slice_30m, scale=1.2)
    _draw_swings(ax, sw_30m, lv_30m, scale=1.2, labels=lbl_30m)
    pos, lbls = _time_labels(slice_30m)
    ax.set_xticks(pos)
    ax.set_xticklabels(lbls, fontsize=7, rotation=30)
    ax.grid(True, alpha=0.2)
    ax.set_ylabel("Price")

    # ── 5m panel ──
    ax = axes[2]
    ax.set_title("5m", fontsize=10, loc="left", fontweight="bold")
    _draw_candles(ax, slice_5m)
    _draw_swings(ax, sw_5m, lv_5m, labels=lbl_5m)

    # ── Trade overlay (on 5m panel) ──
    if trade is not None:
        draw_trade(ax, **trade)

    pos, lbls = _time_labels(slice_5m)
    ax.set_xticks(pos)
    ax.set_xticklabels(lbls, fontsize=7, rotation=30)
    ax.grid(True, alpha=0.2)
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Price")

    # ── Kill zone vertical bands (on all panels) ──
    if show_killzones:
        for ax_i in axes:
            _add_killzone_bands(ax_i, slice_5m)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)


def _add_killzone_bands(ax, data_5m):
    """Add vertical bands for London and NY kill zones."""
    london_kz = (6, 9)   # UTC
    ny_kz = (12, 15)     # UTC

    for zone_name, (start_h, end_h) in [("London KZ", london_kz), ("NY KZ", ny_kz)]:
        in_zone = False
        zone_start = None
        for i in range(len(data_5m)):
            h = data_5m.index[i].hour
            if start_h <= h < end_h:
                if not in_zone:
                    zone_start = i
                    in_zone = True
            else:
                if in_zone and zone_start is not None:
                    ax.axvspan(zone_start, i - 1, alpha=0.06,
                               color="#4caf50" if "London" in zone_name else "#2196f3")
                    # Label
                    mid = (zone_start + i) // 2
                    ax.text(mid, ax.get_ylim()[1], zone_name,
                            fontsize=6, alpha=0.4, ha="center", va="bottom")
                    in_zone = False
        if in_zone and zone_start is not None:
            ax.axvspan(zone_start, len(data_5m) - 1, alpha=0.06,
                       color="#4caf50" if "London" in zone_name else "#2196f3")


def quick_view(
    symbol: str = "EURUSD.X",
    date_str: str = "2026-04-06",
    swing_length: int = 3,
    n_candles_5m: int = 120,
    save_path: str = "",
    show_killzones: bool = True,
    trade: Optional[dict] = None,
) -> None:
    """
    Quick multi-TF view for a symbol and date.
    Loads data automatically from parquet.
    """
    if _load_pair_data is None:
        print("Cannot load data — missing ict_intraday module")
        return

    data = _load_pair_data(symbol)
    name_map = {"EURUSD.X": "EUR/USD", "GBPUSD.X": "GBP/USD", "XAUUSD.X": "XAU/GOLD"}
    pair_name = name_map.get(symbol, symbol)

    plot_mtf(
        data=data,
        symbol=pair_name,
        date_str=date_str,
        swing_length=swing_length,
        n_candles_5m=n_candles_5m,
        save_path=save_path or f"/tmp/{symbol}_mtf.png",
        show_killzones=show_killzones,
        trade=trade,
    )

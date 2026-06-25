#!/usr/bin/env python3
"""
Visual Verification Tool — Structure Labels on Interactive Chart
Uses smartmoneyconcepts library (ICT/SMC) for structure detection.

Usage:
    python backtesting/visualize.py
    python backtesting/visualize.py --tf 15 --days 14 --swing 5
    python backtesting/visualize.py --tf 60 --days 30 --swing 5
    python backtesting/visualize.py --tf 240 --days 60 --swing 5

Opens an HTML file in your browser. No server needed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT = Path(__file__).parent
_ROOT   = _SCRIPT.parent
sys.path.insert(0, str(_ROOT))

from smartmoneyconcepts import smc

try:
    from lwcharts import Chart
except ImportError:
    print("Missing lwcharts. Install: pip install lwcharts")
    sys.exit(1)


def load_tf(symbol: str, tf: str, days: int = 30) -> pd.DataFrame:
    """Load parquet data for a single TF."""
    f = _ROOT / "data" / "market_data" / f"{symbol}{tf}.parquet"
    if not f.exists():
        raise FileNotFoundError(f"Missing data: {f}")
    df = pd.read_parquet(f)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    if days and len(df) > 0:
        cutoff = df["ts"].max() - pd.Timedelta(days=days)
        df = df[df["ts"] >= cutoff].reset_index(drop=True)
    return df


def compute_hh_hl_lh_ll(swings: pd.DataFrame) -> pd.DataFrame:
    """Compute HH/HL/LH/LL labels from smc swing data.

    Returns DataFrame indexed like swings with:
      label: HH, HL, LH, LL, 1H, 1L, or '' 
      trend: bullish, bearish, neutral
    """
    n = len(swings)
    label = np.full(n, "", dtype=object)
    trend = np.full(n, "neutral", dtype=object)

    prev_high = np.nan
    prev_low = np.nan
    prev_high_idx = -1
    prev_low_idx = -1

    for i in range(n):
        hl = swings.iloc[i]["HighLow"]
        lv = swings.iloc[i]["Level"]
        if np.isnan(hl):
            continue

        if hl == 1:  # swing high
            if not np.isnan(prev_high):
                label[i] = "HH" if lv > prev_high else "LH"
            else:
                label[i] = "1H"
            prev_high = lv
            prev_high_idx = i
        else:  # swing low
            if not np.isnan(prev_low):
                label[i] = "HL" if lv > prev_low else "LL"
            else:
                label[i] = "1L"
            prev_low = lv
            prev_low_idx = i

        # Determine trend: look at last 4 labeled swings
        # Bullish = HH + HL pattern, Bearish = LH + LL
        recent_labels = label[max(0, i - 8):i + 1]
        recent_labels = recent_labels[recent_labels != ""]

        has_hh = any(l == "HH" for l in recent_labels)
        has_hl = any(l == "HL" for l in recent_labels)
        has_lh = any(l == "LH" for l in recent_labels)
        has_ll = any(l == "LL" for l in recent_labels)

        # Determine from most recent 2 swings
        last_two = [l for l in recent_labels if l in ("HH", "HL", "LH", "LL")][-2:]
        if len(last_two) >= 2:
            bullish_swings = sum(1 for l in last_two if l in ("HH", "HL"))
            bearish_swings = sum(1 for l in last_two if l in ("LH", "LL"))
            if bullish_swings >= 2:
                trend[i] = "bullish"
            elif bearish_swings >= 2:
                trend[i] = "bearish"
            else:
                trend[i] = "neutral"
        elif has_hh and has_hl:
            trend[i] = "bullish"
        elif has_lh and has_ll:
            trend[i] = "bearish"

    return pd.DataFrame({"label": label, "trend": trend}, index=swings.index)


def main():
    parser = argparse.ArgumentParser(description="Visual structure verification (SMC)")
    parser.add_argument("--symbol", default="GBPUSD")
    parser.add_argument("--tf", default="15", help="Timeframe (15, 60, 240, etc)")
    parser.add_argument("--days", type=int, default=14, help="Days of data to load")
    parser.add_argument("--swing", type=int, default=5, help="Swing length (default 5)")
    parser.add_argument("--output", default=None, help="Output HTML path")
    args = parser.parse_args()

    # ── Load data ──
    print(f"Loading {args.symbol} {args.tf}m — last {args.days} days...")
    df = load_tf(args.symbol, args.tf, days=args.days)
    ts_unix = (df["ts"].astype("int64") // 10**9).values
    print(f"  {len(df)} bars")

    # ── SMC analysis ──
    print("Computing swings (smc)...")
    swings = smc.swing_highs_lows(df, swing_length=args.swing)

    print("Computing BOS/CHoCH (smc)...")
    bos_choch = smc.bos_choch(df, swings, close_break=True)

    print("Computing HH/HL/LH/LL labels...")
    labels_df = compute_hh_hl_lh_ll(swings)

    print("Computing FVGs...")
    fvgs = smc.fvg(df)

    # ── Build markers ──
    markers = []

    # Swing point markers with HH/HL/LH/LL text
    swing_mask = swings["HighLow"].notna()
    swing_idx = np.where(swing_mask.values)[0]
    for i in swing_idx:
        t = int(ts_unix[i])
        hl = swings.iloc[i]["HighLow"]
        lv = swings.iloc[i]["Level"]
        lbl = labels_df.iloc[i]["label"]

        if hl == 1:  # swing high
            if lbl in ("HH", ""):
                markers.append({
                    "time": t, "shape": "arrowDown", "position": "aboveBar",
                    "color": "#ef4444", "text": f"HH {lv:.5f}",
                })
            elif lbl == "LH":
                markers.append({
                    "time": t, "shape": "arrowDown", "position": "aboveBar",
                    "color": "#ef4444", "text": f"LH {lv:.5f}",
                })
            else:
                markers.append({
                    "time": t, "shape": "arrowDown", "position": "aboveBar",
                    "color": "#a855f7", "text": f"{lbl} {lv:.5f}",
                })
        else:  # swing low
            if lbl in ("HL", ""):
                markers.append({
                    "time": t, "shape": "arrowUp", "position": "belowBar",
                    "color": "#22c55e", "text": f"HL {lv:.5f}",
                })
            elif lbl == "LL":
                markers.append({
                    "time": t, "shape": "arrowUp", "position": "belowBar",
                    "color": "#22c55e", "text": f"LL {lv:.5f}",
                })
            else:
                markers.append({
                    "time": t, "shape": "arrowUp", "position": "belowBar",
                    "color": "#a855f7", "text": f"{lbl} {lv:.5f}",
                })

    # BOS markers + horizontal lines
    bos_mask = bos_choch["BOS"].notna()
    bos_idx = np.where(bos_mask.values)[0]
    for idx in bos_idx:
        t = int(ts_unix[idx])
        bos_val = bos_choch.iloc[idx]["BOS"]
        level = bos_choch.iloc[idx]["Level"]
        break_idx = int(bos_choch.iloc[idx]["BrokenIndex"])
        break_t = int(ts_unix[break_idx]) if break_idx < len(ts_unix) else t

        if bos_val == 1:  # bullish BOS
            markers.append({
                "time": break_t, "shape": "arrowUp", "position": "belowBar",
                "color": "#3b82f6", "text": f"BOS↑ {level:.5f}",
            })
        else:  # bearish BOS (-1)
            markers.append({
                "time": break_t, "shape": "arrowDown", "position": "aboveBar",
                "color": "#f97316", "text": f"BOS↓ {level:.5f}",
            })

    # CHoCH markers
    choch_mask = bos_choch["CHOCH"].notna()
    choch_idx = np.where(choch_mask.values)[0]
    for idx in choch_idx:
        t = int(ts_unix[idx])
        choch_val = bos_choch.iloc[idx]["CHOCH"]
        level = bos_choch.iloc[idx]["Level"]
        break_idx = int(bos_choch.iloc[idx]["BrokenIndex"])
        break_t = int(ts_unix[break_idx]) if break_idx < len(ts_unix) else t

        if choch_val == 1:  # bullish CHoCH
            markers.append({
                "time": break_t, "shape": "arrowUp", "position": "belowBar",
                "color": "#a855f7", "text": f"CHoCH↑ {level:.5f}",
            })
        else:  # bearish CHoCH (-1)
            markers.append({
                "time": break_t, "shape": "arrowDown", "position": "aboveBar",
                "color": "#a855f7", "text": f"CHoCH↓ {level:.5f}",
            })

    # ── Summary stats ──
    n_swings = swings["HighLow"].notna().sum()
    n_bos = bos_choch["BOS"].notna().sum()
    n_choch = bos_choch["CHOCH"].notna().sum()
    n_fvg = len(fvgs)
    n_hh = (labels_df["label"] == "HH").sum()
    n_hl = (labels_df["label"] == "HL").sum()
    n_lh = (labels_df["label"] == "LH").sum()
    n_ll = (labels_df["label"] == "LL").sum()

    print(f"\nStructure Summary (smc, swing_length={args.swing}):")
    print(f"  Swings: {n_swings} (HH={n_hh}, HL={n_hl}, LH={n_lh}, LL={n_ll})")
    print(f"  BOS:    {n_bos}")
    print(f"  CHoCH:  {n_choch}")
    print(f"  FVGs:   {n_fvg}")
    print(f"  Markers: {len(markers)}")

    # ── Build chart ──
    plot_df = df.copy()
    plot_df["time"] = ts_unix

    title = f"{args.symbol} {args.tf}m — smc swing={args.swing}, {args.days} days"
    chart = Chart(title, theme="dark", height=700)
    chart.candles(plot_df, time="time")
    chart.volume(plot_df, time="time")

    if markers:
        chart.markers(markers)

    # Horizontal lines at BOS/CHoCH levels
    seen_levels = set()
    for idx in bos_idx:
        level = round(bos_choch.iloc[idx]["Level"], 5)
        if level not in seen_levels:
            seen_levels.add(level)
            bos_val = bos_choch.iloc[idx]["BOS"]
            color = "#3b82f6" if bos_val == 1 else "#f97316"
            label = f"BOS{'↑' if bos_val==1 else '↓'} {level:.5f}"
            chart.hline(price=level, color=color, style="dashed", width=1, label=label)

    # FVG zones as vertical bands on the time axis (unmitigated only)
    # bg_zones_from_mask highlights bars where the mask is True
    fvg_active = np.zeros(len(df), dtype=bool)
    for _, fvg in fvgs.iterrows():
        if fvg["FVG"] not in (1, -1):
            continue
        bar_idx = int(fvg.name) if fvg.name < len(df) else 0
        end = min(bar_idx + 5, len(df) - 1)
        fvg_active[bar_idx:end] = True

    fvg_mask = pd.Series(fvg_active)
    chart.bg_zones_from_mask(fvg_mask, color_true="rgba(100, 100, 255, 0.06)")

    # ── Output ──
    output = args.output
    if not output:
        outfile = f"structure_smc_{args.symbol}_{args.tf}m_swing{args.swing}_{args.days}d.html"
        output = str(_ROOT / "backtesting" / "results" / outfile)
    Path(output).parent.mkdir(exist_ok=True)
    chart.to_html(output)
    print(f"\nChart → {output}")
    print("Open in browser to verify structure labels (SMC).")


if __name__ == "__main__":
    main()

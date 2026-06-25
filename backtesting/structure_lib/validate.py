"""
Multi-pair validation script for structure engine.

Runs structure detection on N days per pair, generates:
  1. Text tables (swing labels + CHoCH/BOS events per day)
  2. Multi-TF charts for visual inspection
  3. Summary statistics

Usage:
    python -m backtesting.struct.validate
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import logging
from datetime import timedelta

import numpy as np
import pandas as pd

from backtesting.struct.swing import swing_points
from backtesting.struct.labels import label_structure, debug_day
from backtesting.struct.sessions import session_ranges

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHART_DIR = Path(__file__).resolve().parent / "validation_charts"
CHART_DIR.mkdir(exist_ok=True)

# Pick days spread across the ~2mo range to get diverse conditions
TEST_DAYS_BY_PAIR = {
    "EURUSD_X": [
        "2026-04-06",  # Classic ICT day (used to tune engine)
        "2026-04-08",  # Choppy multi-CHoCH day
        "2026-04-15",  # Two trades in one day
        "2026-04-22",  # Mid-month, different conditions
        "2026-05-04",  # May sample
        "2026-05-12",  # Mid-May
        "2026-05-20",  # Late May
    ],
    "GBPUSD_X": [
        "2026-04-07",  # Strong trend day
        "2026-04-09",  # Choppy
        "2026-04-16",
        "2026-04-24",
        "2026-05-05",
        "2026-05-13",
        "2026-05-21",
    ],
    "XAUUSD_X": [
        "2026-04-07",
        "2026-04-14",
        "2026-04-21",
        "2026-04-28",
        "2026-05-06",
        "2026-05-14",
        "2026-05-22",
    ],
}

NAME_MAP = {"EURUSD_X": "EUR/USD", "GBPUSD_X": "GBP/USD", "XAUUSD_X": "XAU/GOLD"}


def load_pair_data(symbol: str) -> dict[str, pd.DataFrame]:
    """Load 4H, 30m, 5m data from parquet."""
    pair_dir = DATA_DIR / symbol
    result = {}
    for tf in ("4H", "30m", "5m"):
        path = pair_dir / f"{tf}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing data: {path}")
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        result[tf] = df
    return result


def analyze_day(day_5m: pd.DataFrame, swing_length: int = 3) -> dict:
    """Run structure engine on a single day of 5m data. Return analysis dict."""
    swings, levels = swing_points(day_5m, swing_length=swing_length)
    labels = label_structure(day_5m, swings, levels)

    # Count labels
    label_counts = labels["structure_label"].value_counts()
    n_swings = int(swings.notna().sum())
    n_hh = int(label_counts.get("HH", 0))
    n_hl = int(label_counts.get("HL", 0))
    n_lh = int(label_counts.get("LH", 0))
    n_ll = int(label_counts.get("LL", 0))
    n_1h = int(label_counts.get("1H", 0))
    n_1l = int(label_counts.get("1L", 0))

    # Count events
    n_bull_bos = int(labels["bullish_bos"].sum())
    n_bear_bos = int(labels["bearish_bos"].sum())
    n_bull_choch = int(labels["bullish_choch"].sum())
    n_bear_choch = int(labels["bearish_choch"].sum())

    # Trend distribution
    trend_counts = labels["trend"].value_counts()
    n_bullish = int(trend_counts.get("bullish", 0))
    n_bearish = int(trend_counts.get("bearish", 0))
    n_neutral = int(trend_counts.get("neutral", 0))
    n_transitional = int(trend_counts.get("transitional", 0))

    # Build events table
    has_structure = (labels["structure_label"] != "") | \
                    labels["bullish_bos"] | labels["bearish_bos"] | \
                    labels["bullish_choch"] | labels["bearish_choch"]
    events = labels[has_structure].copy()

    return {
        "pair": "",
        "date": str(day_5m.index[0].date()),
        "n_candles": len(day_5m),
        "n_swings": n_swings,
        "label_counts": {"HH": n_hh, "HL": n_hl, "LH": n_lh, "LL": n_ll, "1H": n_1h, "1L": n_1l},
        "events": {"bullish_bos": n_bull_bos, "bearish_bos": n_bear_bos,
                   "bullish_choch": n_bull_choch, "bearish_choch": n_bear_choch},
        "trend_dist": {"bullish": n_bullish, "bearish": n_bearish,
                       "neutral": n_neutral, "transitional": n_transitional},
        "swings": swings,
        "levels": levels,
        "labels": labels,
        "events_table": events,
    }


def check_failure_modes(analysis: dict, day_ohlc: pd.DataFrame) -> list[str]:
    """Check for common failure modes."""
    issues = []
    lbl = analysis["labels"]

    # 1. No structure at all
    if analysis["n_swings"] == 0:
        issues.append("ZERO swings detected — engine found no pivots at all")

    # 2. Too many swings (> 30 in a trading day is suspicious)
    if analysis["n_swings"] > 30:
        issues.append(f"TOO MANY swings: {analysis['n_swings']} (suspect noise-level pivots)")

    # 3. Too few swings (< 3 in a 5m day with 12h of data)
    if 0 < analysis["n_swings"] < 3:
        issues.append(f"TOO FEW swings: {analysis['n_swings']} (market may be flat or data issue)")

    # 4. No CHoCH events (unusual for a ~12h trading day)
    total_choch = analysis["events"]["bullish_choch"] + analysis["events"]["bearish_choch"]
    if total_choch == 0 and analysis["n_swings"] > 5:
        issues.append(f"ZERO CHoCH events with {analysis['n_swings']} swings — structure never changes trend")

    # 5. Too many CHoCH events (> 6 suggests noise rather than real structure changes)
    if total_choch > 6:
        issues.append(f"TOO MANY CHoCH events: {total_choch} (structure flipping excessively)")

    # 6. Check that neutral trend doesn't dominate a full day with swings
    if analysis["trend_dist"]["neutral"] > len(lbl) * 0.5 and analysis["n_swings"] > 5:
        issues.append(f"Neutral trend dominates ({analysis['trend_dist']['neutral']}/{len(lbl)} candles) despite {analysis['n_swings']} swings")

    # 7. Verify HH levels are ascending and LL levels are descending (basic structure sanity)
    if analysis["n_swings"] >= 4:
        sw = analysis["swings"].values
        lv = analysis["levels"].values
        labels_val = analysis["labels"]

        hh_levels = []
        ll_levels = []
        for i in range(len(labels_val)):
            lbl_val = labels_val.iloc[i]["structure_label"]
            if lbl_val == "HH" and not np.isnan(lv[i]):
                hh_levels.append((i, lv[i]))
            elif lbl_val == "LL" and not np.isnan(lv[i]):
                ll_levels.append((i, lv[i]))

        # Check HH ordering in same trend sequence
        for j in range(1, len(hh_levels)):
            if hh_levels[j][1] < hh_levels[j-1][1] - 0.001:
                issues.append(f"HH DECREASING: HH@{hh_levels[j][0]}={hh_levels[j][1]:.5f} < previous HH@{hh_levels[j-1][0]}={hh_levels[j-1][1]:.5f}")
                break

        # Check LL ordering in same trend sequence
        for j in range(1, len(ll_levels)):
            if ll_levels[j][1] > ll_levels[j-1][1] + 0.001:
                issues.append(f"LL INCREASING: LL@{ll_levels[j][0]}={ll_levels[j][1]:.5f} > previous LL@{ll_levels[j-1][0]}={ll_levels[j-1][1]:.5f}")
                break

    # 8. BOS events should be present in established trends
    total_bos = analysis["events"]["bullish_bos"] + analysis["events"]["bearish_bos"]
    if analysis["trend_dist"]["bullish"] > 50 or analysis["trend_dist"]["bearish"] > 50:
        if total_bos == 0 and analysis["n_swings"] > 5:
            issues.append(f"NO BOS events with strong trend (trend dominates but no structure break)")

    return issues


def print_day_header(date: str, pair: str) -> None:
    log.info("")
    log.info("═" * 75)
    log.info(f"  {date} — {pair}")
    log.info("═" * 75)


def print_analysis_summary(a: dict) -> None:
    lc = a["label_counts"]
    ev = a["events"]
    td = a["trend_dist"]
    log.info(f"  Swings: {a['n_swings']} | Labels: HH={lc['HH']} HL={lc['HL']} LH={lc['LH']} LL={lc['LL']}")
    log.info(f"  Events: ↑BOS={ev['bullish_bos']} ↓BOS={ev['bearish_bos']} ↑CHoCH={ev['bullish_choch']} ↓CHoCH={ev['bearish_choch']}")
    log.info(f"  Trend: bu={td['bullish']} be={td['bearish']} tr={td['transitional']} nt={td['neutral']}")


def print_events_table(a: dict, day_ohlc: pd.DataFrame) -> None:
    """Print a formatted events table for manual verification."""
    events = a["events_table"]
    sw = a["swings"]
    lv = a["levels"]

    if len(events) == 0:
        log.info("  (no structure events)")
        return

    log.info(f"  {'Time':>8} {'Label':>6} {'Level':>10} {'Trend':>12}  Events")
    log.info(f"  {'-'*55}")

    for idx, row in events.iterrows():
        ts_str = idx.strftime("%H:%M")
        lbl = row["structure_label"]
        tr = row["trend"]

        pos = day_ohlc.index.get_loc(idx)
        lv_str = ""
        if lbl in ("HH", "HL", "LH", "LL", "1H", "1L"):
            lv_str = f"{lv.iloc[pos]:.5f}" if not np.isnan(lv.iloc[pos]) else ""

        extras = []
        if row["bullish_bos"]:
            extras.append(f"↑BOS @ {row['bos_level']:.5f}")
        if row["bearish_bos"]:
            extras.append(f"↓BOS @ {row['bos_level']:.5f}")
        if row["bullish_choch"]:
            extras.append(f"↑CHoCH @ {row['choch_level']:.5f}")
        if row["bearish_choch"]:
            extras.append(f"↓CHoCH @ {row['choch_level']:.5f}")

        extra_str = f"  ({', '.join(extras)})" if extras else ""
        log.info(f"  {ts_str:>8}  {lbl:>6}  {lv_str:>10}  {tr:>12}{extra_str}")


def plot_day_chart(symbol: str, date_str: str, data: dict, analysis: dict,
                   save_dir: Path) -> str:
    """Generate multi-TF chart for a day. Returns file path."""
    try:
        from backtesting.struct.viz import plot_mtf

        day_5m = data["5m"][data["5m"].index.date == pd.Timestamp(date_str).date()]
        day_30m = data["30m"][data["30m"].index.date == pd.Timestamp(date_str).date()]
        day_4h = data["4H"][data["4H"].index.date == pd.Timestamp(date_str).date()]

        if len(day_5m) == 0:
            return ""

        # Use swing_labels to pass pre-computed structure
        swing_labels = {
            "5m": analysis["labels"],
        }

        fname = f"{symbol}_{date_str}.png"
        fpath = str(save_dir / fname)

        plot_mtf(
            data={"5m": day_5m, "30m": day_30m, "4H": day_4h},
            symbol=NAME_MAP.get(symbol, symbol),
            date_str=date_str,
            swing_length=3,
            n_candles_5m=len(day_5m),
            save_path=fpath,
        )

        return fpath
    except Exception as e:
        log.warning(f"  Chart generation failed: {e}")
        return ""


def print_validation_results(all_results: list) -> tuple[int, int]:
    """Print summary of all validation results."""
    total_days = len(all_results)
    total_issues = sum(len(r["issues"]) for r in all_results)
    clean_days = sum(1 for r in all_results if not r["issues"])

    log.info("")
    log.info("=" * 75)
    log.info("  VALIDATION SUMMARY")
    log.info("=" * 75)
    log.info(f"  Total days analyzed:  {total_days}")
    log.info(f"  Clean days:           {clean_days} ({clean_days/total_days*100:.0f}%)")
    log.info(f"  Days with issues:     {total_days - clean_days}")
    log.info(f"  Total issues found:   {total_issues}")
    log.info(f"  Charts saved to:      {CHART_DIR}")

    if total_issues > 0:
        log.info("")
        log.info("  ISSUES BY DAY:")
        log.info("  " + "-" * 60)
        for r in all_results:
            if r["issues"]:
                log.info(f"  {r['pair']} {r['date']}:")
                for issue in r["issues"]:
                    log.info(f"    ⚠ {issue}")

    # Summary stats
    n_swings = [r["analysis"]["n_swings"] for r in all_results]
    n_events = [sum(r["analysis"]["events"].values()) for r in all_results]
    log.info("")
    log.info("  AVERAGES:")
    log.info(f"    Swings/day:  {np.mean(n_swings):.1f} (range {min(n_swings)}-{max(n_swings)})")
    log.info(f"    Events/day:  {np.mean(n_events):.1f} (range {min(n_events)}-{max(n_events)})")
    log.info(f"    Charts:      {sum(1 for r in all_results if r['chart'])} generated")

    return total_days, total_issues


def validate_all(
    test_days: dict[str, list[str]] = TEST_DAYS_BY_PAIR,
    swing_length: int = 3,
) -> list[dict]:
    """Run validation across all pairs and days."""
    all_results = []

    for symbol, days in test_days.items():
        log.info("")
        log.info("▓" * 75)
        log.info(f"  ▓ LOADING {symbol} ({NAME_MAP.get(symbol, symbol)})")
        log.info("▓" * 75)
        data = load_pair_data(symbol)

        for date_str in days:
            # Slice to this day only
            day_5m = data["5m"][data["5m"].index.date == pd.Timestamp(date_str).date()].copy()
            if len(day_5m) == 0:
                log.warning(f"  No 5m data for {date_str}")
                continue

            try:
                analysis = analyze_day(day_5m, swing_length=swing_length)
                analysis["pair"] = NAME_MAP.get(symbol, symbol)
                issues = check_failure_modes(analysis, day_5m)

                print_day_header(date_str, NAME_MAP.get(symbol, symbol))
                print_analysis_summary(analysis)
                if issues:
                    log.info(f"  ⚠ ISSUES: {'; '.join(issues)}")
                print_events_table(analysis, day_5m)

                chart = plot_day_chart(symbol, date_str, data, analysis, CHART_DIR)

                all_results.append({
                    "pair": NAME_MAP.get(symbol, symbol),
                    "symbol": symbol,
                    "date": date_str,
                    "analysis": analysis,
                    "issues": issues,
                    "chart": chart,
                })

            except Exception as e:
                log.error(f"  ❌ ERROR: {e}")
                import traceback
                traceback.print_exc()

    return all_results


def main() -> None:
    log.info("╔" + "═" * 73 + "╗")
    log.info("║  ICT/SMC STRUCTURE ENGINE — MULTI-SAMPLE VALIDATION                 ║")
    log.info("║  3 pairs × 7 days = 21 samples across ~2 months of data            ║")
    log.info("╚" + "═" * 73 + "╝")

    results = validate_all()

    total_days, total_issues = print_validation_results(results)
    log.info("")

    if total_issues == 0:
        log.info("  ✅ ALL CHECKS PASSED — engine appears reliable on all samples")
        log.info("")
        log.info("  Next step: integrate with Vibe-Trading as a custom tool so the AI")
        log.info("  can read OHLC + structure labels and propose ICT trade setups.")
    else:
        log.info(f"  ⚠ {total_issues} issues found across {total_days} samples")
        log.info("  Review the Issues by Day section above and inspect the charts.")
        log.info(f"  Charts saved in: {CHART_DIR}")


if __name__ == "__main__":
    main()

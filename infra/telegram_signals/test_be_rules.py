"""
Compare breakeven-arming rules across the full text-era dataset (n=216),
not just the two pilot trades -- testing a rule change only on trades known
to have won would be the same selection-bias mistake in reverse.

Usage:
    python infra/telegram_signals/test_be_rules.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.telegram_signals.backtest_signals import fetch_klines
from infra.telegram_signals.trade_manager import simulate_managed_trade

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / "data" / "telegram_signals" / "just_trade_it" / "signals_parsed.jsonl"

VARIANTS = [
    ("tp1_only (channel default)", dict(be_rule="tp1_only")),
    ("progress_50pct (rejected earlier)", dict(be_rule="progress", progress_frac=0.5)),
    ("progress_25pct", dict(be_rule="progress", progress_frac=0.25)),
    ("progress_hold_50pct_30min", dict(be_rule="progress_hold", progress_frac=0.5, hold_bars=6)),
    ("progress_hold_50pct_2h", dict(be_rule="progress_hold", progress_frac=0.5, hold_bars=24)),
]


def main() -> None:
    sigs = [json.loads(l) for l in open(SIGNALS)]
    results = {name: [] for name, _ in VARIANTS}

    for s in sigs:
        entry_guess = None
        ts = int(datetime.fromisoformat(s["date"]).timestamp() * 1000)
        klines = fetch_klines(s["symbol"], ts)
        if not klines:
            continue
        entry = float(klines[0][4])
        stop_dist_pct = abs(entry - s["stop"]) / entry
        if stop_dist_pct <= 0 or stop_dist_pct > 0.5:
            continue

        for name, kwargs in VARIANTS:
            r = simulate_managed_trade(klines, entry, s["stop"], s["takes"], s["direction"], **kwargs)
            results[name].append(r.weighted_r)

    print(f"{'variant':<38}{'n':>5}{'mean_R':>9}{'sum_R':>9}{'win%':>7}")
    for name, _ in VARIANTS:
        rs = results[name]
        if not rs:
            continue
        n = len(rs)
        mean_r = sum(rs) / n
        win_pct = 100 * sum(1 for r in rs if r > 0) / n
        print(f"{name:<38}{n:>5}{mean_r:>9.4f}{sum(rs):>9.1f}{win_pct:>7.1f}")


if __name__ == "__main__":
    main()

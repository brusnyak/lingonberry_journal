"""
Regenerate backtest_results_net.jsonl using the corrected trade_manager
simulator (real breakeven enforcement) instead of the buggy
backtest_signals.simulate(). Supersedes the earlier apply_cost_model.py run.

Usage:
    python infra/telegram_signals/recompute_net_corrected.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.telegram_signals.backtest_signals import fetch_klines
from infra.telegram_signals.trade_manager import simulate_managed_trade
from infra.telegram_signals.apply_cost_model import fetch_funding, ROUND_TRIP_FEE_PCT, SLIPPAGE_PCT

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / "data" / "telegram_signals" / "just_trade_it" / "signals_parsed.jsonl"
OUT = ROOT / "data" / "telegram_signals" / "just_trade_it" / "backtest_results_net.jsonl"


def main() -> None:
    sigs = [json.loads(l) for l in open(SIGNALS)]
    rows = []
    for s in sigs:
        ts = int(datetime.fromisoformat(s["date"]).timestamp() * 1000)
        klines = fetch_klines(s["symbol"], ts)
        if not klines:
            continue
        entry = float(klines[0][4])
        stop_dist_pct = abs(entry - s["stop"]) / entry
        if stop_dist_pct <= 0 or stop_dist_pct > 0.5:
            continue

        r = simulate_managed_trade(klines, entry, s["stop"], s["takes"], s["direction"], be_rule="tp1_only")
        exit_ts = ts + r.bars_walked * 5 * 60 * 1000
        funding = fetch_funding(s["symbol"], ts, exit_ts)
        sign = 1 if s["direction"] == "LONG" else -1
        funding_cost_pct = sum(sign * float(fe["fundingRate"]) for fe in funding)
        cost_r = (ROUND_TRIP_FEE_PCT + SLIPPAGE_PCT + funding_cost_pct) / stop_dist_pct
        net_r = r.weighted_r - cost_r

        rows.append({
            "msg_id": s["msg_id"],
            "symbol": s["symbol"],
            "direction": s["direction"],
            "entry_approx": entry,
            "n_tp_hit": r.n_tp_hit,
            "hit_stop": r.hit_stop,
            "weighted_r": r.weighted_r,
            "hold_days": round(r.bars_walked * 5 / 60 / 24, 2),
            "cost_r": round(cost_r, 4),
            "weighted_r_net": round(net_r, 4),
        })
        time.sleep(0.03)

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n = len(rows)
    mean_net = sum(r["weighted_r_net"] for r in rows) / n
    print(f"n={n}  mean net R (corrected) = {mean_net:+.4f}  sum = {sum(r['weighted_r_net'] for r in rows):+.1f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

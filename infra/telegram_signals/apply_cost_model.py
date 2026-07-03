"""
Stage 0, step 4: apply a real cost model to the text-era backtest result.

+0.09R mean (backtest_signals.py) is price-only. Two real costs are missing:
  1. Fees + slippage on entry/exit -- fixed % of price, small per trade.
  2. Funding rate -- charged every 8h on the position's full notional while
     held. At 20-80x leverage and multi-day holds (this channel's own data:
     ~52-day walk-forward window needed), funding can dominate.

Converts both into the same R units as the backtest (price-move / stop-
distance) so they subtract directly from the existing weighted_r.

Usage:
    python infra/telegram_signals/apply_cost_model.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / "data" / "telegram_signals" / "just_trade_it" / "signals_parsed.jsonl"
BACKTEST = ROOT / "data" / "telegram_signals" / "just_trade_it" / "backtest_results.jsonl"
FUNDING_CACHE = ROOT / "data" / "telegram_signals" / "just_trade_it" / "funding_cache"

FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
ROUND_TRIP_FEE_PCT = 0.0010  # 0.05% taker each side -- conservative for liquid futures
SLIPPAGE_PCT = 0.0010  # additional round-trip slippage assumption on market fills


def fetch_funding(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    FUNDING_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = FUNDING_CACHE / f"{symbol}_{start_ms}_{end_ms}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    try:
        resp = requests.get(
            FUNDING_URL,
            params={"symbol": f"{symbol}USDT", "startTime": start_ms,
                    "endTime": end_ms, "limit": 1000},
            timeout=10,
        )
        data = resp.json() if resp.status_code == 200 else []
        if not isinstance(data, list):
            data = []
        cache_file.write_text(json.dumps(data))
        return data
    except requests.RequestException:
        return []


def main() -> None:
    sigs = {s["msg_id"]: s for s in (json.loads(l) for l in open(SIGNALS))}
    results = [json.loads(l) for l in open(BACKTEST) if json.loads(l)["status"] == "ok"]

    adjusted = []
    for r in results:
        s = sigs[r["msg_id"]]
        entry_ts = int(datetime.fromisoformat(s["date"]).timestamp() * 1000)
        stop_dist_pct = abs(r["entry_approx"] - s["stop"]) / r["entry_approx"]
        if stop_dist_pct <= 0 or stop_dist_pct > 0.5:  # skip parser-garbage
            continue

        hold_ms = r["bars_walked"] * 5 * 60 * 1000
        exit_ts = entry_ts + hold_ms

        funding_events = fetch_funding(s["symbol"], entry_ts, exit_ts)
        direction_sign = 1 if s["direction"] == "LONG" else -1
        # Long pays funding when rate is positive, receives when negative
        # (and vice versa for short) -- standard perp convention.
        funding_cost_pct = sum(
            direction_sign * float(fe["fundingRate"]) for fe in funding_events
        )

        cost_pct = ROUND_TRIP_FEE_PCT + SLIPPAGE_PCT + funding_cost_pct
        cost_r = cost_pct / stop_dist_pct

        adjusted.append({
            **r,
            "hold_days": round(hold_ms / 1000 / 3600 / 24, 2),
            "funding_events": len(funding_events),
            "funding_cost_pct": round(funding_cost_pct * 100, 4),
            "cost_r": round(cost_r, 4),
            "weighted_r_net": round(r["weighted_r"] - cost_r, 4),
        })
        time.sleep(0.05)

    n = len(adjusted)
    mean_gross = sum(a["weighted_r"] for a in adjusted) / n
    mean_net = sum(a["weighted_r_net"] for a in adjusted) / n
    mean_cost = sum(a["cost_r"] for a in adjusted) / n
    mean_hold = sum(a["hold_days"] for a in adjusted) / n

    print(f"n = {n}")
    print(f"Mean hold time: {mean_hold:.2f} days")
    print(f"Mean cost (fee+slip+funding), in R units: {mean_cost:.4f}")
    print(f"Mean weighted R  gross (price-only): {mean_gross:+.4f}")
    print(f"Mean weighted R  net (after costs):  {mean_net:+.4f}")
    print(f"Sum weighted R net: {sum(a['weighted_r_net'] for a in adjusted):+.1f}")
    n_flipped = sum(1 for a in adjusted if a["weighted_r"] > 0 and a["weighted_r_net"] <= 0)
    print(f"Trades flipped from win to loss by costs alone: {n_flipped}")

    out = ROOT / "data" / "telegram_signals" / "just_trade_it" / "backtest_results_net.jsonl"
    with open(out, "w") as f:
        for a in adjusted:
            f.write(json.dumps(a) + "\n")


if __name__ == "__main__":
    main()

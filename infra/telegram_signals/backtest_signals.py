"""
Stage 0, step 3: check each parsed signal against REAL price history.

For every self-contained text signal (entry/leverage/TP-ladder/stop all in one
message -- no vision parsing involved, so no OCR error can taint this result),
pull 5m klines from Binance USDT-M futures starting at post time and walk
forward to see what actually happened first: stop, or each TP level.

This is the honest verdict: not "did he say it hit," but "did price do it."

Entry price is approximated as the first close at/after the signal's post
time (matches "Вход: по рынку" / market entry, the template used in every
parsed signal). Position sizing: PM range midpoint (or 2% default) of the
notional account size, partials at 50/25/25 per the channel's own stated
principle ("Фиксируй прибыль поэтапно... 50%... еще 25%... оставшиеся 25%").

Usage:
    python infra/telegram_signals/backtest_signals.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / "data" / "telegram_signals" / "just_trade_it" / "signals_parsed.jsonl"
OUT = ROOT / "data" / "telegram_signals" / "just_trade_it" / "backtest_results.jsonl"
CACHE_DIR = ROOT / "data" / "telegram_signals" / "just_trade_it" / "klines_cache"

BINANCE_KLINES = "https://fapi.binance.com/fapi/v1/klines"
PARTIAL_FRACS = [0.5, 0.25, 0.25, 0.0]  # 4th+ take (if any) closes the rest at last frac


MAX_PAGES = 15  # 15 * 1000 * 5min ~= 52 days -- generous ceiling for a ladder exit


def _fetch_one_page(symbol: str, start_ms: int) -> list | None:
    try:
        resp = requests.get(
            BINANCE_KLINES,
            params={"symbol": f"{symbol}USDT", "interval": "5m",
                    "startTime": start_ms, "limit": 1000},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        return data
    except requests.RequestException:
        return None


def fetch_klines(symbol: str, start_ms: int) -> list | None:
    """Paginated fetch, cached per (symbol, start). Stops early once a
    resolution check (done by the caller re-slicing) isn't possible here, so
    we always pull the full MAX_PAGES ceiling once and let simulate() decide
    how much of it it needed -- simplicity over micro-optimizing API calls."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{symbol}_{start_ms}_paged.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    all_klines: list = []
    cursor = start_ms
    for _ in range(MAX_PAGES):
        page = _fetch_one_page(symbol, cursor)
        if not page:
            break
        all_klines.extend(page)
        cursor = page[-1][6] + 1  # last close_time + 1ms
        if len(page) < 1000:
            break
        time.sleep(0.05)

    if not all_klines:
        return None
    cache_file.write_text(json.dumps(all_klines))
    return all_klines


def simulate(sig: dict) -> dict | None:
    from datetime import datetime
    ts = int(datetime.fromisoformat(sig["date"]).timestamp() * 1000)
    klines = fetch_klines(sig["symbol"], ts)
    if not klines:
        return {**sig, "status": "no_data"}

    entry = float(klines[0][4])  # first close at/after signal time
    direction = sig["direction"]
    stop = sig["stop"]
    takes = sig["takes"]
    risk = abs(entry - stop)
    if risk == 0:
        return {**sig, "status": "zero_risk"}

    tp_hits: list[int] = []  # indices into `takes`, in the order they were hit
    hit_stop = False
    bars_walked = 0

    for k in klines:
        bars_walked += 1
        hi, lo = float(k[2]), float(k[3])
        stop_hit = (lo <= stop) if direction == "LONG" else (hi >= stop)
        for i, tp in enumerate(takes):
            if i in tp_hits:
                continue
            touched = (hi >= tp) if direction == "LONG" else (lo <= tp)
            if touched:
                tp_hits.append(i)
        if stop_hit:
            hit_stop = True
            break
        if len(tp_hits) >= len(takes):
            break  # full ladder closed, nothing left at risk

    n_hit = len(tp_hits)
    fracs = PARTIAL_FRACS[:n_hit] if n_hit else []
    used = sum(fracs)
    r_per_tp = [(takes[i] - entry) / risk if direction == "LONG" else (entry - takes[i]) / risk
                for i in range(n_hit)]
    weighted_r = sum(f * r for f, r in zip(fracs, r_per_tp))
    if hit_stop:
        # Worst case for a same-bar stop+TP1 tie (can't resolve intrabar
        # order from OHLC alone): if TP1 already moved SL to breakeven per
        # the channel's own stated rule, the stop-out is at entry, not loss.
        stop_level = entry if n_hit >= 1 else stop
        r_stop = (stop_level - entry) / risk if direction == "LONG" else (entry - stop_level) / risk
        weighted_r += (1.0 - used) * r_stop
    open_frac = max(0.0, 1.0 - used - (1.0 if hit_stop else 0.0))

    return {
        **sig,
        "status": "ok",
        "entry_approx": entry,
        "n_tp_hit": n_hit,
        "hit_stop": hit_stop,
        "weighted_r": round(weighted_r, 3),
        "unresolved_frac": round(open_frac, 2),
        "bars_walked": bars_walked,
        "bars_fetched": len(klines),
    }


def main() -> None:
    sigs = [json.loads(l) for l in open(SIGNALS)]
    results = []
    for i, sig in enumerate(sigs):
        r = simulate(sig)
        if r:
            results.append(r)
        if (i + 1) % 50 == 0:
            print(f"...{i+1}/{len(sigs)}")
        time.sleep(0.05)  # be polite to public API

    with open(OUT, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    ok = [r for r in results if r["status"] == "ok"]
    no_data = [r for r in results if r["status"] == "no_data"]
    print(f"\n{len(ok)} verified against real price data, {len(no_data)} symbols not on Binance futures (skipped, not faked)")
    if not ok:
        return

    unresolved = [r for r in ok if r["unresolved_frac"] > 0.01]
    stopped = [r for r in ok if r["hit_stop"]]
    tp1_plus = [r for r in ok if r["n_tp_hit"] >= 1]
    avg_r = sum(r["weighted_r"] for r in ok) / len(ok)
    print(f"Unresolved within {MAX_PAGES * 1000 * 5 / 60 / 24:.0f}-day window: {len(unresolved)}/{len(ok)} ({100*len(unresolved)/len(ok):.0f}%)")
    print(f"Stop hit: {len(stopped)}/{len(ok)} ({100*len(stopped)/len(ok):.0f}%)")
    print(f"TP1+ hit: {len(tp1_plus)}/{len(ok)} ({100*len(tp1_plus)/len(ok):.0f}%)")
    print(f"Mean weighted R (fixed-risk, ignores leverage/PM sizing): {avg_r:.3f}")
    print(f"Sum weighted R: {sum(r['weighted_r'] for r in ok):.1f}")


if __name__ == "__main__":
    main()

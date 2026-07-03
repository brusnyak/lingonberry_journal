"""
End-to-end pilot: two real signals (VELVET, WLD), ground-truth chart values,
our sizing + trade management, against real Binance price history.

Usage:
    python infra/telegram_signals/run_pilot.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.telegram_signals.backtest_signals import fetch_klines
from infra.telegram_signals.position_sizer import size_trade
from infra.telegram_signals.trade_manager import simulate_managed_trade

CASES = [
    dict(symbol="VELVET", direction="SHORT", entry=1.6223, stop=1.9757,
         takes=[1.2055, 0.7642, 0.4984], post_time="2026-06-30T16:54:07+00:00"),
    dict(symbol="WLD", direction="SHORT", entry=0.5308, stop=0.5797,
         takes=[0.4783, 0.4123, 0.3633], post_time="2026-06-24T11:26:40+00:00"),
]

ACCOUNT_EQUITY = 300.0
RISK_PCT = 0.015


def main() -> None:
    for c in CASES:
        print(f"\n=== {c['symbol']} {c['direction']} ===")
        sized = size_trade(ACCOUNT_EQUITY, RISK_PCT, c["entry"], c["stop"], c["direction"])
        if sized is None:
            print("SKIPPED: notional below exchange minimum")
            continue
        print(f"Sizing: {sized.leverage}x leverage (safe-computed, not copied from channel), "
              f"notional=${sized.notional}, margin=${sized.margin}, risk=${sized.risk_usd}")

        ts = int(datetime.fromisoformat(c["post_time"]).timestamp() * 1000)
        klines = fetch_klines(c["symbol"], ts)
        if not klines:
            print("No price data available")
            continue

        result = simulate_managed_trade(klines, c["entry"], c["stop"], c["takes"], c["direction"])
        pnl_usd = result.weighted_r * sized.risk_usd
        print(f"Result: TPs hit={result.n_tp_hit}/{len(c['takes'])}  stop_hit={result.hit_stop}  "
              f"BE armed by={result.breakeven_armed_by}  bars={result.bars_walked}")
        print(f"Weighted R: {result.weighted_r:+.3f}  ->  ${pnl_usd:+.2f} on this trade "
              f"(vs ${sized.risk_usd:.2f} risked)")


if __name__ == "__main__":
    main()

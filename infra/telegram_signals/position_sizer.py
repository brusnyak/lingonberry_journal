"""
Risk-managed position sizing -- deliberately ignores the channel's posted
leverage. Stage 0 found 81% of posted stops are wider than the liquidation
distance implied by the posted leverage; copying it literally means the
exchange liquidates before the stop-loss order executes.

Sizing rule: pick the account's OWN leverage from OUR risk budget and the
posted stop distance, capped so liquidation sits comfortably outside the
stop (safety_factor default 0.4 -> liquidation distance is at least 2.5x
the stop distance, covering wicks/slippage/funding drift).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizedTrade:
    entry: float
    stop: float
    direction: str
    leverage: float
    notional: float
    margin: float
    risk_usd: float
    stop_distance_pct: float
    max_safe_leverage: float


def size_trade(
    account_equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    direction: str,
    safety_factor: float = 0.40,
    leverage_ceiling: float = 20.0,
    min_notional: float = 5.0,
) -> SizedTrade | None:
    """
    Returns None if the trade can't be sized safely (e.g. required notional
    is below the exchange minimum -- happens on tiny accounts with wide
    stops; better to skip the trade than force an oversized risk).
    """
    stop_distance_pct = abs(entry - stop) / entry
    if stop_distance_pct <= 0:
        return None

    risk_usd = account_equity * risk_pct
    notional = risk_usd / stop_distance_pct

    max_safe_leverage = min(safety_factor / stop_distance_pct, leverage_ceiling)
    leverage = max(1.0, max_safe_leverage)
    margin = notional / leverage

    if notional < min_notional:
        return None

    return SizedTrade(
        entry=entry, stop=stop, direction=direction, leverage=round(leverage, 1),
        notional=round(notional, 2), margin=round(margin, 2),
        risk_usd=round(risk_usd, 2), stop_distance_pct=round(stop_distance_pct * 100, 2),
        max_safe_leverage=round(max_safe_leverage, 1),
    )


if __name__ == "__main__":
    # The two pilot trades, ground-truth values (manually read from chart).
    cases = [
        ("VELVET", "SHORT", 1.6223, 1.9757),
        ("WLD", "SHORT", 0.5308, 0.5797),
    ]
    for symbol, direction, entry, stop in cases:
        t = size_trade(account_equity=300.0, risk_pct=0.015, entry=entry, stop=stop, direction=direction)
        print(f"{symbol} {direction}: entry={entry} stop={stop}")
        if t is None:
            print("  -> SKIPPED: notional below exchange minimum at this risk/stop combo")
        else:
            print(f"  stop_dist={t.stop_distance_pct}%  safe_leverage={t.leverage}x "
                  f"(their posted leverage would be unsafe here)")
            print(f"  notional=${t.notional}  margin=${t.margin}  risk=${t.risk_usd}")

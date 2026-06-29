"""Lvl 3 — Opening-Range Breakout: measure honest (W, b, F) net of cost.

Causal setup, per session per day:
  1. Opening range (OR) = high/low over the first OR_MIN minutes of the session.
  2. First break of OR high -> long (stop-entry at OR high), of OR low -> short.
  3. Risk = OR range. Stop = opposite OR side. Target = TP_R * risk.
  4. No fill within trade window -> skip. Neither stop/target hit by window end
     -> time-exit at last close. SL assumed before TP if a bar spans both.
  5. Cost = one spread per round trip, charged in R (spread / risk).

Output: trade count, win rate, avg win/loss in R, payoff b, expectancy, all net
of cost, plus trades-per-30-calendar-days -> fed into feasibility.p_pass for the
actual probability of passing 8%/<3%DD. Win rate is NOT the goal; b and F are.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from daily_engine.feasibility import p_pass

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "market_data"

# UTC session OR-start times (London ~07:00, NY ~13:00). DST shifts these ±1h;
# acceptable for a first measurement, flagged.
SESSIONS = {"london": (7, 0), "ny": (13, 0)}
OR_MIN = 30
TRADE_HOURS = 5          # window after OR close to catch the break + resolve
# Conservative retail/prop round-trip spreads, in PRICE units (cost_R = spread/risk
# is unit-consistent since risk is also in price units).
SPREADS = {
    "EURUSD": 0.00008, "GBPUSD": 0.00015, "GBPAUD": 0.00035, "AUDUSD": 0.00012,
    "GBPJPY": 0.020, "EURJPY": 0.015, "AUDJPY": 0.015, "CHFJPY": 0.020,
}
DEFAULT_SPREAD = 0.00020


def spread_for(sym: str) -> float:
    return SPREADS.get(sym, DEFAULT_SPREAD)


def load_intraday(symbol: str, tf: str = "5") -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / f"{symbol}{tf}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.set_index("ts").sort_index()[["open", "high", "low", "close"]]


def session_trades(df: pd.DataFrame, tp_R: float, spread: float = DEFAULT_SPREAD,
                   mode: str = "break") -> list[float]:
    """Return list of net-of-cost R outcomes across all sessions/days.

    mode="break": trade the OR breakout (continuation).
    mode="fade":  fade the OR break (mean-reversion) — short the high-break, long
                  the low-break; stop one OR-range beyond, target back into range.
    """
    sgn = 1 if mode == "break" else -1
    out: list[float] = []
    for date, day in df.groupby(df.index.date):
        for (sh, sm) in SESSIONS.values():
            or_start = pd.Timestamp(date, tz="UTC") + pd.Timedelta(hours=sh, minutes=sm)
            or_end = or_start + pd.Timedelta(minutes=OR_MIN)
            win_end = or_end + pd.Timedelta(hours=TRADE_HOURS)

            orw = day[(day.index >= or_start) & (day.index < or_end)]
            if len(orw) < 3:
                continue
            orh, orl = orw["high"].max(), orw["low"].min()
            risk = orh - orl
            if risk < 2 * spread:        # OR too tight -> cost dominates, skip
                continue
            cost_R = spread / risk

            post = day[(day.index >= or_end) & (day.index < win_end)]
            if post.empty:
                continue

            entered = 0          # +1 long / -1 short
            entry = sl = tp = 0.0
            res = None
            for _, bar in post.iterrows():
                hi, lo, cl = bar["high"], bar["low"], bar["close"]
                if entered == 0:
                    if hi >= orh:                  # break up
                        bdir, brk = 1, orh
                    elif lo <= orl:                # break down
                        bdir, brk = -1, orl
                    else:
                        continue
                    d = bdir * sgn                 # fade flips the side
                    entered, entry = d, brk
                    sl = entry - d * risk
                    tp = entry + d * tp_R * risk
                    # allow same bar to resolve below
                if entered == 1:
                    if lo <= sl:
                        res = -1.0; break
                    if hi >= tp:
                        res = tp_R; break
                elif entered == -1:
                    if hi >= sl:
                        res = -1.0; break
                    if lo <= tp:
                        res = tp_R; break
            if entered != 0 and res is None:     # time exit
                last = post["close"].iloc[-1]
                res = (last - entry) / risk if entered == 1 else (entry - last) / risk
            if res is not None:
                out.append(res - cost_R)
    return out


def stats(R: list[float], n_days_span: float) -> dict:
    a = np.array(R)
    wins, losses = a[a > 0], a[a <= 0]
    W = len(wins) / len(a) if len(a) else 0.0
    aw = wins.mean() if len(wins) else 0.0
    al = -losses.mean() if len(losses) else 0.0
    b = aw / al if al > 0 else float("inf")
    return dict(
        N=len(a), W=round(W, 3), avg_win_R=round(aw, 2), avg_loss_R=round(al, 2),
        b=round(b, 2), exp_R=round(a.mean(), 3),
        F_per_30d=round(len(a) / n_days_span * 30, 1),
    )


def main() -> None:
    import sys
    syms = sys.argv[1:] if len(sys.argv) > 1 else ["EURUSD"]
    for sym in syms:
      df = load_intraday(sym, "5")
      spread = spread_for(sym)
      span_days = (df.index.max() - df.index.min()).days
      print(f"=== {sym} 5m ORB  London+NY  OR={OR_MIN}m  spread={spread}  span={span_days}d "
            f"({df.index.min().date()}->{df.index.max().date()}) ===")
      for mode in ["break", "fade"]:
        print(f" [{mode}]  {'tp_R':>4} {'N':>5} {'W':>6} {'avgW':>6} {'avgL':>6} {'b':>6} {'expR':>7} {'F/30d':>7}  P(pass@r=0.5%)")
        for tp_R in [1.0, 1.5, 2.0, 3.0]:
          R = session_trades(df, tp_R, spread, mode)
          if not R:
              print(f"        {tp_R:>4}  no trades"); continue
          s = stats(R, span_days)
          pp = p_pass(s["W"], s["b"] if np.isfinite(s["b"]) else 5.0, int(round(s["F_per_30d"])), 0.005)
          print(f"        {tp_R:>4} {s['N']:>5} {s['W']:>6} {s['avg_win_R']:>6} {s['avg_loss_R']:>6} "
                f"{s['b']:>6} {s['exp_R']:>7} {s['F_per_30d']:>7}  {pp:>6.2f}")
      print()


if __name__ == "__main__":
    main()

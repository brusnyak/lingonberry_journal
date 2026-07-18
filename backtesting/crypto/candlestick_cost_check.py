"""
Cost the two candlestick patterns that survived the MTF screen
(bearish_engulfing, shooting_star; 15m-EMA-bias-aligned, 5m entry) with
real BingX fees + slippage sweep, same rigor ORB already got. Screener
gave raw R-multiples only -- this converts to $ PnL on a $20 account with
real fees/slippage/min-notional, the step that's actually decisive.

Usage: python -m backtesting.crypto.candlestick_cost_check
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data, load_funding_rate
from backtesting.features_v2.registry import registry
from backtesting.engine.costs import CryptoCosts

PAIRS = ["DOGEUSDT", "XRPUSDT", "SOLUSDT"]
PATTERNS = ["bearish_engulfing", "shooting_star"]
EXCHANGE = "bingx"
ATR_MULT = 1.5
RISK_R = 2.0
HORIZON_BARS = 48
SLIPPAGE_SWEEP = [0.0, 0.0005, 0.0010]


def _atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()


def _htf_bias(df15: pd.DataFrame) -> pd.Series:
    ema21 = df15["close"].ewm(span=21, adjust=False).mean()
    ema55 = df15["close"].ewm(span=55, adjust=False).mean()
    bias = pd.Series("neutral", index=df15.index)
    bias[(ema21 > ema55) & (ema21.diff() > 0)] = "bullish"
    bias[(ema21 < ema55) & (ema21.diff() < 0)] = "bearish"
    return bias


def collect_signals(pair: str, pattern: str):
    df15 = load_data(pair, tf="15", exchange=EXCHANGE).sort_values("ts").reset_index(drop=True)
    df5 = load_data(pair, tf="5", exchange=EXCHANGE).sort_values("ts").reset_index(drop=True)
    bias15 = _htf_bias(df15)
    bias_df = pd.DataFrame({"ts": df15["ts"], "bias": bias15.values})
    merged = pd.merge_asof(df5[["ts"]], bias_df, on="ts", direction="backward")
    bias5 = merged["bias"].fillna("neutral").to_numpy()
    atr5 = _atr(df5, 14)
    open_, high, low, close = df5["open"].values, df5["high"].values, df5["low"].values, df5["close"].values
    sig = registry.run(pattern, open_, high, low, close)

    entries = []  # (entry_idx, direction, entry_price, sl_price, tp_price)
    for i in range(60, len(df5) - HORIZON_BARS - 1):
        s = sig[i]
        if s == 0 or atr5[i] != atr5[i] or atr5[i] <= 0:
            continue
        direction = "long" if s == 1 else "short"
        if direction == "long" and bias5[i] != "bullish":
            continue
        if direction == "short" and bias5[i] != "bearish":
            continue
        entry = float(close[i])
        risk = ATR_MULT * float(atr5[i])
        sl = entry - risk if direction == "long" else entry + risk
        tp = entry + RISK_R * risk if direction == "long" else entry - RISK_R * risk
        entries.append((i, direction, entry, sl, tp))
    return df5, entries


def cost_signals(df5: pd.DataFrame, entries: list, costs: CryptoCosts, initial_equity: float = 20.0) -> dict:
    """Walk each signal forward on df5 bars, apply real fees/slippage, fixed 2R/SL, no BE (raw)."""
    equity = initial_equity
    pnls = []
    for entry_idx, direction, entry, sl, tp in entries:
        risk_price = abs(entry - sl)
        lots = costs.calc_lots(equity, risk_pct=0.005, stop_dist_price=risk_price, price=entry)
        if lots <= 0:
            continue
        fill_entry = costs.entry_fill(entry, direction)
        end_i = min(entry_idx + HORIZON_BARS, len(df5) - 1)
        exit_price, is_sl = None, False
        for j in range(entry_idx + 1, end_i + 1):
            hi, lo = float(df5["high"].iat[j]), float(df5["low"].iat[j])
            if direction == "long":
                hit_tp, hit_sl = hi >= tp, lo <= sl
            else:
                hit_tp, hit_sl = lo <= tp, hi >= sl
            if hit_sl:
                exit_price, is_sl = sl, True
                break
            if hit_tp:
                exit_price, is_sl = tp, False
                break
        if exit_price is None:
            exit_price = float(df5["close"].iat[end_i])
        fill_exit = costs.exit_fill(exit_price, direction, is_sl=is_sl)
        gross = costs.pnl(fill_entry, fill_exit, direction, lots)
        fees = costs.entry_commission(lots, fill_entry) + costs.exit_commission(lots, fill_exit, is_sl=is_sl)
        net = gross - fees
        pnls.append(net)
        equity += net  # compound, matches how the account actually behaves

    pnls = np.array(pnls)
    if len(pnls) == 0:
        return {"n": 0}
    wins, losses = pnls[pnls > 0].sum(), -pnls[pnls < 0].sum()
    pf = wins / losses if losses > 0 else float("inf")
    return {
        "n": len(pnls), "win_rate": float((pnls > 0).mean()),
        "pf": pf, "total_pnl": float(pnls.sum()),
        "return_pct": float(pnls.sum() / initial_equity),
        "final_equity": float(equity),
    }


def main():
    rows = []
    for pair in PAIRS:
        for pattern in PATTERNS:
            df5, entries = collect_signals(pair, pattern)
            funding_df = load_funding_rate(pair, exchange=EXCHANGE)
            for slip in SLIPPAGE_SWEEP:
                costs = CryptoCosts(
                    maker_fee=0.0002, taker_fee=0.0005, leverage=50.0,
                    funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
                    min_notional=2.0, entry_slippage_pct=slip, sl_slippage_pct=slip,
                )
                stats = cost_signals(df5, entries, costs)
                rows.append({"pair": pair, "pattern": pattern, "slippage_pct": slip * 100, **stats})

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 180)
    print(df.to_string(index=False))
    out = ROOT / "backtesting" / "crypto" / "reports" / "candlestick_cost_check.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()

"""
MTF candlestick-pattern scalp screener.

Shape requested: 15m structure bias -> 5m entry trigger -> quick in/out,
position-manager-protected (breakeven once the trade is far enough in
profit, so a real winner can never walk back to a real loser). Scans ALL
17 registered candle patterns (backtesting/features_v2) rather than
committing to one upfront -- this is the "quantity approach" pass to see
which patterns (if any) show real signal in this MTF+managed context,
before costing/validating whichever survive.

Mechanics:
  - 15m bias: EMA21 vs EMA55 slope direction (simple, causal, no structure_lib
    dependency at this layer -- deliberately kept simple per the request).
  - 5m entry: candle pattern signal must agree with the 15m bias (long
    pattern + bullish bias, short pattern + bearish bias). No signal on
    neutral/disagreeing bias.
  - SL: 1.5x ATR(14) on 5m. TP: fixed 2R. Managed via position_manager's
    walk_managed_outcome (BE at 50% target OR on 5m BOS-against), which
    caps the worst-case managed outcome at 0R once triggered.
  - Reports BOTH managed and unmanaged R so the position manager's actual
    lift is visible, not assumed.

Raw R-multiples only, no fees/slippage yet -- this is the screening pass
(matches how this project's other pattern grids screen first, cost second).

Usage: python -m backtesting.crypto.mtf_scalp_screener
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from backtesting.features_v2.registry import registry
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.crypto.position_manager import walk_managed_outcome, PositionManagerConfig

PAIRS = ["DOGEUSDT", "XRPUSDT", "SOLUSDT"]  # real BingX history already on disk, no wait
EXCHANGE = "bingx"
RISK_R = 2.0        # fixed 2R target
ATR_MULT = 1.5      # SL distance = 1.5x ATR(14) on entry tf
HORIZON_BARS = 48   # 48 x 5m = 4h max hold -- "get in, get profit, get out"
MIN_SIGNALS = 15    # below this, don't report (too thin to read)


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


def screen_pair(pair: str) -> list[dict]:
    df15 = load_data(pair, tf="15", exchange=EXCHANGE)
    df5 = load_data(pair, tf="5", exchange=EXCHANGE)
    if df15.empty or df5.empty or len(df5) < 200:
        return [{"pair": pair, "pattern": "-", "error": "insufficient data"}]

    df15 = df15.sort_values("ts").reset_index(drop=True)
    df5 = df5.sort_values("ts").reset_index(drop=True)

    bias15 = _htf_bias(df15)
    bias_df = pd.DataFrame({"ts": df15["ts"], "bias": bias15.values})
    # merge_asof: each 5m bar gets the bias of the most recently CLOSED 15m bar (causal)
    merged = pd.merge_asof(df5[["ts"]], bias_df, on="ts", direction="backward")
    bias5 = merged["bias"].fillna("neutral").to_numpy()

    atr5 = _atr(df5, 14)

    swings, levels = swing_points(df5, swing_length=3, causal=True)
    struct5 = label_structure(df5, swings, levels)
    struct5 = struct5.rename(columns={"bullish_bos": "bos_up", "bearish_bos": "bos_down"})

    open_, high, low, close = df5["open"].values, df5["high"].values, df5["low"].values, df5["close"].values

    rows = []
    for pname in registry.names:
        try:
            sig = registry.run(pname, open_, high, low, close)
        except Exception as e:
            rows.append({"pair": pair, "pattern": pname, "error": f"{type(e).__name__}: {e}"})
            continue

        managed_r, unmanaged_r = [], []
        for i in range(60, len(df5) - HORIZON_BARS - 1):
            s = sig[i]
            if s == 0 or atr5[i] != atr5[i] or atr5[i] <= 0:  # NaN-safe
                continue
            direction = "long" if s == 1 else "short"
            if direction == "long" and bias5[i] != "bullish":
                continue
            if direction == "short" and bias5[i] != "bearish":
                continue

            entry = float(close[i])
            risk = ATR_MULT * float(atr5[i])
            if risk <= 0:
                continue
            sl = entry - risk if direction == "long" else entry + risk
            tp = entry + RISK_R * risk if direction == "long" else entry - RISK_R * risk

            m = walk_managed_outcome(df5, i, direction, sl, tp, horizon=HORIZON_BARS,
                                      structure=struct5,
                                      config=PositionManagerConfig(be_on_bos_against=True, be_at_50pct_target=True))
            u = walk_managed_outcome(df5, i, direction, sl, tp, horizon=HORIZON_BARS,
                                      structure=struct5,
                                      config=PositionManagerConfig(be_on_bos_against=False, be_at_50pct_target=False))
            if m:
                managed_r.append(m["r_multiple"])
            if u:
                unmanaged_r.append(u["r_multiple"])

        if len(managed_r) < MIN_SIGNALS:
            continue

        def _stats(rs: list[float]) -> dict:
            arr = np.array(rs)
            wins = arr[arr > 0].sum()
            losses = -arr[arr < 0].sum()
            pf = wins / losses if losses > 0 else float("inf")
            return {"n": len(arr), "win_rate": float((arr > 0).mean()), "pf": pf, "avg_r": float(arr.mean())}

        ms, us = _stats(managed_r), _stats(unmanaged_r)
        rows.append({
            "pair": pair, "pattern": pname,
            "n": ms["n"], "managed_wr": ms["win_rate"], "managed_pf": ms["pf"], "managed_avg_r": ms["avg_r"],
            "unmanaged_wr": us["win_rate"], "unmanaged_pf": us["pf"], "unmanaged_avg_r": us["avg_r"],
            "error": None,
        })
    return rows


def main():
    all_rows = []
    for pair in PAIRS:
        all_rows.extend(screen_pair(pair))

    df = pd.DataFrame(all_rows)
    valid = df[df.get("error").isna()] if "error" in df.columns else df
    if not valid.empty:
        valid = valid.sort_values("managed_pf", ascending=False)
        pd.set_option("display.width", 180)
        print(valid.to_string(index=False))
    else:
        print("No pattern cleared MIN_SIGNALS on any pair.")
        print(df.to_string(index=False))

    out = ROOT / "backtesting" / "crypto" / "reports" / "mtf_scalp_screener.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()

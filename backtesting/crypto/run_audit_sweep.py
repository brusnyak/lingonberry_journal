"""
Audit sweep: multi-asset, multi-window, non-overlapping intervals.
Runs clean strategies (no look-ahead) across all core pairs.

Usage:
    python -m backtesting.crypto.run_audit_sweep
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.crypto.data_quality import require_funding_coverage

# ── Strategies (only clean ones for audit) ──
from backtesting.crypto.strategies.bos_fade import TrBosFade
from backtesting.crypto.strategies.tsmom_breakout import CryptoTsmomBreakout

CORE_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]

# Non-overlapping date windows for each duration
WINDOWS = {
    "7d":   [(90, 83), (83, 76), (76, 69), (69, 62), (62, 55)],  # last 5 weeks
    "30d":  [(120, 90), (90, 60), (60, 30), (30, 0)],
    "60d":  [(180, 120), (120, 60), (60, 0)],
    "90d":  [(270, 180), (180, 90), (90, 0)],
}


def _load_market_specs(pair: str, exchange: str = "binance") -> dict:
    spec_path = Path("data/market_data/crypto") / exchange / "market_specs.parquet"
    if not spec_path.exists():
        return {}
    try:
        specs = pd.read_parquet(spec_path)
        pair_specs = specs[specs["id"] == pair.upper()]
        if pair_specs.empty:
            return {}
        latest = pair_specs.sort_values("ts").iloc[-1]
        return {
            "min_notional": float(latest.get("min_notional", 0) or 0),
            "min_qty": float(latest.get("min_qty", 0) or 0),
            "qty_step": float(latest.get("amount_precision", 0) or 0),
            "tick_size": float(latest.get("price_precision", 0) or 0),
        }
    except Exception:
        return {}


def run_one(strategy_cls, pair: str, entry_tf: str, support_tfs: list[str],
            days: int, params: dict, equity: float = 20.0, leverage: float = 50.0,
            allow_stale_funding: bool = False) -> dict:
    try:
        tfs = list(dict.fromkeys([entry_tf] + support_tfs))
        data = {}
        for tf in tfs:
            df = load_data(pair, tf=tf, days=days, exchange="binance")
            if df.empty:
                return {"pair": pair, "days": days, "tf": entry_tf,
                        "error": f"no data {tf}", **params}
            data[tf] = df

        funding_df = load_funding_rate(pair, exchange="binance")
        if not allow_stale_funding:
            require_funding_coverage(data, funding_df)
        specs = _load_market_specs(pair)
        costs = CryptoCosts(
            leverage=leverage,
            funding_df=funding_df if not funding_df.empty else None,
            min_notional=specs.get("min_notional", 0.0),
            min_qty=specs.get("min_qty", 0.0),
            qty_step=specs.get("qty_step", 0.0),
            tick_size=specs.get("tick_size", 0.0),
        )

        result = run(strategy_cls(**params), data, entry_tf=entry_tf,
                     costs=costs, initial_equity=equity)
        rep = result.report
        return {
            "pair": pair,
            "days": days,
            "tf": entry_tf,
            **params,
            "trades": rep["trades"],
            "win_rate": rep["win_rate"],
            "profit_factor": rep["profit_factor"],
            "payoff_ratio": rep.get("payoff_ratio", 0),
            "avg_r": rep.get("avg_r", 0),
            "total_pnl": rep["total_pnl"],
            "return_pct": rep.get("return_pct", 0),
            "max_drawdown_pct": rep["max_drawdown_pct"],
            "sharpe": rep.get("sharpe", 0),
            "error": None,
        }
    except Exception as e:
        return {"pair": pair, "days": days, "tf": entry_tf,
                "error": f"{type(e).__name__}: {e}", **params}


def run_nonoverlapping(strategy_cls, name: str, strategy_params: dict,
                        entry_tf: str, support_tfs: list[str],
                        equity: float = 20.0, leverage: float = 50.0) -> pd.DataFrame:
    """Run strategy across non-overlapping windows for each pair."""
    rows = []
    total = len(CORE_PAIRS) * sum(len(v) for v in WINDOWS.values())
    done = 0

    for pair in CORE_PAIRS:
        for label, offsets in WINDOWS.items():
            for start_offset, end_offset in offsets:
                # offsets = days_ago, so larger = older
                days = start_offset  # use the full span for data loading
                result = run_one(
                    strategy_cls, pair, entry_tf, support_tfs,
                        days=days, params=strategy_params,
                        equity=equity, leverage=leverage,
                        allow_stale_funding=False,
                )
                result["window"] = label
                result["window_start_ago"] = start_offset
                result["window_end_ago"] = end_offset
                rows.append(result)
                done += 1

                err = result.get("error")
                if err:
                    status = f"ERROR {err}"
                else:
                    status = f"T={result['trades']} PF={result['profit_factor']:.2f} WR={result['win_rate']:.0%}"
                print(f"  [{done}/{total}] {name} {pair} {label} {status}", flush=True)

    return pd.DataFrame(rows)


def print_results(df: pd.DataFrame, title: str):
    print(f"\n{'=' * 120}")
    print(f"  {title}")
    print(f"{'=' * 120}")

    # Filter to successful runs with trades
    ok = df[df["error"].isna() & (df["trades"] >= 3)].copy()
    if ok.empty:
        print("  No valid results")
        return

    # Summarize by pair and window
    for pair in CORE_PAIRS:
        pair_df = ok[ok["pair"] == pair]
        print(f"\n  {pair}:")
        header = f"    {'Window':<6} {'T':>4} {'WR':>6} {'PF':>7} {'RR':>5} {'AvgR':>5} {'PnL':>8} {'Ret%':>6} {'DD%':>6}"
        print(header)
        print("    " + "-" * len(header.strip()))
        for label in ["7d", "30d", "60d", "90d"]:
            w = pair_df[pair_df["window"] == label]
            if w.empty:
                continue
            for _, row in w.iterrows():
                print(f"    {label:<6} {row['trades']:>4} {row['win_rate']:>5.0%} "
                      f"{row['profit_factor']:>6.2f} {row['payoff_ratio']:>4.2f} "
                      f"{row['avg_r']:>4.2f} {row['total_pnl']:>7.2f} "
                      f"{row['return_pct']:>5.0%} {row['max_drawdown_pct']:>5.1%}")

    # Aggregate stats
    print(f"\n  AGGREGATE (all windows with >=3 trades):")
    print(f"    Windows: {len(ok)}")
    print(f"    Median PF: {ok['profit_factor'].median():.2f}")
    print(f"    Median WR: {ok['win_rate'].median():.0%}")
    print(f"    Median avgR: {ok['avg_r'].median():.2f}")
    print(f"    Profitable windows (PF>1): {(ok['profit_factor']>1).mean():.0%}")
    print(f"    Median return%: {ok['return_pct'].median():.1%}")
    print(f"    Median DD%: {ok['max_drawdown_pct'].median():.1%}")
    print(f"    Mean trades/window: {ok['trades'].mean():.0f}")


def main():
    print("=" * 80)
    print("  CRYPTO AUDIT SWEEP — Multi-asset, Multi-window")
    print("  ===============================================")
    print(f"  Pairs: {', '.join(CORE_PAIRS)}")
    print(f"  Windows: 7d×5, 30d×4, 60d×3, 90d×3 = 15 windows/pair × 6 pairs = 90 runs/strategy")
    print(f"  Risk: 5% (scaling_plan default)")
    print(f"  Equity: $20 @ 50x")
    print(f"\n  Clean strategies only (no pre-computed signal look-ahead)")
    print("=" * 80)

    # ── TrBosFade ──────────────────────────────────────────────
    print("\n\n" + "#" * 80)
    print("  Strategy: TrBosFade")
    print("  Best config from DOGE 7d: lookback=30, sl=8, tp1_r=1.5, direction=bull")
    print("#" * 80)
    t0 = time.time()
    bf_params = {"bos_lookback": 30, "sl_buffer_pips": 8, "tp1_r": 1.5,
                 "risk_pct": 0.05, "direction": "bull"}
    df_bf = run_nonoverlapping(TrBosFade, "TrBosFade", bf_params,
                                entry_tf="5", support_tfs=["60", "240"])
    print(f"  Elapsed: {time.time() - t0:.1f}s")
    print_results(df_bf, "TrBosFade — Multi-window audit")

    # ── CryptoTsmomBreakout ─────────────────────────────────────
    print("\n\n" + "#" * 80)
    print("  Strategy: CryptoTsmomBreakout (Donchian)")
    print("  Default params")
    print("#" * 80)
    t0 = time.time()
    tsmom_params = {"risk_pct": 0.05}
    df_tsmom = run_nonoverlapping(CryptoTsmomBreakout, "CryptoTsmom", tsmom_params,
                                   entry_tf="60", support_tfs=["240"])
    print(f"  Elapsed: {time.time() - t0:.1f}s")
    print_results(df_tsmom, "CryptoTsmomBreakout — Multi-window audit")

    # ── Save results ────────────────────────────────────────────
    output_dir = Path("backtesting/results")
    output_dir.mkdir(exist_ok=True)
    df_bf.to_csv(output_dir / "audit_tr_bos_fade.csv", index=False)
    df_tsmom.to_csv(output_dir / "audit_crypto_tsmom.csv", index=False)
    print(f"\n  Results saved to backtesting/results/audit_*.csv")


if __name__ == "__main__":
    main()

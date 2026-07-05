"""
Crypto batch runner — backtest strategies on crypto futures pairs.

Usage:
    python -m backtesting.crypto_batch
    python -m backtesting.crypto_batch --sweep tr_fvg  # sweep one strategy

Sweeps every (pair, tf, param_combo) with CryptoCosts (fees, funding, liquidation).
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Type

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.crypto.validation import RollingValidation, rolling_validate, print_validation_table
from backtesting.engine.base import Strategy
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run


# Core universe: liquid, low min notional, high volatility
CORE_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
]
# Aggressive: higher vol, lower min notional
ALT_PAIRS = [
    "1000PEPEUSDT", "WLDUSDT", "SUIUSDT", "AAVEUSDT", "AVAXUSDT", "LINKUSDT",
    "NEARUSDT", "HYPEUSDT",
]

DEFAULT_PAIRS = CORE_PAIRS + ALT_PAIRS
EXCHANGES = ("binance", "bybit")


@dataclass
class CryptoRunConfig:
    pair: str
    entry_tf: str
    support_tfs: list[str] = field(default_factory=lambda: ["240"])
    params: dict = field(default_factory=dict)
    exchange: str = "binance"
    start: Optional[str] = None
    end: Optional[str] = None
    days: Optional[int] = 30
    initial_equity: float = 20.0
    leverage: float = 50.0


def _load_market_specs(pair: str, exchange: str) -> dict:
    """Load latest market specs for a pair from exchange market_specs.parquet."""
    spec_path = Path("data/market_data/crypto") / exchange.lower() / "market_specs.parquet"
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


def _run_one_crypto(strategy_cls: Type[Strategy], cfg: CryptoRunConfig) -> dict:
    try:
        tfs = list(dict.fromkeys([cfg.entry_tf] + cfg.support_tfs))
        data: dict[str, pd.DataFrame] = {}
        for tf in tfs:
            df = load_data(cfg.pair, tf=tf, days=cfg.days, start=cfg.start, end=cfg.end,
                           exchange=cfg.exchange)
            if df.empty:
                return _err(cfg, f"no data: {cfg.pair} {cfg.exchange} tf={tf}")
            data[tf] = df

        # Build CryptoCosts with funding rates + exchange market specs
        funding_df = load_funding_rate(cfg.pair, exchange=cfg.exchange)
        if funding_df is not None and not funding_df.empty:
            data["funding"] = funding_df  # expose to strategies
        specs = _load_market_specs(cfg.pair, cfg.exchange)
        costs = CryptoCosts(
            leverage=cfg.leverage,
            funding_df=funding_df if not funding_df.empty else None,
            min_notional=specs.get("min_notional", 0.0),
            min_qty=specs.get("min_qty", 0.0),
            qty_step=specs.get("qty_step", 0.0),
            tick_size=specs.get("tick_size", 0.0),
        )

        result = run(
            strategy_cls(**cfg.params),
            data,
            entry_tf=cfg.entry_tf,
            costs=costs,
            initial_equity=cfg.initial_equity,
        )

        rep = result.report
        return {
            "pair": cfg.pair,
            "exchange": cfg.exchange,
            "entry_tf": cfg.entry_tf,
            "leverage": cfg.leverage,
            **cfg.params,
            "trades": rep["trades"],
            "win_rate": rep["win_rate"],
            "profit_factor": rep["profit_factor"],
            "payoff_ratio": rep.get("payoff_ratio", 0),
            "avg_r": rep.get("avg_r", 0),
            "total_pnl": rep["total_pnl"],
            "return_pct": rep.get("return_pct", 0),
            "final_equity": rep.get("final_equity", 0),
            "max_drawdown_pct": rep["max_drawdown_pct"],
            "max_drawdown": rep["max_drawdown"],
            "sharpe": rep.get("sharpe", 0),
            "avg_duration_min": rep.get("avg_duration_min", 0),
            "error": None,
        }
    except Exception as e:
        return _err(cfg, f"{type(e).__name__}: {e}")


def _err(cfg: CryptoRunConfig, msg: str) -> dict:
    return {"pair": cfg.pair, "exchange": cfg.exchange, "entry_tf": cfg.entry_tf, **cfg.params, "error": msg}


def make_crypto_configs(
    strategy_cls: Type[Strategy],
    pairs: list[str] = DEFAULT_PAIRS,
    entry_tfs: list[str] = None,
    support_tfs_map: dict[str, list[str]] = None,
    param_grid: dict[str, list] = None,
    exchanges: list[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    days: Optional[int] = 30,
    initial_equity: float = 20.0,
    leverage: float = 50.0,
    default_risk_pct: float | None = None,
) -> list[CryptoRunConfig]:
    if entry_tfs is None:
        entry_tfs = ["5", "15"]
    if support_tfs_map is None:
        support_tfs_map = {"5": ["60", "240"], "15": ["60", "240"], "3": ["60", "240"]}
    if exchanges is None:
        exchanges = ["binance"]
    if param_grid is None:
        param_grid = getattr(strategy_cls, "spaces", {})

    # Override risk_pct in param_grid if default_risk_pct is set
    if default_risk_pct is not None and "risk_pct" in param_grid:
        param_grid = {**param_grid, "risk_pct": [default_risk_pct]}

    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    configs = []
    for pair, exchange, entry_tf, combo in itertools.product(pairs, exchanges, entry_tfs, combos):
        configs.append(CryptoRunConfig(
            pair=pair,
            entry_tf=entry_tf,
            support_tfs=support_tfs_map.get(entry_tf, ["240"]),
            params=dict(zip(keys, combo)),
            exchange=exchange,
            start=start,
            end=end,
            days=days,
            initial_equity=initial_equity,
            leverage=leverage,
        ))
    return configs


SWEEP_STRATEGIES: dict[str, Type[Strategy]] = {}


def _load_strategies():
    global SWEEP_STRATEGIES
    from backtesting.strategies.tr_fvg import TrFvg
    from backtesting.strategies.tr_accumulation import TrAccumulation
    from backtesting.crypto.strategies.bos_fade import TrBosFade
    from backtesting.crypto.strategies.ict import TrIct
    from backtesting.crypto.strategies.funding_mean_rev import CryptoFundingMeanRev
    from backtesting.crypto.strategies.tsmom_breakout import CryptoTsmomBreakout
    SWEEP_STRATEGIES = {
        "tr_fvg": TrFvg,
        "tr_bos_fade": TrBosFade,
        "tr_accumulation": TrAccumulation,
        "tr_ict": TrIct,
        "crypto_tsmom": CryptoTsmomBreakout,
        "crypto_funding": CryptoFundingMeanRev,
    }


def run_crypto_sweep(
    strategy_cls: Type[Strategy],
    configs: list[CryptoRunConfig],
    workers: int = 1,
    min_trades: int = 5,
    verbose: bool = True,
) -> pd.DataFrame:
    n = len(configs)
    rows = [None] * n

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_one_crypto, strategy_cls, cfg): i for i, cfg in enumerate(configs)}
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                row = fut.result()
                rows[i] = row
                done += 1
                if verbose:
                    cfg = configs[i]
                    err = row.get("error")
                    status = f"ERROR: {str(err)[:60]}" if err else f"T={row.get('trades',0)}  PF={row.get('profit_factor',0):.2f}"
                    print(f"  [{done}/{n}] {cfg.exchange}/{cfg.pair} {cfg.entry_tf}m {cfg.params}  {status}", flush=True)
    else:
        for i, cfg in enumerate(configs, 1):
            if verbose:
                print(f"  [{i}/{n}] {cfg.exchange}/{cfg.pair} {cfg.entry_tf}m {cfg.params}", end="  ", flush=True)
            row = _run_one_crypto(strategy_cls, cfg)
            rows[i - 1] = row
            if verbose:
                err = row.get("error")
                if err:
                    print(f"ERROR: {str(err)[:80]}")
                else:
                    print(f"T={row.get('trades',0)}  PF={row.get('profit_factor',0):.2f}")

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Sort: errors last, then by profit_factor descending
    has_edge = df["error"].isna() & (df.get("trades", 0) >= min_trades)
    df["_rank"] = 0
    df.loc[has_edge, "_rank"] = 1
    df = df.sort_values(["_rank", "profit_factor"], ascending=[False, False])
    df = df.drop(columns=["_rank"])
    return df.reset_index(drop=True)


def print_sweep_table(df: pd.DataFrame, title: str = ""):
    if title:
        print(f"\n{'=' * 100}")
        print(f"  {title}")
        print(f"{'=' * 100}")

    cols = ["pair", "exchange", "entry_tf"]
    # Add param columns
    param_cols = [c for c in df.columns if c not in [
        "pair", "exchange", "entry_tf", "leverage",
        "trades", "win_rate", "profit_factor", "payoff_ratio",
        "avg_r", "total_pnl", "return_pct", "final_equity",
        "max_drawdown_pct", "max_drawdown", "sharpe",
        "avg_duration_min", "error", "_rank",
    ] and c not in getattr(pd, "internal", {})]

    header = f"{'Pair':<15} {'Ex':<8} {'TF':>3} "
    for c in param_cols:
        header += f"{c:<15} "
    header += f"{'T':>4} {'WR':>6} {'PF':>6} {'RR':>5} {'DD%':>6} {'PnL':>8} {'Ret%':>6}"
    print(header)
    print("-" * len(header))

    for _, row in df.iterrows():
        if row.get("error"):
            continue
        line = f"{row['pair']:<15} {row['exchange']:<8} {row['entry_tf']:>3} "
        for c in param_cols:
            v = row.get(c, "")
            line += f"{str(v):<15} "
        line += (f"{row['trades']:>4} "
                 f"{row['win_rate']:>5.0%} "
                 f"{row['profit_factor']:>5.2f} "
                 f"{row['payoff_ratio']:>4.2f} "
                 f"{row['max_drawdown_pct']:>5.1%} "
                 f"{row['total_pnl']:>7.2f} "
                 f"{row['return_pct']:>5.0%}")
        print(line)

    if df.empty:
        print("  No results")
    print("-" * len(header))


def main():
    _load_strategies()
    parser = argparse.ArgumentParser(description="Crypto batch backtesting")
    parser.add_argument("--sweep", choices=list(SWEEP_STRATEGIES.keys()) + ["all"], default="all",
                        help="Strategy to sweep")
    parser.add_argument("--pairs", default=",".join(CORE_PAIRS),
                        help="Comma-separated pairs")
    parser.add_argument("--exchanges", default="binance",
                        help="Comma-separated exchanges")
    parser.add_argument("--tfs", default="5,15",
                        help="Entry timeframes")
    parser.add_argument("--days", type=int, default=30,
                        help="Days of data per window")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel workers")
    parser.add_argument("--equity", type=float, default=20.0,
                        help="Initial equity for $20 scaling test")
    parser.add_argument("--leverage", type=float, default=50.0,
                        help="Leverage")
    parser.add_argument("--risk-pct", type=float, default=None,
                        help="Override risk_pct for all strategies (e.g. 0.05 for 5%%, scaling_plan default)")
    parser.add_argument("--validate", action="store_true",
                        help="Run rolling window validation on top results")
    parser.add_argument("--validate-window", type=int, default=60,
                        help="Validation window days (default 60)")
    parser.add_argument("--validate-step", type=int, default=14,
                        help="Validation step days (default 14)")
    parser.add_argument("--output", default="backtesting/results/crypto_sweep.csv",
                        help="Output CSV path")
    parser.add_argument("--screener-top-n", type=int, default=None,
                        help="Run tier-2 screener and keep top N pairs")
    parser.add_argument("--screener-days", type=int, default=14,
                        help="Days of data for the screener (default 14)")
    args = parser.parse_args()

    pairs = [s.strip().upper() for s in args.pairs.split(",")]
    exchanges = [s.strip().lower() for s in args.exchanges.split(",")]
    tfs = [s.strip() for s in args.tfs.split(",")]

    # ── Optional: filter pairs via tier-2 screener ──
    if args.screener_top_n is not None:
        from backtesting.crypto.screener import screen_pairs, rank_pairs
        ex = exchanges[0] if exchanges else "binance"
        print(f"\n  Running tier-2 screener (top {args.screener_top_n}, "
              f"{args.screener_days}d, {ex})...")
        screened = screen_pairs(days=args.screener_days, exchange=ex)
        if not screened.empty:
            ranked = rank_pairs(screened, top_n=args.screener_top_n)
            screened_pairs = ranked["pair"].tolist()
            # Intersect with user-specified pairs if not all defaults
            if args.pairs != ",".join(CORE_PAIRS):
                screened_pairs = [p for p in screened_pairs if p in pairs]
            if screened_pairs:
                print(f"  Screener selected: {', '.join(screened_pairs)}")
                pairs = screened_pairs
            else:
                print("  Screener returned no matching pairs — using --pairs list")

    # Default risk: 2% for development sweeps. Keeps multiple trades alive without
    # destroying equity on a few losers. Override with --risk-pct for final validation.
    default_risk = args.risk_pct if args.risk_pct is not None else 0.02

    strategies_to_run = list(SWEEP_STRATEGIES.keys()) if args.sweep == "all" else [args.sweep]

    all_dfs = []
    for sname in strategies_to_run:
        cls = SWEEP_STRATEGIES[sname]
        print(f"\n{'#' * 80}")
        print(f"  Strategy: {sname}")
        print(f"{'#' * 80}")

        configs = make_crypto_configs(
            cls, pairs=pairs, entry_tfs=tfs, exchanges=exchanges,
            days=args.days, initial_equity=args.equity, leverage=args.leverage,
            default_risk_pct=default_risk,
        )
        if not configs:
            print("  No configs (strategy has no spaces or no pairs)")
            continue

        t0 = time.time()
        df = run_crypto_sweep(cls, configs, workers=args.workers, min_trades=1)
        elapsed = time.time() - t0

        print_sweep_table(df, title=f"{sname} | {args.days}d | ${args.equity:.0f} @ {args.leverage}x | risk={default_risk:.1%}")
        print(f"  Elapsed: {elapsed:.1f}s")

        # Rolling validation on top configs
        if args.validate:
            top = df[df["error"].isna() & (df["trades"] >= 5)].head(5)
            if not top.empty:
                val_results = []
                for _, row in top.iterrows():
                    cfg = CryptoRunConfig(
                        pair=row["pair"], entry_tf=row["entry_tf"],
                        exchange=row["exchange"], params=row.to_dict(),
                        days=args.days * 6,  # longer data for validation windows
                        initial_equity=args.equity, leverage=args.leverage,
                    )
                    try:
                        vt = _validate_one(cls, cfg, args.validate_window, args.validate_step)
                        label = f"{row['pair']} {row['entry_tf']}m"
                        val_results.append((label, vt))
                    except Exception:
                        pass
                if val_results:
                    print_validation_table(val_results, title=f"{sname} validation: top 5 configs")

        all_dfs.append(df)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        if args.output:
            combined.to_csv(args.output, index=False)
            print(f"\n  Results saved to {args.output}")


def _validate_one(
    strategy_cls: Type[Strategy],
    cfg: CryptoRunConfig,
    window_days: int,
    step_days: int,
) -> RollingValidation:
    """Run a longer backtest and validate across rolling windows."""
    import pandas as pd
    tfs = list(dict.fromkeys([cfg.entry_tf] + cfg.support_tfs))
    data: dict[str, pd.DataFrame] = {}
    for tf in tfs:
        df = load_data(cfg.pair, tf=tf, days=cfg.days, start=cfg.start, end=cfg.end,
                       exchange=cfg.exchange)
        if df.empty:
            return RollingValidation(n_windows=0, n_with_trades=0, n_profitable=0, windows=[])
        data[tf] = df

    funding_df = load_funding_rate(cfg.pair, exchange=cfg.exchange)
    specs = _load_market_specs(cfg.pair, cfg.exchange)
    costs = CryptoCosts(
        leverage=cfg.leverage,
        funding_df=funding_df if not funding_df.empty else None,
        min_notional=specs.get("min_notional", 0.0),
        min_qty=specs.get("min_qty", 0.0),
        qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
    )

    result = run(
        strategy_cls(**cfg.params),
        data,
        entry_tf=cfg.entry_tf,
        costs=costs,
        initial_equity=cfg.initial_equity,
    )
    return rolling_validate(
        result.to_df(),
        window_days=window_days,
        step_days=step_days,
        min_trades=3,
        initial_equity=cfg.initial_equity,
    )


if __name__ == "__main__":
    main()

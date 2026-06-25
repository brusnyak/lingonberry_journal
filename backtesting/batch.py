"""
Batch backtesting runner.

Run a strategy against every (pair, entry_tf, param_combo) in one call.
Results are returned as a sorted DataFrame — drop-in for notebooks or scripts.

Usage:
    from backtesting.batch import run_batch, make_configs
    from backtesting.strategies.tr_accumulation import TrAccumulation

    configs = make_configs(
        pairs=["EURUSD", "GBPAUD", "GBPJPY"],
        entry_tfs=["5", "15"],
        support_tfs_map={"5": ["60", "240"], "15": ["60", "240"]},
        param_grid={"atr_mult": [1.5, 2.0], "tp_r": [1.0, 1.5]},
        start="2026-03-17", end="2026-05-23",
        initial_equity=10_000,
    )
    df = run_batch(TrAccumulation, configs)
    print(df[["pair", "entry_tf", "trades", "profit_factor", "win_rate", "max_dd_pct"]].to_string())
"""

from __future__ import annotations

import itertools
import traceback
from dataclasses import dataclass, field
from typing import Optional, Type

import pandas as pd

from backtesting.engine.base import Strategy
from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run


@dataclass
class RunConfig:
    """One (pair, entry_tf, params, date-range) combination."""
    pair: str
    entry_tf: str
    support_tfs: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    start: Optional[str] = None
    end: Optional[str] = None
    days: Optional[int] = None
    initial_equity: float = 10_000.0


def _run_one(strategy_cls: Type[Strategy], cfg: RunConfig) -> dict:
    try:
        tfs = list(dict.fromkeys([cfg.entry_tf] + cfg.support_tfs))  # dedup, preserve order
        data: dict[str, pd.DataFrame] = {}
        for tf in tfs:
            df = load_data(cfg.pair, tf=tf, start=cfg.start, end=cfg.end, days=cfg.days)
            if df.empty:
                return _err(cfg, f"no data: pair={cfg.pair} tf={tf}")
            data[tf] = df

        result = run(
            strategy_cls(**cfg.params),
            data,
            entry_tf=cfg.entry_tf,
            costs=ForexCosts(),
            initial_equity=cfg.initial_equity,
        )
        return {
            "pair": cfg.pair,
            "entry_tf": cfg.entry_tf,
            "support_tfs": ",".join(cfg.support_tfs),
            **cfg.params,
            **result.report,
            "error": None,
        }
    except Exception:
        return _err(cfg, traceback.format_exc(limit=3))


def _err(cfg: RunConfig, msg: str) -> dict:
    return {"pair": cfg.pair, "entry_tf": cfg.entry_tf, **cfg.params, "error": msg}


def run_batch(
    strategy_cls: Type[Strategy],
    configs: list[RunConfig],
    sort_by: str = "profit_factor",
    min_trades: int = 10,
) -> pd.DataFrame:
    """
    Run all configs sequentially. Returns a DataFrame sorted by sort_by.
    Rows with fewer than min_trades are kept but appear at the bottom.
    """
    rows = []
    n = len(configs)
    for i, cfg in enumerate(configs, 1):
        print(f"  [{i}/{n}] {cfg.pair} {cfg.entry_tf}m  {cfg.params}", end="  ", flush=True)
        row = _run_one(strategy_cls, cfg)
        trades = row.get("trades", 0)
        pf = row.get("profit_factor", 0)
        err = row.get("error")
        if err:
            print(f"ERROR: {str(err)[:80]}")
        else:
            print(f"T={trades}  PF={pf:.2f}")
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Sort: errors last, then by sort_by descending, then min_trades filter to bottom
    has_edge = df["error"].isna() & (df.get("trades", 0) >= min_trades)
    df["_rank"] = 0
    df.loc[has_edge, "_rank"] = 1
    if sort_by in df.columns:
        df = df.sort_values(["_rank", sort_by], ascending=[False, False])
    df = df.drop(columns=["_rank"])
    return df.reset_index(drop=True)


def make_configs(
    pairs: list[str],
    entry_tfs: list[str],
    support_tfs_map: dict[str, list[str]],
    param_grid: dict[str, list],
    start: Optional[str] = None,
    end: Optional[str] = None,
    days: Optional[int] = None,
    initial_equity: float = 10_000.0,
) -> list[RunConfig]:
    """
    Generate all (pair × entry_tf × param_combo) RunConfig objects.

    support_tfs_map: maps entry_tf → list of additional TFs to load.
        e.g. {"5": ["60", "240"], "15": ["60", "240"]}
    param_grid: dict of param_name → list of values to try.
        e.g. {"tp_r": [1.0, 1.5, 2.0], "atr_mult": [1.5, 2.0]}
    """
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    configs = []
    for pair, entry_tf, combo in itertools.product(pairs, entry_tfs, combos):
        configs.append(RunConfig(
            pair=pair,
            entry_tf=entry_tf,
            support_tfs=support_tfs_map.get(entry_tf, []),
            params=dict(zip(keys, combo)),
            start=start,
            end=end,
            days=days,
            initial_equity=initial_equity,
        ))
    return configs

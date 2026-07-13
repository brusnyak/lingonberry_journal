"""Portfolio-level validation for promoted crypto execution buckets.

Per-trade R is not enough. This module turns a selected execution bucket into
an account-level path with concurrency, symbol, cooldown, and daily-loss
throttles.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioRiskConfig:
    risk_per_trade_pct: float = 0.0015
    max_open_trades: int = 3
    max_open_per_symbol: int = 1
    cooldown_after_loss_bars: int = 4
    daily_loss_limit_pct: float = 0.0075
    tf_minutes: int = 15


def filter_execution_bucket(
    trades: pd.DataFrame,
    *,
    entry_model: str,
    target_model: str,
    management_model: str,
) -> pd.DataFrame:
    """Return one concrete execution bucket from the scored execution table."""
    required = {"entry_model", "target_model", "management_model"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"Missing execution columns: {sorted(missing)}")
    out = trades[
        (trades["entry_model"] == entry_model)
        & (trades["target_model"] == target_model)
        & (trades["management_model"] == management_model)
    ].copy()
    return _prepare_trades(out)


def simulate_portfolio(trades: pd.DataFrame, config: PortfolioRiskConfig | None = None) -> tuple[pd.DataFrame, dict]:
    """Apply portfolio risk throttles to a bucket and return accepted trades."""
    cfg = config or PortfolioRiskConfig()
    data = _prepare_trades(trades)
    if data.empty:
        return data, _empty_summary(cfg)

    accepted: list[dict] = []
    open_positions: list[dict] = []
    symbol_cooldown_until: dict[str, pd.Timestamp] = {}
    daily_realized: dict[pd.Timestamp.date, float] = {}
    equity_pct = 0.0
    peak_pct = 0.0
    max_dd_pct = 0.0

    for row in data.itertuples(index=False):
        entry_ts = row.entry_ts
        day = entry_ts.date()
        open_positions = [p for p in open_positions if p["exit_ts"] > entry_ts]
        day_pnl = daily_realized.get(day, 0.0)
        if day_pnl <= -cfg.daily_loss_limit_pct:
            continue
        if len(open_positions) >= cfg.max_open_trades:
            continue
        symbol_open = sum(1 for p in open_positions if p["symbol"] == row.symbol)
        if symbol_open >= cfg.max_open_per_symbol:
            continue
        cooldown_until = symbol_cooldown_until.get(row.symbol)
        if cooldown_until is not None and entry_ts < cooldown_until:
            continue

        pnl_pct = float(row.net_r) * cfg.risk_per_trade_pct
        exit_ts = row.exit_ts
        accepted_row = row._asdict()
        accepted_row["pnl_pct"] = pnl_pct
        accepted_row["risk_per_trade_pct"] = cfg.risk_per_trade_pct
        accepted_row["open_trades_before"] = len(open_positions)
        accepted.append(accepted_row)
        open_positions.append({"symbol": row.symbol, "exit_ts": exit_ts})
        daily_realized[day] = daily_realized.get(day, 0.0) + pnl_pct
        equity_pct += pnl_pct
        peak_pct = max(peak_pct, equity_pct)
        max_dd_pct = max(max_dd_pct, peak_pct - equity_pct)
        if pnl_pct < 0:
            symbol_cooldown_until[row.symbol] = exit_ts + pd.Timedelta(minutes=cfg.tf_minutes * cfg.cooldown_after_loss_bars)

    accepted_df = pd.DataFrame(accepted)
    return accepted_df, summarize_portfolio(accepted_df, cfg, candidates=len(data), max_dd_pct=max_dd_pct)


def summarize_portfolio(
    accepted: pd.DataFrame,
    cfg: PortfolioRiskConfig,
    *,
    candidates: int | None = None,
    max_dd_pct: float | None = None,
) -> dict:
    """Return account-level metrics for accepted trades."""
    if accepted.empty:
        return _empty_summary(cfg, candidates=candidates or 0)
    net = accepted["net_r"].astype(float)
    wins = net[net > 0]
    losses = net[net < 0]
    pnl_pct = accepted["pnl_pct"].astype(float) if "pnl_pct" in accepted.columns else net * cfg.risk_per_trade_pct
    equity = pnl_pct.cumsum()
    dd = (equity.cummax() - equity).max()
    max_dd = float(max_dd_pct) if max_dd_pct is not None else float(dd)
    daily = accepted.assign(day=accepted["entry_ts"].dt.date).groupby("day")["pnl_pct"].sum()
    daily_eq = daily.cumsum()
    daily_dd = float((daily_eq.cummax() - daily_eq).max()) if not daily.empty else 0.0
    return {
        "candidates": int(candidates if candidates is not None else len(accepted)),
        "accepted": int(len(accepted)),
        "acceptance_rate": float(len(accepted) / candidates) if candidates else 1.0,
        "symbols": int(accepted["symbol"].nunique()) if "symbol" in accepted else 0,
        "exchanges": int(accepted["exchange"].nunique()) if "exchange" in accepted else 0,
        "total_r": float(net.sum()),
        "avg_r": float(net.mean()),
        "median_r": float(net.median()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
        "gross_return_pct": float(pnl_pct.sum()),
        "max_dd_pct": max_dd,
        "daily_max_dd_pct": daily_dd,
        "return_to_dd": float(pnl_pct.sum() / max_dd) if max_dd > 0 else np.inf,
        "win_rate": float((net > 0).mean()),
        "stop_rate": float(accepted["hit_stop"].mean()) if "hit_stop" in accepted else np.nan,
        "expiry_rate": float((accepted["exit_reason"] == "expiry").mean()) if "exit_reason" in accepted else np.nan,
        "risk_per_trade_pct": cfg.risk_per_trade_pct,
        "max_open_trades": cfg.max_open_trades,
        "max_open_per_symbol": cfg.max_open_per_symbol,
        "daily_loss_limit_pct": cfg.daily_loss_limit_pct,
    }


def _prepare_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    required = {"entry_ts", "bars_to_exit", "symbol", "exchange", "net_r"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"Missing trade columns: {sorted(missing)}")
    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data["bars_to_exit"] = pd.to_numeric(data["bars_to_exit"], errors="coerce")
    data["net_r"] = pd.to_numeric(data["net_r"], errors="coerce")
    data = data.dropna(subset=["entry_ts", "bars_to_exit", "net_r"]).sort_values("entry_ts").reset_index(drop=True)
    if "exit_ts" not in data.columns:
        data["exit_ts"] = data["entry_ts"] + pd.to_timedelta(data["bars_to_exit"] * 15, unit="m")
    else:
        data["exit_ts"] = pd.to_datetime(data["exit_ts"], utc=True, errors="coerce")
    data = data.dropna(subset=["exit_ts"]).copy()
    data["_execution_priority"] = data.apply(_execution_priority, axis=1)
    data = data.sort_values(["entry_ts", "exchange", "symbol", "_execution_priority"]).reset_index(drop=True)
    identity = _execution_identity_cols(data)
    if identity:
        data = data.drop_duplicates(subset=identity, keep="first").reset_index(drop=True)
    return data.drop(columns=["_execution_priority"], errors="ignore").sort_values("entry_ts").reset_index(drop=True)


def _execution_identity_cols(data: pd.DataFrame) -> list[str]:
    cols = ["exchange", "symbol", "entry_ts", "entry", "stop", "target", "direction", "target_model", "management_model"]
    return [c for c in cols if c in data.columns]


def _execution_priority(row: pd.Series) -> tuple[int, int]:
    entry_model = str(row.get("entry_model", ""))
    confirmation = str(row.get("confirmation_model", ""))
    confirmed_rank = 0 if entry_model.startswith("structure_confirmed_") or confirmation not in {"", "none", "nan"} else 1
    entry_rank = {
        "structure_confirmed_fvg_ce_retest": 0,
        "fvg_ce_retest": 1,
        "structure_confirmed_fvg_edge_retest": 2,
        "fvg_edge_retest": 3,
        "structure_confirmed_next_open": 4,
        "next_open": 5,
    }.get(entry_model, 9)
    return confirmed_rank, entry_rank


def _empty_summary(cfg: PortfolioRiskConfig, *, candidates: int = 0) -> dict:
    return {
        "candidates": int(candidates),
        "accepted": 0,
        "acceptance_rate": 0.0,
        "symbols": 0,
        "exchanges": 0,
        "total_r": 0.0,
        "avg_r": 0.0,
        "median_r": 0.0,
        "profit_factor": 0.0,
        "gross_return_pct": 0.0,
        "max_dd_pct": 0.0,
        "daily_max_dd_pct": 0.0,
        "return_to_dd": 0.0,
        "win_rate": 0.0,
        "stop_rate": 0.0,
        "expiry_rate": 0.0,
        "risk_per_trade_pct": cfg.risk_per_trade_pct,
        "max_open_trades": cfg.max_open_trades,
        "max_open_per_symbol": cfg.max_open_per_symbol,
        "daily_loss_limit_pct": cfg.daily_loss_limit_pct,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Portfolio-validate a promoted crypto execution bucket.")
    parser.add_argument("--input", default="backtesting/results/event_atlas_target_layer/survivor_execution_paths.csv")
    parser.add_argument("--entry-model", default="structure_confirmed_fvg_top_retest")
    parser.add_argument("--target-model", default="fixed_1_5r")
    parser.add_argument("--management-model", default="partial_1r_be")
    parser.add_argument("--risk-pct", type=float, default=0.0015)
    parser.add_argument("--max-open", type=int, default=3)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.0075)
    parser.add_argument("--output-dir", default="backtesting/results/event_atlas_portfolio_layer")
    args = parser.parse_args()

    trades = pd.read_csv(args.input)
    bucket = filter_execution_bucket(
        trades,
        entry_model=args.entry_model,
        target_model=args.target_model,
        management_model=args.management_model,
    )
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=args.risk_pct,
        max_open_trades=args.max_open,
        max_open_per_symbol=args.max_open_per_symbol,
        daily_loss_limit_pct=args.daily_loss_limit_pct,
    )
    accepted, summary = simulate_portfolio(bucket, cfg)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted.to_csv(output_dir / "portfolio_trades.csv", index=False)
    pd.DataFrame([summary]).to_csv(output_dir / "portfolio_summary.csv", index=False)
    print(pd.DataFrame([summary]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

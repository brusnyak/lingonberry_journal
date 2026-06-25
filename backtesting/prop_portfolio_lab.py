#!/usr/bin/env python3
"""Prop-focused portfolio combiner for signal_lab events.

This stacks only rules that already pass basic per-rule filters, then simulates
the combined trade stream with daily lockout and max-trades-per-day limits.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.signal_lab import (  # noqa: E402
    ACCOUNT_KEYS,
    ACCOUNT_SIZE,
    DEFAULT_SYMBOLS,
    OUT,
    detect_events,
    filter_profiles,
    filtered_account_curves,
    r_column_for_exit_model,
)


@dataclass(frozen=True)
class Rule:
    filter_profile: str
    symbol: str
    session: str
    signal: str
    variant: str
    direction: str
    htf: str
    exit_model: str

    @property
    def key(self) -> tuple:
        return (
            self.symbol,
            self.session,
            self.signal,
            self.variant,
            self.direction,
            self.htf,
        )

    @property
    def setup_key(self) -> tuple:
        return (self.filter_profile, *self.key)


def load_or_detect_events(symbols: list[str], days: int, tag: str, refresh: bool) -> pd.DataFrame:
    path = OUT / f"signal_lab_{tag}_events.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, parse_dates=["ts"])
    frames = []
    for symbol in symbols:
        events = detect_events(symbol, days)
        print(f"{symbol}: {len(events)} signal variants")
        if not events.empty:
            frames.append(events)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(path, index=False)
    return out


def candidate_rules(
    events: pd.DataFrame,
    exit_models: list[str],
    min_trades: int,
    max_rule_dd: float,
    min_wr: float,
    max_rules_to_try: int,
) -> pd.DataFrame:
    acct = filtered_account_curves(events, exit_models=exit_models, daily_lockout_pct=0.0)
    if acct.empty:
        return acct
    acct = acct[
        (acct["n"] >= min_trades)
        & (acct["max_dd_pct"] <= max_rule_dd)
        & (acct["win_rate_pct"] >= min_wr)
    ].copy()
    if acct.empty:
        return acct
    acct["rule_score"] = (
        acct["return_pct"]
        - acct["max_dd_pct"] * 2.0
        + acct["win_rate_pct"] * 0.04
        + acct["direction_accuracy_15"] * 0.02
    )
    dedupe = ["symbol", "session", "signal", "variant", "direction", "htf", "exit_model"]
    acct = acct.sort_values(["rule_score", "return_pct"], ascending=[False, False])
    acct = acct.drop_duplicates(dedupe, keep="first")
    return acct.head(max_rules_to_try).reset_index(drop=True)


def trades_for_rule(events: pd.DataFrame, rule: Rule) -> pd.DataFrame:
    profiles = filter_profiles(events)
    if rule.filter_profile not in profiles:
        return pd.DataFrame()
    sub = profiles[rule.filter_profile]
    mask = np.ones(len(sub), dtype=bool)
    for col, val in zip(ACCOUNT_KEYS, rule.key):
        mask &= sub[col].astype(str).to_numpy() == str(val)
    out = sub.loc[mask].copy()
    if out.empty:
        return out
    r_col = r_column_for_exit_model(rule.exit_model)
    out["rule_id"] = "|".join((rule.filter_profile, *map(str, rule.key), rule.exit_model))
    out["exit_model"] = rule.exit_model
    out["trade_r"] = out[r_col].astype(float)
    return out


def simulate_portfolio(
    trades: pd.DataFrame,
    daily_lockout_pct: float,
    max_trades_per_day: int,
    risk_pct: float,
) -> dict:
    if trades.empty:
        return {}
    trades = trades.sort_values("ts").drop_duplicates(["ts", "symbol"], keep="first")
    equity = ACCOUNT_SIZE
    peak = equity
    max_dd = 0.0
    wins = 0
    taken = 0
    skipped_day_limit = 0
    skipped_lockout = 0
    day_start: dict[str, float] = {}
    day_pnl: dict[str, float] = {}
    day_count: dict[str, int] = {}
    max_trade_return = -999.0
    taken_rows = []

    for _, row in trades.iterrows():
        day = str(pd.Timestamp(row["ts"]).date())
        day_start.setdefault(day, equity)
        day_count.setdefault(day, 0)
        if day_count[day] >= max_trades_per_day:
            skipped_day_limit += 1
            continue
        base = day_start[day]
        day_loss = max(0.0, -day_pnl.get(day, 0.0) / base * 100.0) if base else 0.0
        if daily_lockout_pct > 0 and day_loss >= daily_lockout_pct:
            skipped_lockout += 1
            continue
        r = float(row["trade_r"])
        if not np.isfinite(r):
            continue
        pnl = ACCOUNT_SIZE * risk_pct * r
        equity += pnl
        day_pnl[day] = day_pnl.get(day, 0.0) + pnl
        day_count[day] += 1
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        max_trade_return = max(max_trade_return, pnl / ACCOUNT_SIZE * 100.0)
        wins += int(pnl > 0)
        taken += 1
        taken_rows.append(row)

    max_daily_loss = 0.0
    max_daily_gain = 0.0
    for day, pnl in day_pnl.items():
        base = day_start.get(day, ACCOUNT_SIZE)
        day_ret = pnl / base * 100.0 if base else 0.0
        max_daily_loss = max(max_daily_loss, -day_ret)
        max_daily_gain = max(max_daily_gain, day_ret)

    return {
        "rules": int(trades["rule_id"].nunique()),
        "signals": int(len(trades)),
        "n": int(taken),
        "skipped_day_limit": int(skipped_day_limit),
        "skipped_daily_lockout": int(skipped_lockout),
        "return_pct": float((equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100.0),
        "max_dd_pct": float(max_dd),
        "max_daily_loss_pct": float(max_daily_loss),
        "max_daily_gain_pct": float(max_daily_gain),
        "max_trade_return_pct": float(max_trade_return),
        "win_rate_pct": float(wins / max(taken, 1) * 100.0),
        "avg_r": float(pd.Series([r["trade_r"] for r in taken_rows]).mean()) if taken_rows else 0.0,
        "risk_pct": float(risk_pct * 100.0),
    }


def greedy_portfolio(
    events: pd.DataFrame,
    candidates: pd.DataFrame,
    daily_lockout_pct: float,
    max_trades_per_day: int,
    max_rules: int,
    risk_pct: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected: list[Rule] = []
    selected_setups: set[tuple] = set()
    selected_trades = pd.DataFrame()
    rows = []
    portfolio_score = -1e9

    for _ in range(max_rules):
        best = None
        best_trades = None
        best_metrics = None
        round_best_score = -1e9
        for _, c in candidates.iterrows():
            rule = Rule(
                c["filter_profile"],
                c["symbol"],
                c["session"],
                c["signal"],
                c["variant"],
                c["direction"],
                c["htf"],
                c["exit_model"],
            )
            if rule in selected or rule.setup_key in selected_setups:
                continue
            trades = trades_for_rule(events, rule)
            combo = pd.concat([selected_trades, trades], ignore_index=True) if not selected_trades.empty else trades
            metrics = simulate_portfolio(combo, daily_lockout_pct, max_trades_per_day, risk_pct)
            if not metrics:
                continue
            score = metrics["return_pct"] - metrics["max_dd_pct"] * 2.5 + metrics["win_rate_pct"] * 0.03
            if score > round_best_score:
                best = rule
                best_trades = combo
                best_metrics = metrics | {"score": float(score)}
                round_best_score = score
        if best is None or best_trades is None or best_metrics is None or round_best_score <= portfolio_score:
            break
        selected.append(best)
        selected_setups.add(best.setup_key)
        selected_trades = best_trades
        portfolio_score = best_metrics["score"]
        rows.append(best_metrics | {"added_rule": best.rule_id if hasattr(best, "rule_id") else "|".join((best.filter_profile, *map(str, best.key), best.exit_model))})

    return pd.DataFrame(rows), selected_trades


def main() -> None:
    parser = argparse.ArgumentParser(description="Prop-focused portfolio combiner.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--tag", default="")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--exit-models", default="tp1_sl1_24,tp2_sl1_24,tp3_sl1_24")
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--max-rule-dd", type=float, default=1.5)
    parser.add_argument("--min-wr", type=float, default=60.0)
    parser.add_argument("--max-rules-to-try", type=int, default=80)
    parser.add_argument("--max-rules", type=int, default=6)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--daily-lockout-pct", type=float, default=3.0)
    parser.add_argument("--risk-pct", type=float, default=0.5, help="Risk per trade as account percent.")
    args = parser.parse_args()

    tag = args.tag.strip() or f"{args.days}d_v2"
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exit_models = [m.strip() for m in args.exit_models.split(",") if m.strip()]

    events = load_or_detect_events(symbols, args.days, tag, args.refresh)
    candidates = candidate_rules(
        events,
        exit_models,
        args.min_trades,
        args.max_rule_dd,
        args.min_wr,
        args.max_rules_to_try,
    )
    candidates_path = OUT / f"prop_portfolio_{tag}_candidates.csv"
    candidates.to_csv(candidates_path, index=False)

    greedy, trades = greedy_portfolio(
        events,
        candidates,
        args.daily_lockout_pct,
        args.max_trades_per_day,
        args.max_rules,
        args.risk_pct / 100.0,
    )
    greedy_path = OUT / f"prop_portfolio_{tag}_greedy.csv"
    trades_path = OUT / f"prop_portfolio_{tag}_trades.csv"
    greedy.to_csv(greedy_path, index=False)
    trades.to_csv(trades_path, index=False)

    print(f"Saved {candidates_path} rows={len(candidates)}")
    print(f"Saved {greedy_path} rows={len(greedy)}")
    print(f"Saved {trades_path} rows={len(trades)}")
    if not candidates.empty:
        cols = [
            "filter_profile",
            "symbol",
            "session",
            "signal",
            "variant",
            "direction",
            "htf",
            "exit_model",
            "n",
            "return_pct",
            "max_dd_pct",
            "win_rate_pct",
            "avg_r",
            "direction_accuracy_15",
            "rule_score",
        ]
        print("\nTOP CANDIDATE RULES")
        print(candidates[cols].head(20).to_string(index=False))
    if not greedy.empty:
        print("\nGREEDY PORTFOLIO")
        print(greedy.to_string(index=False))


if __name__ == "__main__":
    main()

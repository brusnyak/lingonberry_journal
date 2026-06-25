#!/usr/bin/env python3
"""Walk-forward validation for costed prop portfolios."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.prop_portfolio_lab import (  # noqa: E402
    Rule,
    candidate_rules,
    greedy_portfolio,
    simulate_portfolio,
    trades_for_rule,
)
from backtesting.signal_lab import OUT  # noqa: E402


def parse_rule(rule_id: str) -> Rule:
    parts = rule_id.split("|")
    if len(parts) != 8:
        raise ValueError(f"Bad rule id: {rule_id}")
    return Rule(*parts)


def portfolio_trades(events: pd.DataFrame, rules: list[Rule]) -> pd.DataFrame:
    frames = []
    for rule in rules:
        trades = trades_for_rule(events, rule)
        if not trades.empty:
            frames.append(trades)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward prop portfolio validation.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--train-days", type=int, default=300)
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--exit-models", default="tp1_costed_24,tp2_costed_24,tp3_costed_24")
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--max-rule-dd", type=float, default=4.0)
    parser.add_argument("--min-wr", type=float, default=52.0)
    parser.add_argument("--max-rules-to-try", type=int, default=120)
    parser.add_argument("--max-rules", type=int, default=10)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--daily-lockout-pct", type=float, default=3.0)
    parser.add_argument("--risk-pct", type=float, default=1.0)
    args = parser.parse_args()

    events_path = OUT / f"signal_lab_{args.tag}_events.csv"
    events = pd.read_csv(events_path, parse_dates=["ts"]).sort_values("ts")
    start = events["ts"].min().normalize()
    end = events["ts"].max().normalize()
    exit_models = [m.strip() for m in args.exit_models.split(",") if m.strip()]

    rows = []
    all_test_trades = []
    split = 0
    train_start = start
    while True:
        train_end = train_start + pd.Timedelta(days=args.train_days)
        test_end = train_end + pd.Timedelta(days=args.test_days)
        if test_end > end:
            break
        train = events[(events["ts"] >= train_start) & (events["ts"] < train_end)].copy()
        test = events[(events["ts"] >= train_end) & (events["ts"] < test_end)].copy()
        if train.empty or test.empty:
            train_start += pd.Timedelta(days=args.step_days)
            continue

        candidates = candidate_rules(
            train,
            exit_models,
            args.min_trades,
            args.max_rule_dd,
            args.min_wr,
            args.max_rules_to_try,
        )
        greedy, _ = greedy_portfolio(
            train,
            candidates,
            args.daily_lockout_pct,
            args.max_trades_per_day,
            args.max_rules,
            args.risk_pct / 100.0,
        )
        rules = [parse_rule(rule_id) for rule_id in greedy["added_rule"].tolist()] if not greedy.empty else []
        trades = portfolio_trades(test, rules)
        metrics = simulate_portfolio(
            trades,
            args.daily_lockout_pct,
            args.max_trades_per_day,
            args.risk_pct / 100.0,
        )
        split += 1
        rows.append(
            {
                "split": split,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
                "train_events": len(train),
                "test_events": len(test),
                "selected_rules": len(rules),
                **metrics,
            }
        )
        if not trades.empty:
            trades = trades.copy()
            trades["split"] = split
            all_test_trades.append(trades)
        train_start += pd.Timedelta(days=args.step_days)

    summary = pd.DataFrame(rows)
    trades_out = pd.concat(all_test_trades, ignore_index=True) if all_test_trades else pd.DataFrame()
    summary_path = OUT / f"prop_walk_forward_{args.tag}_{args.train_days}x{args.test_days}_summary.csv"
    trades_path = OUT / f"prop_walk_forward_{args.tag}_{args.train_days}x{args.test_days}_trades.csv"
    summary.to_csv(summary_path, index=False)
    trades_out.to_csv(trades_path, index=False)

    print(f"Saved {summary_path} rows={len(summary)}")
    print(f"Saved {trades_path} rows={len(trades_out)}")
    if not summary.empty:
        cols = [
            "split",
            "test_start",
            "test_end",
            "selected_rules",
            "n",
            "return_pct",
            "max_dd_pct",
            "max_daily_loss_pct",
            "win_rate_pct",
            "avg_r",
        ]
        print(summary[cols].to_string(index=False))
        print("\nTOTAL")
        print(
            summary[
                [
                    "n",
                    "return_pct",
                    "max_dd_pct",
                    "max_daily_loss_pct",
                    "win_rate_pct",
                    "avg_r",
                ]
            ].agg(
                {
                    "n": "sum",
                    "return_pct": "sum",
                    "max_dd_pct": "max",
                    "max_daily_loss_pct": "max",
                    "win_rate_pct": "mean",
                    "avg_r": "mean",
                }
            ).to_string()
        )


if __name__ == "__main__":
    main()

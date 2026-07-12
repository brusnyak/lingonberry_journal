"""Build focused UI review packets for promoted crypto execution buckets."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, filter_execution_bucket, simulate_portfolio


DEFAULT_INPUT = Path("backtesting/results/event_atlas_target_layer/survivor_execution_paths.csv")
DEFAULT_OUTPUT = Path("backtesting/results/review_samples/crypto_portfolio_candidate_review_samples.csv")


def build_portfolio_candidate_review_packet(
    trades: pd.DataFrame,
    *,
    output_path: Path = DEFAULT_OUTPUT,
    per_symbol: int = 2,
) -> pd.DataFrame:
    """Export accepted and rejected examples for the current promoted bucket."""
    selected = filter_execution_bucket(
        trades,
        entry_model="structure_confirmed_fvg_top_retest",
        target_model="fixed_1_5r",
        management_model="partial_1r_be",
    )
    accepted, _summary = simulate_portfolio(
        selected,
        PortfolioRiskConfig(
            risk_per_trade_pct=0.0015,
            max_open_trades=3,
            max_open_per_symbol=1,
            daily_loss_limit_pct=0.0075,
        ),
    )
    raw_top = _raw_top_retest_bucket(trades)
    confirmed_keys = _trade_keys(selected)
    accepted_keys = _trade_keys(accepted)

    accepted_winners = accepted[accepted["net_r"] > 0].copy()
    accepted_winners["review_bucket"] = "accepted_winner"
    accepted_losers = accepted[accepted["net_r"] <= 0].copy()
    accepted_losers["review_bucket"] = "accepted_loser"

    stale = raw_top[raw_top["bars_to_entry"].astype(float) > 4].copy()
    stale["review_bucket"] = "rejected_stale_retest"

    timely = raw_top[raw_top["bars_to_entry"].astype(float) <= 4].copy()
    timely = timely[~_key_series(timely).isin(confirmed_keys)].copy()
    timely["review_bucket"] = "rejected_no_confirmation"

    portfolio_rejected = selected[~_key_series(selected).isin(accepted_keys)].copy()
    portfolio_rejected["review_bucket"] = "rejected_portfolio_throttle"

    packet = pd.concat(
        [
            _sample_by_symbol(accepted_winners, per_symbol),
            _sample_by_symbol(accepted_losers, per_symbol),
            _sample_by_symbol(stale, per_symbol),
            _sample_by_symbol(timely, per_symbol),
            _sample_by_symbol(portfolio_rejected, per_symbol),
        ],
        ignore_index=True,
    )
    packet = _to_review_schema(packet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output_path, index=False)

    for symbol, group in packet.groupby("symbol"):
        group.to_csv(output_path.with_name(f"crypto_portfolio_candidate_review_{symbol}.csv"), index=False)
    return packet


def _raw_top_retest_bucket(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades[
        (trades["entry_model"] == "fvg_top_retest")
        & (trades["target_model"] == "fixed_1_5r")
        & (trades["management_model"] == "partial_1r_be")
    ].copy()
    return _prepare(out)


def _prepare(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True, errors="coerce")
    out["net_r"] = pd.to_numeric(out["net_r"], errors="coerce")
    out["mae_r"] = pd.to_numeric(out["mae_r"], errors="coerce")
    return out.dropna(subset=["entry_ts", "net_r"]).sort_values("entry_ts").reset_index(drop=True)


def _sample_by_symbol(trades: pd.DataFrame, per_symbol: int) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    data = _prepare(trades)
    if "review_bucket" not in data.columns:
        data["review_bucket"] = "sample"
    rows = []
    for (_bucket, _symbol), group in data.groupby(["review_bucket", "symbol"], dropna=False):
        if "accepted_winner" in str(_bucket):
            group = group.sort_values("net_r", ascending=False)
        elif "accepted_loser" in str(_bucket):
            group = group.sort_values("net_r")
        elif "stale" in str(_bucket):
            group = group.sort_values("bars_to_entry", ascending=False)
        elif "no_confirmation" in str(_bucket):
            group = group.sort_values("mae_r")
        else:
            group = group.sort_values("entry_ts")
        rows.append(group.head(per_symbol))
    return pd.concat(rows, ignore_index=True) if rows else data.head(0)


def _to_review_schema(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    out = trades.copy()
    out["ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["predictor"] = "crypto_portfolio_candidate"
    out["session"] = out.get("session_utc", "late_us")
    out["direction"] = "short"
    out["entry_price"] = out["entry"].astype(float)
    out["sl"] = out["stop"].astype(float)
    out["tp1"] = out["target"].astype(float)
    out["risk_price"] = out["risk_price"].astype(float)
    out["outcome_1.5r"] = out["net_r"].astype(float)
    out["hit_1.5r"] = out["hit_target"].astype(bool)
    out["notes_hint"] = out.apply(_notes_hint, axis=1)
    cols = [
        "ts",
        "symbol",
        "exchange",
        "tf",
        "predictor",
        "session",
        "direction",
        "entry_price",
        "sl",
        "tp1",
        "risk_price",
        "outcome_1.5r",
        "hit_1.5r",
        "mfe_r",
        "mae_r",
        "exit_reason",
        "review_bucket",
        "entry_model",
        "target_model",
        "management_model",
        "bars_to_entry",
        "confirmation_model",
        "notes_hint",
    ]
    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
    order = {
        "accepted_winner": 0,
        "accepted_loser": 1,
        "rejected_stale_retest": 2,
        "rejected_no_confirmation": 3,
        "rejected_portfolio_throttle": 4,
    }
    out["_bucket_order"] = out["review_bucket"].map(order).fillna(99)
    out = out.sort_values(["symbol", "_bucket_order", "ts"])
    return out[cols].reset_index(drop=True)


def _notes_hint(row: pd.Series) -> str:
    bucket = str(row.get("review_bucket", ""))
    if bucket == "accepted_winner":
        return "Accepted winner: judge if direction/confirmation/retest/target were genuinely valid before outcome."
    if bucket == "accepted_loser":
        return "Accepted loser: identify whether loss was acceptable variance or a structural flaw."
    if bucket == "rejected_stale_retest":
        return "Rejected stale retest: check whether late retest should stay blocked."
    if bucket == "rejected_no_confirmation":
        return "Rejected no confirmation: check if structure filter correctly blocked the short."
    if bucket == "rejected_portfolio_throttle":
        return "Rejected by portfolio throttle: check if trade was redundant/clustered or worth overriding."
    return "Judge direction, retest quality, stop, target, and management."


def _trade_keys(trades: pd.DataFrame) -> set[str]:
    if trades.empty:
        return set()
    return set(_key_series(trades).dropna().astype(str))


def _key_series(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=str)
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True, errors="coerce").astype(str)
    return trades["exchange"].astype(str) + "|" + trades["symbol"].astype(str) + "|" + entry_ts


def main() -> int:
    parser = argparse.ArgumentParser(description="Build crypto portfolio-candidate review packet.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--per-symbol", type=int, default=2)
    args = parser.parse_args()

    trades = pd.read_csv(args.input)
    packet = build_portfolio_candidate_review_packet(
        trades,
        output_path=Path(args.output),
        per_symbol=args.per_symbol,
    )
    print(f"Saved {args.output} rows={len(packet)} symbols={packet['symbol'].nunique() if not packet.empty else 0}")
    if not packet.empty:
        print(packet["review_bucket"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

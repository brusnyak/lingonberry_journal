"""Validate direction filters against canonical crypto setup candidates."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.canonical_session_harness import SETUPS, SetupSpec, select_setup
from backtesting.crypto.foundation_validation import DEFAULT_INPUTS, _layer_metrics, _prepare_outcomes
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio


DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_direction_filter_validation")
TARGET_MODELS = ("fixed_1_5r", "fixed_2r")
MANAGEMENT_MODELS = ("hold_target_expiry", "be_after_half_target", "partial_1r_be_after_half_target")


DIRECTION_FILTERS = (
    "base",
    "confirmed_only",
    "local_ema_aligned",
    "middle_local_ema_aligned",
    "global_middle_ema_aligned",
    "all_ema_aligned",
    "regime_aligned",
    "full_trend",
    "not_counter_structure",
)


def run_direction_filter_validation(
    inputs: dict[str, Path] | None = None,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    setups: list[SetupSpec] | None = None,
    target_models: tuple[str, ...] = TARGET_MODELS,
    management_models: tuple[str, ...] = MANAGEMENT_MODELS,
    filters: tuple[str, ...] = DIRECTION_FILTERS,
    risk_config: PortfolioRiskConfig | None = None,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = inputs or DEFAULT_INPUTS
    selected_setups = setups or list(SETUPS)
    cfg = risk_config or PortfolioRiskConfig(
        risk_per_trade_pct=0.002,
        max_open_trades=6,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.005,
    )
    rows = []
    for window, path in paths.items():
        if not path.exists():
            continue
        trades = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        for setup in selected_setups:
            for target_model in target_models:
                for management_model in management_models:
                    spec = replace(setup, target_model=target_model, management_model=management_model)
                    base_selected = select_setup(trades, spec)
                    for filter_name in filters:
                        filtered = _apply_direction_filter(base_selected, filter_name)
                        accepted, portfolio = simulate_portfolio(filtered, cfg)
                        prepared = _prepare_outcomes(accepted)
                        rows.append(_summary_row(window, spec, filter_name, base_selected, filtered, prepared, portfolio))

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = _attach_base_deltas(summary)
        summary = summary.sort_values(
            ["verdict", "window", "direction_accuracy_delta", "avg_r_delta", "accepted"],
            ascending=[True, True, False, False, False],
        ).reset_index(drop=True)
    winners = _winner_table(summary)
    summary.to_csv(output_dir / "direction_filter_summary.csv", index=False)
    winners.to_csv(output_dir / "direction_filter_winners.csv", index=False)
    _write_report(summary, winners, output_dir / "direction_filter_validation_report.md")
    return {"summary": summary, "winners": winners}


def _apply_direction_filter(trades: pd.DataFrame, filter_name: str) -> pd.DataFrame:
    if trades.empty or filter_name == "base":
        return trades.copy()
    data = trades.copy()
    if filter_name == "confirmed_only":
        confirmed_entry = data["entry_model"].astype(str).str.startswith("structure_confirmed_")
        confirmed_model = ~data["confirmation_model"].astype(str).isin(["", "none", "nan"])
        return data[confirmed_entry | confirmed_model].copy().reset_index(drop=True)
    if filter_name == "local_ema_aligned":
        return data[_state_matches_direction(data, "local_ema_state")].copy().reset_index(drop=True)
    if filter_name == "middle_local_ema_aligned":
        return data[_state_matches_direction(data, "middle_ema_state") & _state_matches_direction(data, "local_ema_state")].copy().reset_index(drop=True)
    if filter_name == "global_middle_ema_aligned":
        return data[_state_matches_direction(data, "global_ema_state") & _state_matches_direction(data, "middle_ema_state")].copy().reset_index(drop=True)
    if filter_name == "all_ema_aligned":
        return data[
            _state_matches_direction(data, "global_ema_state")
            & _state_matches_direction(data, "middle_ema_state")
            & _state_matches_direction(data, "local_ema_state")
        ].copy().reset_index(drop=True)
    if filter_name == "regime_aligned":
        return data[_regime_matches_direction(data)].copy().reset_index(drop=True)
    if filter_name == "full_trend":
        return data[data["trend_alignment"].astype(str) == "full_trend"].copy().reset_index(drop=True)
    if filter_name == "not_counter_structure":
        return data[data["trend_alignment"].astype(str) != "counter_global_or_structure"].copy().reset_index(drop=True)
    raise ValueError(f"Unknown direction filter: {filter_name}")


def _state_matches_direction(data: pd.DataFrame, col: str) -> pd.Series:
    desired = np.where(data["direction"].astype(str).str.lower() == "long", "bullish", "bearish")
    return data[col].astype(str).to_numpy() == desired


def _regime_matches_direction(data: pd.DataFrame) -> pd.Series:
    direction = data["direction"].astype(str).str.lower()
    regime = data["ctx_240_regime"].astype(str).str.lower()
    return ((direction == "long") & (regime == "bull")) | ((direction == "short") & (regime == "bear"))


def _summary_row(
    window: str,
    spec: SetupSpec,
    filter_name: str,
    base_selected: pd.DataFrame,
    filtered: pd.DataFrame,
    accepted: pd.DataFrame,
    portfolio: dict,
) -> dict:
    base_count = len(base_selected)
    row = {
        "window": window,
        "setup_name": spec.name,
        "target_model": spec.target_model,
        "management_model": spec.management_model,
        "direction_filter": filter_name,
        "base_candidates": int(base_count),
        "filtered_candidates": int(len(filtered)),
        "candidate_keep_rate": float(len(filtered) / base_count) if base_count else 0.0,
        "accepted": int(len(accepted)),
        "symbols": int(accepted["symbol"].nunique()) if not accepted.empty and "symbol" in accepted else 0,
        "avg_r": float(portfolio.get("avg_r", 0.0)),
        "median_r": float(portfolio.get("median_r", 0.0)),
        "profit_factor": float(portfolio.get("profit_factor", 0.0)),
        "gross_return_pct": float(portfolio.get("gross_return_pct", 0.0)),
        "max_dd_pct": float(portfolio.get("max_dd_pct", 0.0)),
        "return_to_dd": float(portfolio.get("return_to_dd", 0.0)),
        "win_rate": float(portfolio.get("win_rate", 0.0)),
        "stop_rate": float(portfolio.get("stop_rate", 0.0)),
        "expiry_rate": float(portfolio.get("expiry_rate", 0.0)),
    }
    if accepted.empty:
        return {
            **row,
            "direction_accuracy": 0.0,
            "clean_path_rate": 0.0,
            "bad_direction_rate": 0.0,
            "bad_entry_rate": 0.0,
            "target_too_far_rate": 0.0,
        }
    metrics = _layer_metrics(accepted)
    return {
        **row,
        "direction_accuracy": metrics["direction_accuracy"],
        "clean_path_rate": metrics["clean_path_rate"],
        "bad_direction_rate": metrics["bad_direction_rate"],
        "bad_entry_rate": metrics["bad_entry_rate"],
        "target_too_far_rate": metrics["target_too_far_rate"],
    }


def _attach_base_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    key_cols = ["window", "setup_name", "target_model", "management_model"]
    base = out[out["direction_filter"] == "base"][
        key_cols + ["accepted", "avg_r", "direction_accuracy", "bad_entry_rate", "return_to_dd"]
    ].rename(columns={
        "accepted": "base_accepted",
        "avg_r": "base_avg_r",
        "direction_accuracy": "base_direction_accuracy",
        "bad_entry_rate": "base_bad_entry_rate",
        "return_to_dd": "base_return_to_dd",
    })
    out = out.merge(base, on=key_cols, how="left")
    out["accepted_keep_rate"] = np.where(out["base_accepted"] > 0, out["accepted"] / out["base_accepted"], 0.0)
    out["avg_r_delta"] = out["avg_r"] - out["base_avg_r"]
    out["direction_accuracy_delta"] = out["direction_accuracy"] - out["base_direction_accuracy"]
    out["bad_entry_rate_delta"] = out["bad_entry_rate"] - out["base_bad_entry_rate"]
    out["return_to_dd_delta"] = out["return_to_dd"] - out["base_return_to_dd"]
    out["verdict"] = out.apply(_verdict, axis=1)
    return out


def _verdict(row: pd.Series) -> str:
    if row["direction_filter"] == "base":
        return "base"
    if row["accepted"] < 30 or row["accepted_keep_rate"] < 0.35:
        return "reject_too_sparse"
    if row["direction_accuracy_delta"] >= 0.05 and row["avg_r_delta"] >= 0 and row["bad_entry_rate_delta"] <= 0.05:
        return "direction_improver"
    if row["avg_r_delta"] >= 0.15 and row["direction_accuracy_delta"] >= 0:
        return "return_improver"
    if row["direction_accuracy_delta"] <= -0.05 or row["avg_r_delta"] < -0.10:
        return "worse"
    return "neutral"


def _winner_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    winners = summary[summary["verdict"].isin(["direction_improver", "return_improver"])].copy()
    if winners.empty:
        return winners
    cols = [
        "window", "setup_name", "target_model", "management_model", "direction_filter",
        "accepted", "accepted_keep_rate", "avg_r", "avg_r_delta",
        "direction_accuracy", "direction_accuracy_delta", "bad_entry_rate",
        "bad_entry_rate_delta", "return_to_dd", "return_to_dd_delta", "verdict",
    ]
    return winners[cols].sort_values(["direction_accuracy_delta", "avg_r_delta"], ascending=False).reset_index(drop=True)


def _write_report(summary: pd.DataFrame, winners: pd.DataFrame, output_path: Path) -> None:
    lines = [
        "# Crypto Direction Filter Validation",
        "",
        "Date: 2026-07-13.",
        "",
        "## Purpose",
        "",
        "- Test add-on direction filters against canonical setup candidates.",
        "- Keep the setup/event logic fixed; only direction gating changes.",
        "- Reject filters that improve stats by deleting most trades.",
        "",
        "## Meaningful Filter Winners",
        "",
    ]
    lines.extend(_markdown_table(_format(winners.head(40))))
    lines.extend(["", "## Verdict Counts", ""])
    if summary.empty:
        lines.append("_empty_")
    else:
        counts = summary.groupby(["direction_filter", "verdict"], dropna=False).size().reset_index(name="rows")
        lines.extend(_markdown_table(counts.sort_values(["direction_filter", "verdict"])))
    lines.extend(["", "## Best Rows By Direction Accuracy Delta", ""])
    if summary.empty:
        lines.append("_empty_")
    else:
        cols = [
            "window", "setup_name", "target_model", "management_model", "direction_filter",
            "accepted", "accepted_keep_rate", "avg_r", "avg_r_delta",
            "direction_accuracy", "direction_accuracy_delta", "bad_entry_rate",
            "verdict",
        ]
        show = summary[summary["direction_filter"] != "base"].sort_values(
            ["direction_accuracy_delta", "avg_r_delta"], ascending=False
        )[cols].head(60)
        lines.extend(_markdown_table(_format(show)))
    lines.extend([
        "",
        "## Decision Rules",
        "",
        "- Promote only filters marked `direction_improver` or `return_improver`.",
        "- Ignore filters with `accepted < 30` or `accepted_keep_rate < 35%`.",
        "- If no add-on filter improves direction cleanly, the next work is better regime definition, not more entry filters.",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _format(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if col.endswith("_rate") or col.endswith("_delta") and "rate" in col or col in {"win_rate", "direction_accuracy", "direction_accuracy_delta", "accepted_keep_rate"}:
            out[col] = out[col].map(lambda x: f"{float(x) * 100:+.1f}%" if "delta" in col else f"{float(x) * 100:.1f}%" if pd.notna(x) and np.isfinite(float(x)) else "")
        elif col.endswith("_pct"):
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) and np.isfinite(float(x)) else "")
        elif col in {"avg_r", "median_r", "profit_factor", "return_to_dd", "avg_r_delta", "return_to_dd_delta"}:
            out[col] = out[col].map(lambda x: f"{float(x):+.3f}" if pd.notna(x) and np.isfinite(float(x)) else "inf")
    return out


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_empty_"]
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run crypto direction-filter validation.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    result = run_direction_filter_validation(output_dir=Path(args.output_dir))
    print(result["winners"].head(30).to_string(index=False))
    print(result["summary"].groupby(["direction_filter", "verdict"]).size().reset_index(name="rows").to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Foundation validation for canonical crypto setup research.

This module does not create new setups. It stress-tests the existing canonical
setup definitions across target and management choices, then reports which
foundation layer is most likely failing: direction, entry, stop, target,
management, or portfolio validation.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.canonical_session_harness import SETUPS, SetupSpec, select_setup
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio


DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_foundation_validation")
DEFAULT_INPUTS = {
    "15m_60d": Path("backtesting/results/crypto_fvg_execution_matrix_binance_15m/fvg_execution_trades.parquet"),
    "15m_30d": Path("backtesting/results/crypto_fvg_execution_matrix_binance_15m_30d/fvg_execution_trades.parquet"),
    "5m_30d": Path("backtesting/results/crypto_fvg_execution_matrix_binance_5m_30d/fvg_execution_trades.parquet"),
}
TARGET_MODELS = ("fixed_1_5r", "fixed_2r")
MANAGEMENT_MODELS = ("hold_target_expiry", "be_after_half_target", "partial_1r_be_after_half_target")


def run_foundation_validation(
    inputs: dict[str, Path] | None = None,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    setups: list[SetupSpec] | None = None,
    target_models: tuple[str, ...] = TARGET_MODELS,
    management_models: tuple[str, ...] = MANAGEMENT_MODELS,
    risk_config: PortfolioRiskConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Run canonical setup validation over available execution matrices."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = risk_config or PortfolioRiskConfig(
        risk_per_trade_pct=0.002,
        max_open_trades=6,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.005,
    )
    selected_setups = setups or list(SETUPS)
    paths = inputs or DEFAULT_INPUTS

    rows: list[dict] = []
    symbol_rows: list[dict] = []
    entry_rows: list[dict] = []
    accepted_frames: list[pd.DataFrame] = []

    for window, path in paths.items():
        if not path.exists():
            rows.append(_missing_input_row(window, path))
            continue
        trades = _load_trades(path)
        for setup in selected_setups:
            for target_model in target_models:
                for management_model in management_models:
                    spec = replace(setup, target_model=target_model, management_model=management_model)
                    selected = select_setup(trades, spec)
                    accepted, portfolio = simulate_portfolio(selected, cfg)
                    enriched = _prepare_outcomes(accepted)
                    rows.append(_summary_row(window, spec, selected, enriched, portfolio))
                    symbol_rows.extend(_symbol_rows(window, spec, enriched))
                    entry_rows.extend(_entry_rows(window, spec, enriched))
                    if not enriched.empty:
                        accepted_frames.append(enriched.assign(window=window, setup_name=spec.name))

    summary = pd.DataFrame(rows).sort_values(
        ["window", "foundation_grade", "return_to_dd", "avg_r"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)
    by_symbol = pd.DataFrame(symbol_rows).sort_values(
        ["window", "setup_name", "target_model", "management_model", "gross_return_pct"],
        ascending=[True, True, True, True, False],
    ).reset_index(drop=True) if symbol_rows else pd.DataFrame()
    by_entry = pd.DataFrame(entry_rows).sort_values(
        ["window", "setup_name", "target_model", "management_model", "avg_r"],
        ascending=[True, True, True, True, False],
    ).reset_index(drop=True) if entry_rows else pd.DataFrame()
    accepted_all = pd.concat(accepted_frames, ignore_index=True) if accepted_frames else pd.DataFrame()
    confidence = _confidence_table(summary)

    summary.to_csv(output_dir / "foundation_summary.csv", index=False)
    by_symbol.to_csv(output_dir / "foundation_by_symbol.csv", index=False)
    by_entry.to_csv(output_dir / "foundation_by_entry_model.csv", index=False)
    confidence.to_csv(output_dir / "foundation_confidence.csv", index=False)
    if not accepted_all.empty:
        accepted_all.to_csv(output_dir / "foundation_accepted_trades.csv", index=False)
    _write_report(summary, confidence, by_symbol, by_entry, output_dir / "foundation_validation_report.md")
    return {
        "summary": summary,
        "confidence": confidence,
        "by_symbol": by_symbol,
        "by_entry": by_entry,
        "accepted": accepted_all,
    }


def _load_trades(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def _prepare_outcomes(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    data = trades.copy()
    for col in ["net_r", "mfe_r", "mae_r", "bars_to_entry", "bars_to_exit", "pnl_pct"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["hit_1r", "hit_target", "hit_stop"]:
        if col in data.columns:
            data[col] = data[col].astype(bool)
    data["direction_correct"] = data["mfe_r"] >= 1.0
    data["clean_path"] = (data["mfe_r"] >= 1.0) & (data["mae_r"] > -0.5)
    data["bad_direction"] = data["mfe_r"] < 0.5
    data["bad_entry"] = data["mae_r"] <= -1.0
    data["stop_after_favorable"] = data["hit_stop"] & (data["mfe_r"] >= 1.0)
    data["target_too_far"] = (data["mfe_r"] >= 1.0) & (~data["hit_target"]) & (data["exit_reason"].astype(str) == "expiry")
    data["management_neutralized"] = (data["exit_reason"].astype(str) == "breakeven") & (data["mfe_r"] >= 1.0)
    data["expired_after_1r"] = data["hit_1r"] & (data["exit_reason"].astype(str) == "expiry")
    data["layer_failure"] = data.apply(_classify_failure, axis=1)
    return data


def _classify_failure(row: pd.Series) -> str:
    if float(row.get("net_r", 0.0)) > 0:
        return "winner"
    if bool(row.get("bad_direction", False)):
        return "direction"
    if bool(row.get("bad_entry", False)):
        return "entry"
    if bool(row.get("stop_after_favorable", False)):
        return "stop"
    if bool(row.get("target_too_far", False)):
        return "target"
    if bool(row.get("management_neutralized", False)):
        return "management"
    if str(row.get("exit_reason", "")) == "expiry":
        return "no_follow_through"
    return "other"


def _summary_row(
    window: str,
    spec: SetupSpec,
    selected: pd.DataFrame,
    accepted: pd.DataFrame,
    portfolio: dict,
) -> dict:
    base = {
        "window": window,
        "setup_name": spec.name,
        "target_model": spec.target_model,
        "management_model": spec.management_model,
        "candidates": int(len(selected)),
        "accepted": int(len(accepted)),
        "symbols": int(accepted["symbol"].nunique()) if not accepted.empty and "symbol" in accepted else 0,
        "acceptance_rate": float(len(accepted) / len(selected)) if len(selected) else 0.0,
        "avg_r": float(portfolio.get("avg_r", 0.0)),
        "median_r": float(portfolio.get("median_r", 0.0)),
        "profit_factor": float(portfolio.get("profit_factor", 0.0)),
        "gross_return_pct": float(portfolio.get("gross_return_pct", 0.0)),
        "max_dd_pct": float(portfolio.get("max_dd_pct", 0.0)),
        "daily_max_dd_pct": float(portfolio.get("daily_max_dd_pct", 0.0)),
        "return_to_dd": float(portfolio.get("return_to_dd", 0.0)),
        "win_rate": float(portfolio.get("win_rate", 0.0)),
        "stop_rate": float(portfolio.get("stop_rate", 0.0)),
        "expiry_rate": float(portfolio.get("expiry_rate", 0.0)),
    }
    if accepted.empty:
        return {
            **base,
            **_empty_layer_metrics(),
            "dominant_failure": "none",
            "foundation_grade": "reject",
            "foundation_reason": "no accepted trades",
        }
    metrics = _layer_metrics(accepted)
    return {
        **base,
        **metrics,
        "dominant_failure": _dominant_failure(accepted),
        "foundation_grade": _grade(base, metrics),
        "foundation_reason": _grade_reason(base, metrics),
    }


def _missing_input_row(window: str, path: Path) -> dict:
    return {
        "window": window,
        "setup_name": "missing_input",
        "target_model": "n/a",
        "management_model": "n/a",
        "candidates": 0,
        "accepted": 0,
        "symbols": 0,
        "foundation_grade": "missing",
        "foundation_reason": f"input not found: {path}",
    }


def _empty_layer_metrics() -> dict:
    return {
        "direction_accuracy": 0.0,
        "clean_path_rate": 0.0,
        "bad_direction_rate": 0.0,
        "bad_entry_rate": 0.0,
        "stop_after_favorable_rate": 0.0,
        "target_too_far_rate": 0.0,
        "management_neutralized_rate": 0.0,
        "expired_after_1r_rate": 0.0,
        "hit_1r_rate": 0.0,
        "target_rate": 0.0,
        "median_mfe_r": 0.0,
        "median_mae_r": 0.0,
        "median_bars_to_entry": 0.0,
        "median_bars_to_exit": 0.0,
    }


def _layer_metrics(data: pd.DataFrame) -> dict:
    return {
        "direction_accuracy": float(data["direction_correct"].mean()),
        "clean_path_rate": float(data["clean_path"].mean()),
        "bad_direction_rate": float(data["bad_direction"].mean()),
        "bad_entry_rate": float(data["bad_entry"].mean()),
        "stop_after_favorable_rate": float(data["stop_after_favorable"].mean()),
        "target_too_far_rate": float(data["target_too_far"].mean()),
        "management_neutralized_rate": float(data["management_neutralized"].mean()),
        "expired_after_1r_rate": float(data["expired_after_1r"].mean()),
        "hit_1r_rate": float(data["hit_1r"].mean()) if "hit_1r" in data else np.nan,
        "target_rate": float(data["hit_target"].mean()) if "hit_target" in data else np.nan,
        "median_mfe_r": float(data["mfe_r"].median()),
        "median_mae_r": float(data["mae_r"].median()),
        "median_bars_to_entry": float(data["bars_to_entry"].median()) if "bars_to_entry" in data else np.nan,
        "median_bars_to_exit": float(data["bars_to_exit"].median()) if "bars_to_exit" in data else np.nan,
    }


def _dominant_failure(data: pd.DataFrame) -> str:
    failures = data[data["layer_failure"] != "winner"]["layer_failure"]
    if failures.empty:
        return "none"
    return str(failures.value_counts().idxmax())


def _grade(base: dict, metrics: dict) -> str:
    accepted = int(base["accepted"])
    avg_r = float(base["avg_r"])
    pf = float(base["profit_factor"])
    dd = float(base["max_dd_pct"])
    direction = float(metrics["direction_accuracy"])
    bad_entry = float(metrics["bad_entry_rate"])
    clean = float(metrics["clean_path_rate"])
    if accepted < 30:
        return "reject"
    if avg_r >= 0.35 and pf >= 2.0 and dd <= 0.02 and direction >= 0.55 and bad_entry <= 0.30:
        return "promote_candidate"
    if avg_r > 0.10 and pf >= 1.25 and direction >= 0.45 and clean >= 0.20:
        return "research_candidate"
    return "reject"


def _grade_reason(base: dict, metrics: dict) -> str:
    reasons = []
    if int(base["accepted"]) < 30:
        reasons.append("sample<30")
    if float(base["avg_r"]) <= 0:
        reasons.append("avg_r<=0")
    if float(base["profit_factor"]) < 1.25:
        reasons.append("pf<1.25")
    if float(metrics["direction_accuracy"]) < 0.45:
        reasons.append("direction<45%")
    if float(metrics["bad_entry_rate"]) > 0.35:
        reasons.append("bad_entry>35%")
    if float(metrics["target_too_far_rate"]) > 0.30:
        reasons.append("target_too_far>30%")
    return ", ".join(reasons) if reasons else "passes foundation thresholds"


def _symbol_rows(window: str, spec: SetupSpec, data: pd.DataFrame) -> list[dict]:
    rows = []
    if data.empty or "symbol" not in data:
        return rows
    total_return = float(data["pnl_pct"].sum()) if "pnl_pct" in data else 0.0
    for symbol, group in data.groupby("symbol"):
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        gross_return = float(group["pnl_pct"].sum()) if "pnl_pct" in group else 0.0
        rows.append({
            "window": window,
            "setup_name": spec.name,
            "target_model": spec.target_model,
            "management_model": spec.management_model,
            "symbol": symbol,
            "trades": int(len(group)),
            "avg_r": float(net.mean()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "gross_return_pct": gross_return,
            "return_share": float(gross_return / total_return) if total_return else np.nan,
            "direction_accuracy": float(group["direction_correct"].mean()),
            "bad_direction_rate": float(group["bad_direction"].mean()),
            "bad_entry_rate": float(group["bad_entry"].mean()),
            "target_too_far_rate": float(group["target_too_far"].mean()),
            "dominant_failure": _dominant_failure(group),
        })
    return rows


def _entry_rows(window: str, spec: SetupSpec, data: pd.DataFrame) -> list[dict]:
    rows = []
    if data.empty or "entry_model" not in data:
        return rows
    for entry_model, group in data.groupby("entry_model"):
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            "window": window,
            "setup_name": spec.name,
            "target_model": spec.target_model,
            "management_model": spec.management_model,
            "entry_model": entry_model,
            "trades": int(len(group)),
            "avg_r": float(net.mean()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "win_rate": float((net > 0).mean()),
            "direction_accuracy": float(group["direction_correct"].mean()),
            "bad_entry_rate": float(group["bad_entry"].mean()),
            "target_too_far_rate": float(group["target_too_far"].mean()),
            "median_bars_to_entry": float(group["bars_to_entry"].median()) if "bars_to_entry" in group else np.nan,
            "dominant_failure": _dominant_failure(group),
        })
    return rows


def _confidence_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    valid = summary[~summary["setup_name"].isin(["missing_input"])].copy()
    rows = []
    for setup, group in valid.groupby("setup_name"):
        promoted = group[group["foundation_grade"] == "promote_candidate"]
        research = group[group["foundation_grade"].isin(["promote_candidate", "research_candidate"])]
        best = group.sort_values(["return_to_dd", "avg_r"], ascending=False).head(1)
        if best.empty:
            continue
        b = best.iloc[0]
        rows.append({
            "setup_name": setup,
            "tested_variants": int(len(group)),
            "promote_candidates": int(len(promoted)),
            "research_candidates": int(len(research)),
            "best_window": b["window"],
            "best_target_model": b["target_model"],
            "best_management_model": b["management_model"],
            "best_avg_r": float(b.get("avg_r", 0.0)),
            "best_return_to_dd": float(b.get("return_to_dd", 0.0)),
            "best_direction_accuracy": float(b.get("direction_accuracy", 0.0)),
            "dominant_failure": b.get("dominant_failure", "unknown"),
            "confidence": _setup_confidence(group),
        })
    return pd.DataFrame(rows).sort_values(["confidence", "best_return_to_dd"], ascending=[True, False]).reset_index(drop=True)


def _setup_confidence(group: pd.DataFrame) -> str:
    windows = set(group["window"].astype(str))
    promoted_windows = set(group[group["foundation_grade"] == "promote_candidate"]["window"].astype(str))
    research_windows = set(group[group["foundation_grade"].isin(["promote_candidate", "research_candidate"])]["window"].astype(str))
    if {"15m_30d", "15m_60d"}.issubset(promoted_windows):
        return "medium_high"
    if {"15m_30d", "15m_60d"}.issubset(research_windows):
        return "medium"
    if promoted_windows:
        return "low_medium"
    if research_windows and windows:
        return "low"
    return "reject"


def _write_report(summary: pd.DataFrame, confidence: pd.DataFrame, by_symbol: pd.DataFrame, by_entry: pd.DataFrame, output_path: Path) -> None:
    lines = [
        "# Crypto Foundation Validation",
        "",
        "Date: 2026-07-13.",
        "",
        "## Purpose",
        "",
        "- Validate foundation layers before adding new pattern-recognition logic.",
        "- Compare the same canonical setup filters across target and management choices.",
        "- Surface whether failures are direction, entry, stop, target, management, or no-follow-through.",
        "",
        "## Confidence By Setup",
        "",
    ]
    lines.extend(_markdown_table(_format(confidence)))
    lines.extend(["", "## Best Promote / Research Candidates", ""])
    candidates = summary[summary["foundation_grade"].isin(["promote_candidate", "research_candidate"])].copy()
    show_cols = [
        "window", "setup_name", "target_model", "management_model", "accepted", "avg_r",
        "profit_factor", "return_to_dd", "win_rate", "direction_accuracy",
        "bad_direction_rate", "bad_entry_rate", "target_too_far_rate",
        "dominant_failure", "foundation_grade",
    ]
    if candidates.empty:
        lines.append("_empty_")
    else:
        lines.extend(_markdown_table(_format(candidates[show_cols].sort_values(["foundation_grade", "return_to_dd"], ascending=[True, False]).head(40))))
    lines.extend(["", "## Rejected / Weak Foundation Rows", ""])
    rejected = summary[summary["foundation_grade"] == "reject"].copy()
    if rejected.empty:
        lines.append("_empty_")
    else:
        lines.extend(_markdown_table(_format(rejected[show_cols + ["foundation_reason"]].head(40))))
    lines.extend(["", "## Concentration Warning", ""])
    concentration = _concentration_warnings(by_symbol)
    lines.extend(_markdown_table(_format(concentration)))
    lines.extend(["", "## Entry Model Leaders", ""])
    if by_entry.empty:
        lines.append("_empty_")
    else:
        leaders = by_entry[by_entry["trades"] >= 5].sort_values(["avg_r", "profit_factor"], ascending=False).head(40)
        lines.extend(_markdown_table(_format(leaders)))
    lines.extend([
        "",
        "## Decision Rules",
        "",
        "- Do not add a new recognition layer if direction accuracy is below 55% on the setup.",
        "- Do not loosen frequency if `bad_entry_rate` rises above 30-35%.",
        "- Do not lower RR globally; target choice is setup/timeframe-specific.",
        "- Treat any setup with only one strong window as regime-dependent until holdout confirms it.",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _concentration_warnings(by_symbol: pd.DataFrame) -> pd.DataFrame:
    if by_symbol.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["window", "setup_name", "target_model", "management_model"]
    for keys, group in by_symbol.groupby(group_cols):
        net_total = float(group["gross_return_pct"].sum())
        positive = group[group["gross_return_pct"] > 0].copy()
        positive_total = float(positive["gross_return_pct"].sum()) if not positive.empty else 0.0
        if not np.isfinite(positive_total) or positive_total <= 0:
            continue
        top = positive.sort_values("gross_return_pct", ascending=False).iloc[0]
        share = float(top["gross_return_pct"] / positive_total)
        rows.append({
            **dict(zip(group_cols, keys)),
            "top_symbol": top["symbol"],
            "top_symbol_positive_return_share": share,
            "symbols": int(group["symbol"].nunique()),
            "net_return_pct": net_total,
            "positive_return_pct": positive_total,
            "warning": "concentrated" if share > 0.50 else "ok",
        })
    return pd.DataFrame(rows).sort_values("top_symbol_positive_return_share", ascending=False).reset_index(drop=True)


def _format(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if col.endswith("_rate") or col in {"win_rate", "direction_accuracy", "best_direction_accuracy", "clean_path_rate", "acceptance_rate", "top_symbol_positive_return_share", "return_share"}:
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.1f}%" if pd.notna(x) and np.isfinite(float(x)) else "")
        elif col.endswith("_pct"):
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) and np.isfinite(float(x)) else "")
        elif col in {"avg_r", "median_r", "profit_factor", "return_to_dd", "median_mfe_r", "median_mae_r", "best_avg_r", "best_return_to_dd", "best_direction_accuracy"}:
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
    parser = argparse.ArgumentParser(description="Run crypto foundation validation over canonical setup definitions.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--inputs", default="", help="Optional comma list like label=path,label=path.")
    args = parser.parse_args()

    inputs = DEFAULT_INPUTS
    if args.inputs:
        inputs = {}
        for part in args.inputs.split(","):
            label, value = part.split("=", 1)
            inputs[label.strip()] = Path(value.strip())
    result = run_foundation_validation(inputs, output_dir=Path(args.output_dir))
    print(result["confidence"].to_string(index=False))
    print(result["summary"].sort_values(["foundation_grade", "return_to_dd"], ascending=[True, False]).head(30).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

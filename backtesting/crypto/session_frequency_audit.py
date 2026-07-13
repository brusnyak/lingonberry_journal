"""Audit session-module frequency and ignored crypto entries.

This is intentionally diagnostic. It separates:

- real executable frequency;
- strategy-filter scarcity;
- portfolio-throttle scarcity;
- hindsight near-misses that look valid only after the outcome is known.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio


DEFAULT_INPUT = Path("backtesting/results/crypto_fvg_execution_matrix_binance_15m/fvg_execution_trades.parquet")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_session_frequency_audit")
DEFAULT_REVIEW_OUTPUT = Path("backtesting/results/review_samples/crypto_london_frequency_audit_review_samples.csv")

LONDON_CURRENT = {
    "session_utc": "london",
    "direction": "long",
    "ctx_240_regime": "bull",
    "trend_alignment": "middle_local_ema",
    "middle_ema_state": "bullish",
    "local_ema_state": "bullish",
    "entry_model": "structure_confirmed_next_open",
    "target_model": "fixed_2r",
    "management_model": "be_after_half_target",
    "confirmation_model": "latest_bull_regime",
}

LATE_US_CURRENT = {
    "session_utc": "late_us",
    "direction": "short",
    "ctx_240_regime": "neutral",
    "trend_alignment": "global_middle_ema",
    "global_ema_state": "bearish",
    "middle_ema_state": "bearish",
    "local_ema_state": "bearish",
    "entry_model": "fvg_ce_retest",
    "target_model": "fixed_2r",
    "management_model": "hold_target_expiry",
    "confirmation_model": "none",
}


def run_frequency_audit(
    trades: pd.DataFrame,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    review_output: Path = DEFAULT_REVIEW_OUTPUT,
) -> dict[str, pd.DataFrame]:
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=0.002,
        max_open_trades=6,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.005,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    frequency = _session_frequency(trades)
    modules = _module_summary(trades, cfg)
    variants = _london_variants(trades, cfg)
    funnel = _london_filter_funnel(trades, cfg)
    review = _london_review_packet(trades)

    frequency.to_csv(output_dir / "session_frequency_by_symbol.csv", index=False)
    modules.to_csv(output_dir / "module_frequency_summary.csv", index=False)
    variants.to_csv(output_dir / "london_variant_summary.csv", index=False)
    funnel.to_csv(output_dir / "london_filter_funnel.csv", index=False)
    review_output.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(review_output, index=False)
    _write_report(
        frequency,
        modules,
        variants,
        funnel,
        output_path=output_dir / "session_frequency_audit_report.md",
        review_output=review_output,
    )
    return {
        "frequency": frequency,
        "modules": modules,
        "variants": variants,
        "funnel": funnel,
        "review": review,
    }


def _session_frequency(trades: pd.DataFrame) -> pd.DataFrame:
    plan = trades[
        (trades["target_model"] == "fixed_2r")
        & (trades["management_model"] == "be_after_half_target")
    ].copy()
    rows = []
    for keys, group in plan.groupby(["symbol", "session_utc", "direction"], dropna=False):
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            "symbol": keys[0],
            "session_utc": keys[1],
            "direction": keys[2],
            "rows": int(len(group)),
            "avg_r": float(net.mean()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) else np.inf,
            "stop_rate": float(group["hit_stop"].mean()),
            "expiry_rate": float((group["exit_reason"] == "expiry").mean()),
        })
    return pd.DataFrame(rows).sort_values(["symbol", "session_utc", "direction"]).reset_index(drop=True)


def _module_summary(trades: pd.DataFrame, cfg: PortfolioRiskConfig) -> pd.DataFrame:
    rows = []
    for name, spec in [("london_current", LONDON_CURRENT), ("late_us_current", LATE_US_CURRENT)]:
        selected = _filter(trades, spec)
        accepted, summary = simulate_portfolio(selected, cfg)
        rows.append({
            "module": name,
            "candidates": int(len(selected)),
            "accepted": int(len(accepted)),
            "symbols": int(accepted["symbol"].nunique()) if not accepted.empty else 0,
            "avg_r": float(summary["avg_r"]),
            "profit_factor": float(summary["profit_factor"]),
            "gross_return_pct": float(summary["gross_return_pct"]),
            "max_dd_pct": float(summary["max_dd_pct"]),
            "stop_rate": float(summary["stop_rate"]),
            "expiry_rate": float(summary["expiry_rate"]),
        })
    return pd.DataFrame(rows)


def _london_variants(trades: pd.DataFrame, cfg: PortfolioRiskConfig) -> pd.DataFrame:
    common = {
        "session_utc": "london",
        "direction": "long",
        "entry_model": "structure_confirmed_next_open",
        "target_model": "fixed_2r",
        "management_model": "be_after_half_target",
    }
    variants = {
        "current": LONDON_CURRENT,
        "drop_ctx_keep_ema_confirm": {
            **common,
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "confirmation_model": "latest_bull_regime",
        },
        "ctx_bull_any_entry_confirm": {
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
            "confirmation_model": "latest_bull_regime",
        },
        "ctx_bull_all_middle_local_long": {
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
        },
        "all_london_long_fixed2_be": common,
    }
    rows = []
    for name, spec in variants.items():
        selected = _filter(trades, spec)
        accepted, summary = simulate_portfolio(selected, cfg)
        rows.append({
            "variant": name,
            "candidates": int(len(selected)),
            "accepted": int(len(accepted)),
            "symbols": int(accepted["symbol"].nunique()) if not accepted.empty else 0,
            "avg_r": float(summary["avg_r"]),
            "profit_factor": float(summary["profit_factor"]),
            "gross_return_pct": float(summary["gross_return_pct"]),
            "max_dd_pct": float(summary["max_dd_pct"]),
            "stop_rate": float(summary["stop_rate"]),
            "expiry_rate": float(summary["expiry_rate"]),
        })
    return pd.DataFrame(rows).sort_values("gross_return_pct", ascending=False).reset_index(drop=True)


def _london_filter_funnel(trades: pd.DataFrame, cfg: PortfolioRiskConfig) -> pd.DataFrame:
    stages = [
        ("all_london_long_fixed2_be", {
            "session_utc": "london",
            "direction": "long",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
        }),
        ("plus_ctx_bull", {
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
        }),
        ("plus_middle_local_bullish", {
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
        }),
        ("plus_structure_confirmed_next_open", {
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "entry_model": "structure_confirmed_next_open",
            "target_model": "fixed_2r",
            "management_model": "be_after_half_target",
        }),
        ("current_with_latest_bull_regime", LONDON_CURRENT),
    ]
    rows = []
    for stage, spec in stages:
        selected = _filter(trades, spec)
        accepted, summary = simulate_portfolio(selected, cfg)
        rows.append({
            "stage": stage,
            "candidates": int(len(selected)),
            "accepted": int(len(accepted)),
            "symbols": int(accepted["symbol"].nunique()) if not accepted.empty else 0,
            "accepted_avg_r": float(summary["avg_r"]),
            "accepted_pf": float(summary["profit_factor"]),
            "accepted_return_pct": float(summary["gross_return_pct"]),
            "accepted_dd_pct": float(summary["max_dd_pct"]),
            "accepted_stop_rate": float(summary["stop_rate"]),
            "accepted_expiry_rate": float(summary["expiry_rate"]),
        })
    return pd.DataFrame(rows)


def _london_review_packet(trades: pd.DataFrame, per_symbol: int = 3) -> pd.DataFrame:
    current = _filter(trades, LONDON_CURRENT).copy()
    wide = trades[
        (trades["session_utc"] == "london")
        & (trades["direction"] == "long")
        & (trades["target_model"] == "fixed_2r")
        & (trades["management_model"] == "be_after_half_target")
    ].copy()
    near = wide.loc[~wide.index.isin(current.index)].copy()
    samples = []
    for bucket, data, ascending in [
        ("current_london_winner", current[current["net_r"] > 0], False),
        ("current_london_loser", current[current["net_r"] <= 0], True),
        ("hindsight_near_miss_winner", near[near["net_r"] > 0], False),
        ("hindsight_near_miss_loser", near[near["net_r"] <= 0], True),
    ]:
        if data.empty:
            continue
        take = (
            data.sort_values(["symbol", "net_r"], ascending=[True, ascending])
            .groupby("symbol", group_keys=False)
            .head(per_symbol)
            .copy()
        )
        take["review_bucket"] = bucket
        samples.append(take)
    packet = pd.concat(samples, ignore_index=True) if samples else current.head(0)
    if packet.empty:
        return packet
    out = pd.DataFrame({
        "ts": pd.to_datetime(packet["entry_ts"], utc=True),
        "symbol": packet["symbol"],
        "exchange": packet["exchange"],
        "tf": packet["tf"],
        "predictor": "crypto_london_frequency_audit",
        "session": packet["session_utc"],
        "direction": packet["direction"],
        "entry_price": packet["entry"].astype(float),
        "sl": packet["stop"].astype(float),
        "tp1": packet["target"].astype(float),
        "risk_price": packet["risk_price"].astype(float),
        "outcome_2r": packet["net_r"].astype(float),
        "hit_2r": packet["hit_target"].astype(bool),
        "mfe_r": packet["mfe_r"].astype(float),
        "mae_r": packet["mae_r"].astype(float),
        "exit_reason": packet["exit_reason"],
        "review_bucket": packet["review_bucket"],
        "entry_model": packet["entry_model"],
        "target_model": packet["target_model"],
        "management_model": packet["management_model"],
        "bars_to_entry": packet["bars_to_entry"],
        "confirmation_model": packet["confirmation_model"],
        "notes_hint": packet.apply(_notes_hint, axis=1),
    })
    return out.sort_values(["symbol", "review_bucket", "ts"]).reset_index(drop=True)


def _notes_hint(row: pd.Series) -> str:
    bucket = str(row.get("review_bucket", ""))
    if bucket.startswith("hindsight_near_miss"):
        return "HINDSIGHT near-miss: judge visually only. Do not train from this as a winner unless a causal filter is identified."
    if bucket.endswith("loser"):
        return "Current-filter loser: inspect direction, consolidation, candle confirmation, and whether entry came after exhaustion."
    return "Current-filter winner: identify causal price action that should generalize."


def _filter(trades: pd.DataFrame, spec: dict[str, str]) -> pd.DataFrame:
    out = trades.copy()
    for col, value in spec.items():
        out = out[out[col].astype(str) == str(value)].copy()
    return out.reset_index(drop=True)


def _write_report(
    frequency: pd.DataFrame,
    modules: pd.DataFrame,
    variants: pd.DataFrame,
    funnel: pd.DataFrame,
    *,
    output_path: Path,
    review_output: Path,
) -> None:
    lines = [
        "# Crypto Session Frequency Audit",
        "",
        "Date: 2026-07-13.",
        "",
        "## Verdict",
        "",
        "- Frequency is not an executable-event problem. It is a strategy-filter and review-sampling problem.",
        "- The UI sample was intentionally small. It did not represent all London candidates.",
        "- Loosening all London-long filters is a bad strategy: it creates many more trades but destroys expectancy and drawdown.",
        "- The only frequency expansion worth testing next is additional causal entry types inside the same London context, not all ignored entries.",
        "",
        "## Module Summary",
        "",
    ]
    lines.extend(_markdown_table(_format_metrics(modules)))
    lines.extend(["", "## London Variants", ""])
    lines.extend(_markdown_table(_format_metrics(variants)))
    lines.extend(["", "## London Filter Funnel", ""])
    lines.extend(_markdown_table(_format_metrics(funnel)))
    lines.extend([
        "",
        "## Session/Direction Reality Check",
        "",
        "The raw London-long universe contains many executable rows per symbol, but most are not profitable as a module.",
        "",
    ])
    top = frequency.sort_values("avg_r", ascending=False).head(20).copy()
    lines.extend(_markdown_table(_format_metrics(top)))
    lines.extend([
        "",
        "## Review Packet",
        "",
        f"- UI review packet: `{review_output}`.",
        "- It includes current London winners/losers and hindsight near-miss winners/losers.",
        "- Treat near-miss winners as diagnostic only. Using them directly is hindsight leakage.",
        "",
        "## Research Implication",
        "",
        "- Session research supports separate modules: London trend-continuation, late-US flush/countertrend, optional Asia pullback/flush.",
        "- Consolidation should be tested as a precondition: narrow pre-session range, breakout/displacement, then retest/engulfing confirmation.",
        "- Candle patterns should be tested as entry confirmation, not standalone signals. First candidates: engulfing/reversal strength, wick rejection at FVG CE, inside-bar compression break.",
        "",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _format_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col.endswith("_pct") or col.endswith("_rate"):
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) else "")
        elif col in {"avg_r", "profit_factor", "accepted_avg_r", "accepted_pf"}:
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
    parser = argparse.ArgumentParser(description="Audit crypto session frequency and ignored entries.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT))
    args = parser.parse_args()

    path = Path(args.input)
    trades = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    result = run_frequency_audit(trades, output_dir=Path(args.output_dir), review_output=Path(args.review_output))
    print(f"frequency_rows={len(result['frequency'])}")
    print(f"review_rows={len(result['review'])}")
    print(result["modules"].to_string(index=False))
    print(result["variants"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

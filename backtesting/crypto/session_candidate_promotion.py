"""Promote one session/trend execution candidate into portfolio forensics."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio
from backtesting.crypto.trade_forensics import ForensicsConfig, _forensic_row, build_forensic_review_packet


def promote_candidate(
    trades: pd.DataFrame,
    *,
    filters: dict[str, str],
    output_dir: Path,
    risk_pct: float = 0.002,
    max_open: int = 6,
    max_open_per_symbol: int = 1,
    daily_loss_limit_pct: float = 0.005,
    review_output: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    selected = _filter(trades, filters)
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=risk_pct,
        max_open_trades=max_open,
        max_open_per_symbol=max_open_per_symbol,
        daily_loss_limit_pct=daily_loss_limit_pct,
    )
    accepted, summary = simulate_portfolio(selected, cfg)
    forensic = pd.DataFrame([_forensic_row(row._asdict(), ForensicsConfig(risk_per_trade_pct=risk_pct)) for row in accepted.itertuples(index=False)])
    output_dir.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output_dir / "candidate_trades.csv", index=False)
    accepted.to_csv(output_dir / "portfolio_trades.csv", index=False)
    forensic.to_csv(output_dir / "trade_forensics.csv", index=False)
    pd.DataFrame([summary]).to_csv(output_dir / "portfolio_summary.csv", index=False)
    write_candidate_report(
        selected,
        accepted,
        forensic,
        summary,
        filters=filters,
        output_path=output_dir / "candidate_promotion_report.md",
    )
    if review_output is not None:
        build_forensic_review_packet(forensic, output_path=review_output)
    return accepted, forensic, summary


def write_candidate_report(
    selected: pd.DataFrame,
    accepted: pd.DataFrame,
    forensic: pd.DataFrame,
    summary: dict,
    *,
    filters: dict[str, str],
    output_path: Path,
) -> None:
    lines = [
        "# Crypto Session Candidate Promotion",
        "",
        "Date: 2026-07-13.",
        "",
        "## Filters",
        "",
    ]
    lines.extend([f"- `{k}` = `{v}`" for k, v in filters.items()])
    lines.extend([
        "",
        "## Portfolio",
        "",
        f"- Candidate trades: `{len(selected)}`.",
        f"- Accepted trades: `{len(accepted)}`.",
        f"- Symbols: `{accepted['symbol'].nunique() if not accepted.empty else 0}`.",
        f"- Return: `{summary.get('gross_return_pct', 0) * 100:+.2f}%`.",
        f"- Max DD: `{summary.get('max_dd_pct', 0) * 100:.2f}%`.",
        f"- Return/DD: `{summary.get('return_to_dd', 0):.2f}`.",
        f"- PF: `{summary.get('profit_factor', 0):.2f}`.",
        f"- Avg R: `{summary.get('avg_r', 0):+.3f}`.",
        f"- Win rate: `{summary.get('win_rate', 0) * 100:.1f}%`.",
        f"- Stop rate: `{summary.get('stop_rate', 0) * 100:.1f}%`.",
        f"- Expiry rate: `{summary.get('expiry_rate', 0) * 100:.1f}%`.",
        "",
    ])
    if not forensic.empty and "failure_layer" in forensic.columns:
        lines.extend(["## Forensics", ""])
        lines.extend(_markdown_table(_count_table(forensic, "failure_layer")))
        lines.extend(["", "Path split:", ""])
        lines.extend(_markdown_table(_count_table(forensic, "path_tag")))
        lines.extend(["", "By symbol:", ""])
        by_symbol = forensic.groupby("symbol").agg(
            trades=("symbol", "size"),
            avg_r=("net_r", "mean"),
            stop_rate=("hit_stop", "mean"),
            expiry_rate=("exit_reason", lambda s: (s == "expiry").mean()),
        ).reset_index().sort_values("avg_r")
        for col in ["avg_r", "stop_rate", "expiry_rate"]:
            by_symbol[col] = by_symbol[col].map(lambda x: f"{x:.3f}")
        lines.extend(_markdown_table(by_symbol))
    lines.extend([
        "",
        "## Judgment",
        "",
        "- This is still in-sample over the same `60d` window.",
        "- Promote only after holdout/window validation and manual UI review of forensic losers.",
        "",
    ])
    output_path.write_text("\n".join(lines))


def _filter(trades: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    out = trades.copy()
    for col, val in filters.items():
        if val == "" or val.lower() == "any":
            continue
        if col not in out.columns:
            raise ValueError(f"Missing filter column: {col}")
        out = out[out[col].astype(str) == val].copy()
    return out.reset_index(drop=True)


def _count_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df[col].value_counts(dropna=False).rename_axis(col).reset_index(name="count")
    out["share"] = out["count"] / max(len(df), 1)
    out["avg_r"] = out[col].map(df.groupby(col, dropna=False)["net_r"].mean())
    out["share"] = out["share"].map(lambda x: f"{x:.1%}")
    out["avg_r"] = out["avg_r"].map(lambda x: f"{x:+.3f}")
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
    parser = argparse.ArgumentParser(description="Promote one crypto session candidate.")
    parser.add_argument("--input", default="backtesting/results/crypto_fvg_execution_matrix_binance_15m/fvg_execution_trades.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--review-output", default="")
    parser.add_argument("--filter", action="append", default=[], help="Exact filter in col=value form.")
    parser.add_argument("--risk-pct", type=float, default=0.002)
    parser.add_argument("--max-open", type=int, default=6)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    args = parser.parse_args()

    path = Path(args.input)
    trades = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    filters = {}
    for item in args.filter:
        if "=" not in item:
            raise ValueError(f"Invalid filter: {item}")
        key, value = item.split("=", 1)
        filters[key] = value
    accepted, forensic, summary = promote_candidate(
        trades,
        filters=filters,
        output_dir=Path(args.output_dir),
        risk_pct=args.risk_pct,
        max_open=args.max_open,
        max_open_per_symbol=args.max_open_per_symbol,
        daily_loss_limit_pct=args.daily_loss_limit_pct,
        review_output=Path(args.review_output) if args.review_output else None,
    )
    print(pd.DataFrame([summary]).to_string(index=False))
    print(f"accepted={len(accepted)} forensic={len(forensic)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

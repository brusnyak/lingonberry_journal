"""Pattern audit for canonical crypto session trades."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path("backtesting/results/crypto_canonical_session_harness/binance_15m_60d_canonical_trades.csv")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_canonical_pattern_audit")
DEFAULT_REVIEW_OUTPUT = Path("backtesting/results/review_samples/crypto_canonical_pattern_review_samples.csv")


def run_pattern_audit(
    trades: pd.DataFrame,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    review_output: Path = DEFAULT_REVIEW_OUTPUT,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = _prepare(trades)
    setup = _group_stats(data, ["setup_name"])
    setup_hour = _group_stats(data, ["setup_name", "entry_hour_utc"])
    setup_symbol = _group_stats(data, ["setup_name", "symbol"])
    setup_entry = _group_stats(data, ["setup_name", "entry_model"])
    path = _path_quality(data)
    review = _review_packet(data)

    setup.to_csv(output_dir / "setup_pattern_stats.csv", index=False)
    setup_hour.to_csv(output_dir / "setup_hour_stats.csv", index=False)
    setup_symbol.to_csv(output_dir / "setup_symbol_stats.csv", index=False)
    setup_entry.to_csv(output_dir / "setup_entry_model_stats.csv", index=False)
    path.to_csv(output_dir / "setup_path_quality.csv", index=False)
    review_output.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(review_output, index=False)
    _write_report(
        setup,
        setup_hour,
        setup_symbol,
        setup_entry,
        path,
        output_path=output_dir / "canonical_pattern_audit_report.md",
        review_output=review_output,
    )
    return {
        "setup": setup,
        "setup_hour": setup_hour,
        "setup_symbol": setup_symbol,
        "setup_entry": setup_entry,
        "path": path,
        "review": review,
    }


def _prepare(trades: pd.DataFrame) -> pd.DataFrame:
    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    data["entry_hour_utc"] = data["entry_ts"].dt.hour
    data["net_r"] = pd.to_numeric(data["net_r"], errors="coerce")
    data["mfe_r"] = pd.to_numeric(data["mfe_r"], errors="coerce")
    data["mae_r"] = pd.to_numeric(data["mae_r"], errors="coerce")
    data["bars_to_exit"] = pd.to_numeric(data["bars_to_exit"], errors="coerce")
    data["direction_correct"] = data["mfe_r"] >= 1.0
    data["clean_path"] = (data["mfe_r"] >= 1.0) & (data["mae_r"] > -0.5)
    data["bad_direction"] = data["mfe_r"] < 0.5
    data["bad_entry"] = data["mae_r"] <= -1.0
    data["target_too_far"] = (data["mfe_r"] >= 1.0) & (~data["hit_target"].astype(bool)) & (data["exit_reason"].astype(str) == "expiry")
    return data.dropna(subset=["net_r"]).reset_index(drop=True)


def _group_stats(data: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in data.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        net = group["net_r"]
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            **dict(zip(group_cols, keys)),
            "trades": int(len(group)),
            "avg_r": float(net.mean()),
            "median_r": float(net.median()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "win_rate": float((net > 0).mean()),
            "direction_accuracy": float(group["direction_correct"].mean()),
            "clean_path_rate": float(group["clean_path"].mean()),
            "bad_direction_rate": float(group["bad_direction"].mean()),
            "bad_entry_rate": float(group["bad_entry"].mean()),
            "target_too_far_rate": float(group["target_too_far"].mean()),
            "target_rate": float(group["hit_target"].astype(bool).mean()),
            "stop_rate": float(group["hit_stop"].astype(bool).mean()),
            "expiry_rate": float((group["exit_reason"].astype(str) == "expiry").mean()),
            "median_mfe_r": float(group["mfe_r"].median()),
            "median_mae_r": float(group["mae_r"].median()),
            "median_bars_to_exit": float(group["bars_to_exit"].median()),
        })
    return pd.DataFrame(rows).sort_values(["avg_r", "profit_factor", "trades"], ascending=[False, False, False]).reset_index(drop=True)


def _path_quality(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for setup, group in data.groupby("setup_name"):
        winners = group[group["net_r"] > 0]
        losers = group[group["net_r"] <= 0]
        rows.append({
            "setup_name": setup,
            "winner_count": int(len(winners)),
            "loser_count": int(len(losers)),
            "winner_median_mfe_r": float(winners["mfe_r"].median()) if not winners.empty else np.nan,
            "winner_median_mae_r": float(winners["mae_r"].median()) if not winners.empty else np.nan,
            "loser_median_mfe_r": float(losers["mfe_r"].median()) if not losers.empty else np.nan,
            "loser_median_mae_r": float(losers["mae_r"].median()) if not losers.empty else np.nan,
            "loser_bad_direction_rate": float(losers["bad_direction"].mean()) if not losers.empty else np.nan,
            "loser_bad_entry_rate": float(losers["bad_entry"].mean()) if not losers.empty else np.nan,
            "loser_target_too_far_rate": float(losers["target_too_far"].mean()) if not losers.empty else np.nan,
        })
    return pd.DataFrame(rows).sort_values("winner_count", ascending=False).reset_index(drop=True)


def _review_packet(data: pd.DataFrame, per_setup: int = 8) -> pd.DataFrame:
    samples = []
    for setup, group in data.groupby("setup_name"):
        buckets = [
            ("best_winner", group[group["net_r"] > 0].sort_values("net_r", ascending=False)),
            ("clean_winner", group[group["clean_path"] & (group["net_r"] > 0)].sort_values("net_r", ascending=False)),
            ("worst_loser", group[group["net_r"] <= 0].sort_values("net_r")),
            ("bad_direction_loser", group[group["bad_direction"] & (group["net_r"] <= 0)].sort_values("net_r")),
            ("target_too_far", group[group["target_too_far"]].sort_values("net_r")),
        ]
        for bucket, rows in buckets:
            if rows.empty:
                continue
            take = rows.head(per_setup).copy()
            take["review_bucket"] = f"{setup}:{bucket}"
            samples.append(take)
    packet = pd.concat(samples, ignore_index=True) if samples else data.head(0).copy()
    if packet.empty:
        return packet
    out = pd.DataFrame({
        "ts": pd.to_datetime(packet["entry_ts"], utc=True),
        "symbol": packet["symbol"],
        "exchange": packet["exchange"],
        "tf": packet["tf"],
        "predictor": "crypto_canonical_pattern_audit",
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
    return out.sort_values(["review_bucket", "symbol", "ts"]).reset_index(drop=True)


def _notes_hint(row: pd.Series) -> str:
    flags = []
    if bool(row.get("clean_path", False)):
        flags.append("clean path")
    if bool(row.get("bad_direction", False)):
        flags.append("bad direction/no follow-through")
    if bool(row.get("bad_entry", False)):
        flags.append("bad entry/adverse excursion")
    if bool(row.get("target_too_far", False)):
        flags.append("target likely too far")
    return "Canonical pattern audit: " + (", ".join(flags) if flags else "normal path") + "."


def _write_report(
    setup: pd.DataFrame,
    setup_hour: pd.DataFrame,
    setup_symbol: pd.DataFrame,
    setup_entry: pd.DataFrame,
    path: pd.DataFrame,
    *,
    output_path: Path,
    review_output: Path,
) -> None:
    lines = [
        "# Crypto Canonical Pattern Audit",
        "",
        "Date: 2026-07-13.",
        "",
        "## Purpose",
        "",
        "- Measure direction accuracy, best/worst trading hours, entry trigger quality, and path failure modes.",
        "- Export review samples for best winners, clean winners, worst losers, bad-direction losers, and target-too-far cases.",
        "",
        "## Setup Stats",
        "",
    ]
    lines.extend(_markdown_table(_format(setup.head(20))))
    lines.extend(["", "## Best Setup/Hour Buckets", ""])
    lines.extend(_markdown_table(_format(setup_hour[setup_hour["trades"] >= 5].head(30))))
    lines.extend(["", "## Best Setup/Symbol Buckets", ""])
    lines.extend(_markdown_table(_format(setup_symbol[setup_symbol["trades"] >= 4].head(30))))
    lines.extend(["", "## Entry Model Quality", ""])
    lines.extend(_markdown_table(_format(setup_entry.head(30))))
    lines.extend(["", "## Path Quality", ""])
    lines.extend(_markdown_table(_format(path)))
    lines.extend([
        "",
        "## Review Packet",
        "",
        f"- UI review packet: `{review_output}`.",
        "- Review `bad_direction_loser` before changing stops.",
        "- Review `target_too_far` before reducing or increasing RR.",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _format(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col.endswith("_rate") or col == "direction_accuracy":
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.1f}%" if pd.notna(x) else "")
        elif col.endswith("_r") or col in {"avg_r", "median_r", "profit_factor"}:
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
    parser = argparse.ArgumentParser(description="Audit canonical crypto trade patterns.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT))
    args = parser.parse_args()

    trades = pd.read_csv(args.input)
    result = run_pattern_audit(trades, output_dir=Path(args.output_dir), review_output=Path(args.review_output))
    print(result["setup"].to_string(index=False))
    print(f"review_rows={len(result['review'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

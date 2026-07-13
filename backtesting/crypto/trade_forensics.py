"""Trade-level forensics for promoted crypto execution buckets.

Aggregate R is not enough. This module inspects the actual candle path around
accepted trades and tags what happened before and after entry so the next change
is aimed at the broken layer, not at the prettiest summary row.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, filter_execution_bucket, simulate_portfolio
from backtesting.engine.data import load_data


DEFAULT_INPUT = Path("backtesting/results/event_atlas_shock_layer/survivor_execution_paths.csv")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/event_atlas_shock_layer")
DEFAULT_REVIEW_OUTPUT = Path("backtesting/results/review_samples/crypto_shock_forensics_review_samples.csv")


@dataclass(frozen=True)
class ForensicsConfig:
    pre_bars: int = 16
    post_bars: int = 24
    atr_period: int = 14
    risk_per_trade_pct: float = 0.002
    max_open_trades: int = 6
    max_open_per_symbol: int = 1
    daily_loss_limit_pct: float = 0.005
    days: int = 400


def build_trade_forensics(
    trades: pd.DataFrame,
    *,
    entry_model: str,
    target_model: str,
    management_model: str,
    config: ForensicsConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cfg = config or ForensicsConfig()
    bucket = filter_execution_bucket(
        trades,
        entry_model=entry_model,
        target_model=target_model,
        management_model=management_model,
    )
    accepted, portfolio_summary = simulate_portfolio(
        bucket,
        PortfolioRiskConfig(
            risk_per_trade_pct=cfg.risk_per_trade_pct,
            max_open_trades=cfg.max_open_trades,
            max_open_per_symbol=cfg.max_open_per_symbol,
            daily_loss_limit_pct=cfg.daily_loss_limit_pct,
        ),
    )
    rows = []
    for row in accepted.itertuples(index=False):
        rows.append(_forensic_row(row._asdict(), cfg))
    forensic = pd.DataFrame(rows)
    management = compare_management_variants(
        trades,
        entry_model=entry_model,
        target_model=target_model,
    )
    return forensic, management, portfolio_summary


def compare_management_variants(
    trades: pd.DataFrame,
    *,
    entry_model: str,
    target_model: str,
) -> pd.DataFrame:
    data = trades[
        (trades["entry_model"] == entry_model)
        & (trades["target_model"] == target_model)
    ].copy()
    if data.empty:
        return pd.DataFrame()
    rows = []
    for model, group in data.groupby("management_model"):
        net = pd.to_numeric(group["net_r"], errors="coerce").dropna()
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            "management_model": model,
            "events": int(len(group)),
            "avg_r": float(net.mean()),
            "median_r": float(net.median()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "target_rate": float(group["hit_target"].mean()),
            "stop_rate": float(group["hit_stop"].mean()),
            "expiry_rate": float((group["exit_reason"] == "expiry").mean()),
            "hit_1r_rate": float(group["hit_1r"].mean()),
        })
    return pd.DataFrame(rows).sort_values(["avg_r", "profit_factor"], ascending=False)


def write_audit_report(
    forensic: pd.DataFrame,
    management: pd.DataFrame,
    portfolio_summary: dict,
    *,
    output_path: Path,
    entry_model: str,
    target_model: str,
    management_model: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Crypto Trade Forensics Audit",
        "",
        "Date: 2026-07-13.",
        "",
        "## Scope",
        "",
        f"- Entry: `{entry_model}`.",
        f"- Target: `{target_model}`.",
        f"- Management: `{management_model}`.",
        f"- Accepted trades inspected: `{len(forensic)}`.",
        f"- Risk proxy: `{portfolio_summary.get('risk_per_trade_pct', 0) * 100:.2f}%` per trade.",
        f"- Portfolio return: `{portfolio_summary.get('gross_return_pct', 0) * 100:+.2f}%`.",
        f"- Portfolio max DD: `{portfolio_summary.get('max_dd_pct', 0) * 100:.2f}%`.",
        f"- Portfolio PF: `{portfolio_summary.get('profit_factor', 0):.2f}`.",
        "",
    ]
    lines.extend(_layer_verdicts(forensic, management))
    output_path.write_text("\n".join(lines) + "\n")


def build_forensic_review_packet(
    forensic: pd.DataFrame,
    *,
    output_path: Path = DEFAULT_REVIEW_OUTPUT,
    per_bucket: int = 8,
) -> pd.DataFrame:
    """Export the most useful forensic edge cases in the review UI schema."""
    if forensic.empty:
        packet = pd.DataFrame()
    else:
        data = forensic[forensic["forensic_error"].fillna("") == ""].copy()
        samples = []
        bucket_specs = [
            ("clean_winner", data[(data["net_r"] > 0) & (data["path_tag"] == "clean_target_path")].sort_values("net_r", ascending=False)),
            ("no_followthrough_loser", data[data["path_tag"] == "no_followthrough"].sort_values("net_r")),
            ("gaveback_after_progress", data[data["path_tag"].isin(["gave_back_after_1r", "gave_back_after_half_target"])].sort_values("net_r")),
            ("expiry_after_progress", data[data["path_tag"] == "expiry_after_progress"].sort_values("net_r")),
            ("weak_symbol_loser", data[(data["net_r"] <= 0) & (data["symbol"].isin(["1000PEPEUSDT", "NEARUSDT", "AVAXUSDT", "WLDUSDT"]))].sort_values("net_r")),
        ]
        for bucket, group in bucket_specs:
            if group.empty:
                continue
            take = group.head(per_bucket).copy()
            take["review_bucket"] = bucket
            samples.append(take)
        packet = _forensics_to_review_schema(pd.concat(samples, ignore_index=True) if samples else data.head(0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output_path, index=False)
    if not packet.empty:
        for (exchange, symbol), group in packet.groupby(["exchange", "symbol"], dropna=False):
            safe_exchange = str(exchange).lower()
            safe_symbol = str(symbol).upper()
            group.to_csv(output_path.with_name(f"{output_path.stem}_{safe_exchange}_{safe_symbol}.csv"), index=False)
    return packet


def _forensic_row(row: dict, cfg: ForensicsConfig) -> dict:
    symbol = str(row["symbol"])
    exchange = str(row["exchange"])
    tf = str(row.get("tf", "15"))
    entry_ts = pd.Timestamp(row["entry_ts"])
    if entry_ts.tzinfo is None:
        entry_ts = entry_ts.tz_localize("UTC")
    else:
        entry_ts = entry_ts.tz_convert("UTC")

    try:
        data = load_data(symbol, tf=tf, days=cfg.days, asset_type="crypto", exchange=exchange, crypto_source="merged")
        data = data.sort_values("ts").reset_index(drop=True)
        data["ts"] = pd.to_datetime(data["ts"], utc=True)
    except Exception as exc:
        return {**_base_row(row), "forensic_error": str(exc)}

    idxs = data.index[data["ts"] == entry_ts].tolist()
    if not idxs:
        prior = data[data["ts"] <= entry_ts]
        if prior.empty:
            return {**_base_row(row), "forensic_error": "entry_ts_not_found"}
        entry_i = int(prior.index[-1])
    else:
        entry_i = int(idxs[0])

    atr = _atr(data, cfg.atr_period)
    entry = float(row["entry"])
    stop = float(row["stop"])
    target = float(row["target"])
    risk = float(row["risk_price"])
    if risk <= 0:
        return {**_base_row(row), "forensic_error": "invalid_risk"}

    pre = data.iloc[max(0, entry_i - cfg.pre_bars):entry_i]
    post = data.iloc[entry_i:min(len(data), entry_i + cfg.post_bars)]
    atr_now = float(atr.iat[entry_i]) if entry_i < len(atr) and np.isfinite(atr.iat[entry_i]) else np.nan
    pre_move_r = ((float(pre["close"].iloc[-1]) - float(pre["close"].iloc[0])) / risk) if len(pre) >= 2 else np.nan
    pre_range_atr = ((float(pre["high"].max()) - float(pre["low"].min())) / atr_now) if len(pre) and np.isfinite(atr_now) and atr_now > 0 else np.nan
    pre_lower_lows = int((pre["low"].diff() < 0).sum()) if len(pre) else 0
    pre_lower_highs = int((pre["high"].diff() < 0).sum()) if len(pre) else 0

    direction = str(row.get("direction", "short")).lower()
    path = _path_milestones(post, direction=direction, entry=entry, stop=stop, target=target, risk=risk)
    base = _base_row(row)
    out = {
        **base,
        "forensic_error": "",
        "pre_move_r": pre_move_r,
        "pre_range_atr": pre_range_atr,
        "pre_lower_low_count": pre_lower_lows,
        "pre_lower_high_count": pre_lower_highs,
        "pre_structure_tape": _pre_structure_tape(direction, pre_move_r, pre_lower_lows, pre_lower_highs),
        **path,
    }
    out["failure_layer"] = _failure_layer(out)
    out["path_tag"] = _path_tag(out)
    return out


def _forensics_to_review_schema(forensic: pd.DataFrame) -> pd.DataFrame:
    if forensic.empty:
        return pd.DataFrame()
    out = forensic.copy()
    out["ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["predictor"] = "crypto_shock_forensics"
    out["session"] = out["session_utc"] if "session_utc" in out.columns else "late_us"
    out["direction"] = out["direction"].fillna("short") if "direction" in out.columns else "short"
    out["entry_price"] = out["entry"].astype(float)
    out["sl"] = out["stop"].astype(float)
    out["tp1"] = out["target"].astype(float)
    out["outcome_1.5r"] = out["net_r"].astype(float)
    out["hit_1.5r"] = out["hit_target"].astype(bool)
    out["notes_hint"] = out.apply(_forensic_notes_hint, axis=1)
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
        "shock_state",
        "failure_layer",
        "path_tag",
        "pre_structure_tape",
        "notes_hint",
    ]
    for col in ["entry_model", "target_model", "management_model"]:
        if col not in out.columns:
            out[col] = ""
    order = {
        "no_followthrough_loser": 0,
        "gaveback_after_progress": 1,
        "expiry_after_progress": 2,
        "weak_symbol_loser": 3,
        "clean_winner": 4,
    }
    out["_bucket_order"] = out["review_bucket"].map(order).fillna(99)
    return out.sort_values(["exchange", "symbol", "_bucket_order", "ts"])[cols].reset_index(drop=True)


def _forensic_notes_hint(row: pd.Series) -> str:
    bucket = str(row.get("review_bucket", ""))
    if bucket == "no_followthrough_loser":
        return "Forensic loser: did the short have enough direction/entry confirmation, or was this a bad short into no follow-through?"
    if bucket == "gaveback_after_progress":
        return "Forensic giveback: price progressed, then failed. Judge target distance and whether management should exit earlier."
    if bucket == "expiry_after_progress":
        return "Forensic expiry after progress: judge whether target is too far or time exit should be active."
    if bucket == "weak_symbol_loser":
        return "Weak-symbol loser: judge whether symbol should be filtered or setup quality was still valid."
    if bucket == "clean_winner":
        return "Clean winner: identify what was present here that losers lacked."
    return "Judge direction, entry confirmation, shock state, target, and management."


def _path_milestones(post: pd.DataFrame, *, direction: str, entry: float, stop: float, target: float, risk: float) -> dict:
    is_long = direction == "long"
    one_r = entry + risk if is_long else entry - risk
    half_target = entry + 0.5 * (target - entry)
    mfe = 0.0
    mae = 0.0
    bars_to_half = np.nan
    bars_to_1r = np.nan
    bars_to_target = np.nan
    bars_to_stop = np.nan
    first_adverse_05r = np.nan
    close_r = np.nan
    for offset, candle in enumerate(post.itertuples(index=False), start=1):
        high = float(candle.high)
        low = float(candle.low)
        close = float(candle.close)
        if is_long:
            mfe = max(mfe, (high - entry) / risk)
            mae = min(mae, (low - entry) / risk)
            close_r = (close - entry) / risk
            adverse_r = (low - entry) / risk
            half_hit = high >= half_target
            one_r_hit = high >= one_r
            target_hit = high >= target
            stop_hit = low <= stop
        else:
            mfe = max(mfe, (entry - low) / risk)
            mae = min(mae, (entry - high) / risk)
            close_r = (entry - close) / risk
            adverse_r = (entry - high) / risk
            half_hit = low <= half_target
            one_r_hit = low <= one_r
            target_hit = low <= target
            stop_hit = high >= stop
        if np.isnan(first_adverse_05r) and adverse_r <= -0.5:
            first_adverse_05r = offset
        if np.isnan(bars_to_stop) and stop_hit:
            bars_to_stop = offset
        if np.isnan(bars_to_half) and half_hit:
            bars_to_half = offset
        if np.isnan(bars_to_1r) and one_r_hit:
            bars_to_1r = offset
        if np.isnan(bars_to_target) and target_hit:
            bars_to_target = offset
    return {
        "path_mfe_r": mfe,
        "path_mae_r": mae,
        "path_close_r": close_r,
        "bars_to_half_target": bars_to_half,
        "bars_to_1r": bars_to_1r,
        "bars_to_target": bars_to_target,
        "bars_to_stop": bars_to_stop,
        "bars_to_first_adverse_05r": first_adverse_05r,
        "reached_half_target": not np.isnan(bars_to_half),
        "reached_1r": not np.isnan(bars_to_1r),
        "reached_target": not np.isnan(bars_to_target),
        "touched_stop": not np.isnan(bars_to_stop),
    }


def _base_row(row: dict) -> dict:
    keep = [
        "exchange", "symbol", "tf", "entry_ts", "entry", "stop", "target", "risk_price",
        "session_utc", "direction",
        "entry_model", "target_model", "management_model",
        "net_r", "mfe_r", "mae_r", "hit_1r", "hit_target", "hit_stop", "exit_reason",
        "bars_to_entry", "bars_to_exit", "confirmation_model", "shock_state",
        "shock_reason", "ema_state", "pnl_pct", "open_trades_before",
    ]
    return {k: row.get(k) for k in keep}


def _pre_structure_tape(direction: str, pre_move_r: float, lower_lows: int, lower_highs: int) -> str:
    if direction == "long":
        if np.isfinite(pre_move_r) and pre_move_r >= 1.0:
            return "bullish_continuation"
        if np.isfinite(pre_move_r) and pre_move_r <= -1.0:
            return "bearish_reversal_pressure"
        if lower_lows <= 4 and lower_highs <= 4:
            return "mixed_or_chop"
        return "orderly_bullish"
    if np.isfinite(pre_move_r) and pre_move_r <= -1.0 and lower_lows >= 4:
        return "bearish_continuation"
    if np.isfinite(pre_move_r) and pre_move_r >= 1.0:
        return "bullish_reversal_pressure"
    if lower_lows >= 4 and lower_highs >= 4:
        return "orderly_bearish"
    return "mixed_or_chop"


def _failure_layer(row: dict) -> str:
    if row.get("net_r", 0) > 0:
        return "working"
    if not row.get("reached_half_target", False) and float(row.get("path_mfe_r", 0) or 0) < 0.5:
        return "direction_or_entry"
    if row.get("reached_1r", False) and not row.get("hit_target", False):
        return "management_or_target"
    if row.get("exit_reason") == "expiry":
        return "target_or_time_exit"
    if row.get("hit_stop", False):
        return "entry_or_stop"
    return "unknown"


def _path_tag(row: dict) -> str:
    if row.get("reached_target", False):
        return "clean_target_path"
    if row.get("reached_1r", False) and row.get("touched_stop", False):
        return "gave_back_after_1r"
    if row.get("reached_half_target", False) and row.get("touched_stop", False):
        return "gave_back_after_half_target"
    if not row.get("reached_half_target", False):
        return "no_followthrough"
    if row.get("exit_reason") == "expiry":
        return "expiry_after_progress"
    return "partial_followthrough"


def _layer_verdicts(forensic: pd.DataFrame, management: pd.DataFrame) -> list[str]:
    if forensic.empty:
        return ["## Verdict", "", "No accepted trades to inspect.", ""]
    clean = forensic[forensic["forensic_error"].fillna("") == ""].copy()
    lines = ["## Layer Verdicts", ""]
    lines.append(f"- Data: `{len(clean)}/{len(forensic)}` accepted trades had candle windows reconstructed.")
    lines.append(f"- Direction: winners `{(clean['net_r'] > 0).mean() * 100:.1f}%`; avg R `{clean['net_r'].mean():+.3f}`.")
    lines.append(f"- Entry: median bars to entry `{clean['bars_to_entry'].median():.1f}`; median MAE `{clean['mae_r'].median():+.3f}R`.")
    lines.append(f"- Stop: stop exits `{clean['hit_stop'].mean() * 100:.1f}%`; median path MAE `{clean['path_mae_r'].median():+.3f}R`.")
    lines.append(f"- Target: target exits `{clean['hit_target'].mean() * 100:.1f}%`; reached `1R` `{clean['reached_1r'].mean() * 100:.1f}%`; reached half-target `{clean['reached_half_target'].mean() * 100:.1f}%`.")
    lines.append(f"- Expiry: expiry exits `{(clean['exit_reason'] == 'expiry').mean() * 100:.1f}%`.")
    lines.append("")
    lines.append("Failure-layer split:")
    lines.append("")
    lines.extend(_markdown_table(_count_table(clean, "failure_layer")))
    lines.append("")
    lines.append("Path split:")
    lines.append("")
    lines.extend(_markdown_table(_count_table(clean, "path_tag")))
    lines.append("")
    lines.append("Pre-entry tape split:")
    lines.append("")
    lines.extend(_markdown_table(_count_table(clean, "pre_structure_tape")))
    if not management.empty:
        lines.append("")
        lines.append("Management variants for same entry/target:")
        lines.append("")
        keep = management[[
            "management_model", "events", "avg_r", "median_r", "profit_factor",
            "target_rate", "stop_rate", "expiry_rate", "hit_1r_rate",
        ]].copy()
        for col in ["avg_r", "median_r", "profit_factor", "target_rate", "stop_rate", "expiry_rate", "hit_1r_rate"]:
            keep[col] = keep[col].map(lambda x: f"{x:.3f}")
        lines.extend(_markdown_table(keep))
    lines.append("")
    lines.append("## Judgment")
    lines.append("")
    lines.append("- Proven: shock-aware half-target management reduces stop damage without needing EMA as a hard filter.")
    lines.append("- Assumed: the 11-symbol reviewed basket is representative enough for the next UI sample.")
    lines.append("- Unknown: whether the same bucket survives discovery/holdout and symbol promotion without curve-fit leakage.")
    lines.append("- Next test: UI review only the forensic edge cases, not random winners.")
    lines.append("")
    return lines


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
    parser = argparse.ArgumentParser(description="Build trade-level forensics for a promoted crypto execution bucket.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--entry-model", default="structure_confirmed_fvg_top_retest")
    parser.add_argument("--target-model", default="fixed_1_5r")
    parser.add_argument("--management-model", default="partial_1r_be_after_half_target")
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT))
    parser.add_argument("--review-per-bucket", type=int, default=8)
    parser.add_argument("--risk-pct", type=float, default=0.002)
    parser.add_argument("--max-open", type=int, default=6)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    args = parser.parse_args()

    trades = pd.read_csv(args.input)
    cfg = ForensicsConfig(
        risk_per_trade_pct=args.risk_pct,
        max_open_trades=args.max_open,
        max_open_per_symbol=args.max_open_per_symbol,
        daily_loss_limit_pct=args.daily_loss_limit_pct,
    )
    forensic, management, summary = build_trade_forensics(
        trades,
        entry_model=args.entry_model,
        target_model=args.target_model,
        management_model=args.management_model,
        config=cfg,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    forensic_path = output_dir / "trade_forensics.csv"
    management_path = output_dir / "management_variant_audit.csv"
    report_path = output_dir / "trade_forensics_audit.md"
    review_path = Path(args.review_output)
    forensic.to_csv(forensic_path, index=False)
    management.to_csv(management_path, index=False)
    write_audit_report(
        forensic,
        management,
        summary,
        output_path=report_path,
        entry_model=args.entry_model,
        target_model=args.target_model,
        management_model=args.management_model,
    )
    packet = build_forensic_review_packet(forensic, output_path=review_path, per_bucket=args.review_per_bucket)
    print(f"Saved {forensic_path} rows={len(forensic)}")
    print(f"Saved {management_path} rows={len(management)}")
    print(f"Saved {report_path}")
    print(f"Saved {review_path} rows={len(packet)}")
    if not forensic.empty:
        print(forensic["failure_layer"].value_counts().to_string())
        print(forensic["path_tag"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

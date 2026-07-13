"""Session setup lab for crypto FVG modules.

This lab tests whether London frequency can be expanded with causal setup
features instead of bluntly loosening the module filters.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio
from backtesting.engine.data import load_data
from backtesting.crypto.config import DEFAULT_DAYS, DEFAULT_SOURCE


DEFAULT_INPUT = Path("backtesting/results/crypto_fvg_execution_matrix_binance_15m/fvg_execution_trades.parquet")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_session_setup_lab")
DEFAULT_REVIEW_OUTPUT = Path("backtesting/results/review_samples/crypto_london_setup_lab_review_samples.csv")


def run_session_setup_lab(
    trades: pd.DataFrame,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    review_output: Path = DEFAULT_REVIEW_OUTPUT,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _london_base(trades)
    enriched = _dedupe_executions(_attach_entry_features(base))
    variants = _variant_summary(enriched)
    by_symbol = _by_symbol(enriched)
    review = _review_packet(enriched)

    enriched.to_csv(output_dir / "london_setup_enriched_trades.csv", index=False)
    variants.to_csv(output_dir / "london_setup_variant_summary.csv", index=False)
    by_symbol.to_csv(output_dir / "london_setup_by_symbol.csv", index=False)
    review_output.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(review_output, index=False)
    _write_report(
        variants,
        by_symbol,
        output_path=output_dir / "session_setup_lab_report.md",
        review_output=review_output,
    )
    return {"enriched": enriched, "variants": variants, "by_symbol": by_symbol, "review": review}


def _london_base(trades: pd.DataFrame) -> pd.DataFrame:
    return trades[
        (trades["session_utc"] == "london")
        & (trades["direction"] == "long")
        & (trades["target_model"] == "fixed_2r")
        & (trades["management_model"] == "be_after_half_target")
    ].copy().reset_index(drop=True)


def _attach_entry_features(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = []
    for (exchange, symbol, tf), group in trades.groupby(["exchange", "symbol", "tf"], dropna=False):
        data = load_data(
            str(symbol),
            tf=str(tf),
            days=DEFAULT_DAYS,
            asset_type="crypto",
            exchange=str(exchange),
            crypto_source=DEFAULT_SOURCE,
        ).sort_values("ts").reset_index(drop=True)
        data["ts"] = pd.to_datetime(data["ts"], utc=True)
        atr = _atr(data, 14)
        features = []
        for row in group.itertuples(index=False):
            entry_ts = pd.Timestamp(row.entry_ts)
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.tz_localize("UTC")
            else:
                entry_ts = entry_ts.tz_convert("UTC")
            prior = data.index[data["ts"] <= entry_ts]
            if len(prior) == 0:
                features.append(_empty_features())
                continue
            i = int(prior[-1])
            features.append(_entry_features(data, atr, i))
        enriched = group.reset_index(drop=True).join(pd.DataFrame(features))
        out.append(enriched)
    return pd.concat(out, ignore_index=True) if out else trades.head(0).copy()


def _entry_features(data: pd.DataFrame, atr: pd.Series, i: int) -> dict:
    row = data.iloc[i]
    atr_now = float(atr.iat[i]) if i < len(atr) and np.isfinite(atr.iat[i]) and atr.iat[i] > 0 else np.nan
    open_ = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    candle_range = high - low
    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    prev_close = float(data["close"].iat[i - 1]) if i > 0 else open_
    prev_open = float(data["open"].iat[i - 1]) if i > 0 else open_
    prev_high = float(data["high"].iat[i - 1]) if i > 0 else high
    prev_low = float(data["low"].iat[i - 1]) if i > 0 else low
    pre8 = data.iloc[max(0, i - 8):i]
    pre4 = data.iloc[max(0, i - 4):i]
    pre_range_atr_8 = _range_atr(pre8, atr_now)
    pre_range_atr_4 = _range_atr(pre4, atr_now)
    rolling_high_4 = float(pre4["high"].max()) if len(pre4) else np.nan
    rolling_low_4 = float(pre4["low"].min()) if len(pre4) else np.nan
    hour = pd.Timestamp(row["ts"]).hour

    body_frac = body / candle_range if candle_range > 0 else 0.0
    close_pos = (close - low) / candle_range if candle_range > 0 else 0.5
    lower_wick_frac = lower_wick / candle_range if candle_range > 0 else 0.0
    true_range_atr = candle_range / atr_now if np.isfinite(atr_now) and atr_now > 0 else np.nan
    impulse_atr = (close - prev_close) / atr_now if np.isfinite(atr_now) and atr_now > 0 else np.nan

    bullish_body = close > open_ and body_frac >= 0.55 and close_pos >= 0.70
    bullish_engulf = close > open_ and prev_close < prev_open and close >= prev_open and open_ <= prev_close
    wick_rejection = close > open_ and lower_wick_frac >= 0.35 and close_pos >= 0.60
    compression_8 = np.isfinite(pre_range_atr_8) and pre_range_atr_8 <= 2.25
    tight_compression_4 = np.isfinite(pre_range_atr_4) and pre_range_atr_4 <= 1.25
    breaks_micro_range = np.isfinite(rolling_high_4) and close > rolling_high_4
    reclaimed_prev_high = close > prev_high
    no_entry_exhaustion = not (np.isfinite(true_range_atr) and true_range_atr >= 2.25 and close_pos < 0.65)

    return {
        "entry_hour_utc": hour,
        "london_early": 7 <= hour < 10,
        "london_mid": 10 <= hour < 13,
        "entry_body_frac": body_frac,
        "entry_close_pos": close_pos,
        "entry_lower_wick_frac": lower_wick_frac,
        "entry_range_atr": true_range_atr,
        "entry_impulse_atr": impulse_atr,
        "pre_range_atr_8": pre_range_atr_8,
        "pre_range_atr_4": pre_range_atr_4,
        "bullish_body": bullish_body,
        "bullish_engulf": bullish_engulf,
        "wick_rejection": wick_rejection,
        "compression_8": compression_8,
        "tight_compression_4": tight_compression_4,
        "breaks_micro_range": breaks_micro_range,
        "reclaimed_prev_high": reclaimed_prev_high,
        "no_entry_exhaustion": no_entry_exhaustion,
        "candle_confirm": bullish_body or bullish_engulf or wick_rejection,
        "compression_break": compression_8 and breaks_micro_range,
        "rejection_or_break": wick_rejection or breaks_micro_range or bullish_engulf,
    }


def _empty_features() -> dict:
    return {
        "entry_hour_utc": np.nan,
        "london_early": False,
        "london_mid": False,
        "entry_body_frac": np.nan,
        "entry_close_pos": np.nan,
        "entry_lower_wick_frac": np.nan,
        "entry_range_atr": np.nan,
        "entry_impulse_atr": np.nan,
        "pre_range_atr_8": np.nan,
        "pre_range_atr_4": np.nan,
        "bullish_body": False,
        "bullish_engulf": False,
        "wick_rejection": False,
        "compression_8": False,
        "tight_compression_4": False,
        "breaks_micro_range": False,
        "reclaimed_prev_high": False,
        "no_entry_exhaustion": False,
        "candle_confirm": False,
        "compression_break": False,
        "rejection_or_break": False,
    }


def _range_atr(window: pd.DataFrame, atr_now: float) -> float:
    if window.empty or not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    return float((window["high"].max() - window["low"].min()) / atr_now)


def _variant_summary(trades: pd.DataFrame) -> pd.DataFrame:
    specs = {
        "all_london_long": {},
        "middle_local_bull": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
        },
        "middle_local_bull_any_entry_confirm": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "confirmation_model": "latest_bull_regime",
        },
        "middle_local_bull_candle_confirm": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "candle_confirm": True,
        },
        "middle_local_bull_compression_break": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "compression_break": True,
        },
        "middle_local_bull_rejection_or_break": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "rejection_or_break": True,
        },
        "middle_local_bull_no_exhaustion": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "no_entry_exhaustion": True,
        },
        "early_london_middle_local_bull": {
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
            "london_early": True,
        },
    }
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=0.002,
        max_open_trades=6,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.005,
    )
    rows = []
    for name, spec in specs.items():
        selected = _filter(trades, spec)
        accepted, summary = simulate_portfolio(selected, cfg)
        rows.append(_summary_row(name, selected, accepted, summary))
    return pd.DataFrame(rows).sort_values(["gross_return_pct", "avg_r"], ascending=False).reset_index(drop=True)


def _summary_row(name: str, selected: pd.DataFrame, accepted: pd.DataFrame, summary: dict) -> dict:
    span = _span_days(selected["entry_ts"]) if not selected.empty else 0.0
    symbols = int(selected["symbol"].nunique()) if not selected.empty else 0
    return {
        "variant": name,
        "candidates": int(len(selected)),
        "accepted": int(len(accepted)),
        "symbols": int(accepted["symbol"].nunique()) if not accepted.empty else 0,
        "candidate_per_symbol_day": float(len(selected) / (span * max(symbols, 1))) if span > 0 else np.nan,
        "accepted_per_symbol_day": float(len(accepted) / (span * max(symbols, 1))) if span > 0 else np.nan,
        "avg_r": float(summary.get("avg_r", 0.0)),
        "profit_factor": float(summary.get("profit_factor", 0.0)),
        "gross_return_pct": float(summary.get("gross_return_pct", 0.0)),
        "max_dd_pct": float(summary.get("max_dd_pct", 0.0)),
        "stop_rate": float(summary.get("stop_rate", 0.0)),
        "expiry_rate": float(summary.get("expiry_rate", 0.0)),
    }


def _by_symbol(trades: pd.DataFrame) -> pd.DataFrame:
    selected = _filter(trades, {
        "ctx_240_regime": "bull",
        "trend_alignment": "middle_local_ema",
        "middle_ema_state": "bullish",
        "local_ema_state": "bullish",
    })
    rows = []
    for symbol, group in selected.groupby("symbol"):
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            "symbol": symbol,
            "candidates": int(len(group)),
            "avg_r": float(net.mean()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "candle_confirm_share": float(group["candle_confirm"].mean()),
            "compression_break_share": float(group["compression_break"].mean()),
            "rejection_or_break_share": float(group["rejection_or_break"].mean()),
            "stop_rate": float(group["hit_stop"].mean()),
            "expiry_rate": float((group["exit_reason"] == "expiry").mean()),
        })
    return pd.DataFrame(rows).sort_values("avg_r", ascending=False).reset_index(drop=True)


def _review_packet(trades: pd.DataFrame, per_symbol: int = 4) -> pd.DataFrame:
    current = _dedupe_executions(_filter(trades, {
        "ctx_240_regime": "bull",
        "trend_alignment": "middle_local_ema",
        "middle_ema_state": "bullish",
        "local_ema_state": "bullish",
    })).copy()
    if current.empty:
        return current
    buckets = []
    for bucket, data, ascending in [
        ("setup_confirm_winner", current[(current["candle_confirm"] | current["compression_break"]) & (current["net_r"] > 0)], False),
        ("setup_confirm_loser", current[(current["candle_confirm"] | current["compression_break"]) & (current["net_r"] <= 0)], True),
        ("no_confirm_winner", current[~(current["candle_confirm"] | current["compression_break"]) & (current["net_r"] > 0)], False),
        ("no_confirm_loser", current[~(current["candle_confirm"] | current["compression_break"]) & (current["net_r"] <= 0)], True),
    ]:
        if data.empty:
            continue
        take = data.sort_values(["symbol", "net_r"], ascending=[True, ascending]).groupby("symbol", group_keys=False).head(per_symbol).copy()
        take["review_bucket"] = bucket
        buckets.append(take)
    packet = pd.concat(buckets, ignore_index=True) if buckets else current.head(0).copy()
    if packet.empty:
        return packet
    return pd.DataFrame({
        "ts": pd.to_datetime(packet["entry_ts"], utc=True),
        "symbol": packet["symbol"],
        "exchange": packet["exchange"],
        "tf": packet["tf"],
        "predictor": "crypto_london_setup_lab",
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
    }).sort_values(["symbol", "review_bucket", "ts"]).reset_index(drop=True)


def _notes_hint(row: pd.Series) -> str:
    parts = []
    if bool(row.get("candle_confirm", False)):
        parts.append("candle-confirm")
    if bool(row.get("compression_break", False)):
        parts.append("compression-break")
    if bool(row.get("rejection_or_break", False)):
        parts.append("rejection/break")
    if not parts:
        parts.append("no candle/setup confirmation")
    return "Setup lab: " + ", ".join(parts) + ". Judge if this is visually causal or just post-hoc noise."


def _filter(trades: pd.DataFrame, spec: dict[str, object]) -> pd.DataFrame:
    out = trades.copy()
    for col, value in spec.items():
        if col not in out.columns:
            return out.head(0).copy()
        if isinstance(value, bool):
            out = out[out[col].astype(bool) == value].copy()
        else:
            out = out[out[col].astype(str) == str(value)].copy()
    return out.reset_index(drop=True)


def _dedupe_executions(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    data = trades.copy()
    data["_execution_priority"] = data.apply(_execution_priority, axis=1)
    sort_cols = [c for c in ["entry_ts", "exchange", "symbol", "_execution_priority"] if c in data.columns]
    data = data.sort_values(sort_cols).reset_index(drop=True)
    identity = [c for c in ["exchange", "symbol", "entry_ts", "entry", "stop", "target", "direction", "target_model", "management_model"] if c in data.columns]
    if identity:
        data = data.drop_duplicates(subset=identity, keep="first").reset_index(drop=True)
    return data.drop(columns=["_execution_priority"], errors="ignore")


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


def _span_days(ts: pd.Series) -> float:
    times = pd.to_datetime(ts, utc=True)
    if times.empty:
        return 0.0
    return max((times.max() - times.min()).total_seconds() / 86400.0, 1.0)


def _write_report(variants: pd.DataFrame, by_symbol: pd.DataFrame, *, output_path: Path, review_output: Path) -> None:
    lines = [
        "# Crypto Session Setup Lab",
        "",
        "Date: 2026-07-13.",
        "",
        "## Verdict",
        "",
        "- Tested candle/setup filters on London-long `fixed_2r + be_after_half_target` candidates.",
        "- The goal is frequency expansion without accepting the whole noisy London-long universe.",
        "- Candle patterns are treated as confirmation features, not standalone signals.",
        "",
        "## Variant Summary",
        "",
    ]
    lines.extend(_markdown_table(_format_metrics(variants)))
    lines.extend(["", "## Middle/Local Bullish By Symbol", ""])
    lines.extend(_markdown_table(_format_metrics(by_symbol)))
    lines.extend([
        "",
        "## Review Packet",
        "",
        f"- UI packet: `{review_output}`.",
        "- Review `setup_confirm_loser` and `no_confirm_winner` first. Those decide whether candle/setup features are causal.",
        "",
        "## Next Implementation Rule",
        "",
        "- Do not loosen London to all long FVGs. That already fails.",
        "- If candle/setup filters do not improve holdout, the right answer is another module, not more permissive London entries.",
        "",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _format_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col.endswith("_pct") or col.endswith("_rate") or col.endswith("_share"):
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) else "")
        elif col in {"avg_r", "profit_factor", "candidate_per_symbol_day", "accepted_per_symbol_day"}:
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
    parser = argparse.ArgumentParser(description="Run crypto London session setup lab.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT))
    args = parser.parse_args()

    path = Path(args.input)
    trades = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    result = run_session_setup_lab(trades, output_dir=Path(args.output_dir), review_output=Path(args.review_output))
    print(result["variants"].to_string(index=False))
    print(f"review_rows={len(result['review'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

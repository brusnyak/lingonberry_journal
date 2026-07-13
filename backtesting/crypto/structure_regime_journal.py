"""Multi-timeframe structure journal for crypto foundation research.

This is a diagnostic layer, not a signal generator. It joins accepted trades
to causal 15m/60m/240m structure rows, labels trend/pullback/range context,
and summarizes whether structure explains winners and losers.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.direction_layer import DirectionLayerConfig, recent_shock_state, structure_at
from backtesting.crypto.config import DEFAULT_DAYS, DEFAULT_SOURCE


DEFAULT_ACCEPTED_TRADES = Path(
    "backtesting/results/crypto_foundation_validation_reindexed/foundation_accepted_trades.csv"
)
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_structure_regime_journal_reindexed")
DEFAULT_STRUCTURE_ROOT = Path("data/features/structure/L2_R2")


def build_structure_regime_journal(
    trades_path: Path = DEFAULT_ACCEPTED_TRADES,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    structure_root: Path = DEFAULT_STRUCTURE_ROOT,
    days: int = DEFAULT_DAYS,
) -> dict[str, pd.DataFrame]:
    trades = _load_table(trades_path)
    if trades.empty:
        raise ValueError(f"No trades found at {trades_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    enriched = enrich_trades_with_structure(trades, structure_root=structure_root, days=days)
    by_mode = summarize(enriched, ["setup_name", "mtf_mode"])
    by_regime = summarize(enriched, ["setup_name", "context_regime", "middle_regime", "local_regime"])
    by_pa = summarize(enriched, ["setup_name", "compression_state", "shock_alignment"])
    by_foundation = summarize(enriched, ["setup_name", "foundation_state", "consolidation_state", "trend_strength"])
    by_hour = summarize(enriched, ["setup_name", "entry_hour_utc", "mtf_mode"])

    enriched.to_csv(output_dir / "structure_regime_trade_journal.csv", index=False)
    by_mode.to_csv(output_dir / "structure_regime_by_mtf_mode.csv", index=False)
    by_regime.to_csv(output_dir / "structure_regime_by_regime_stack.csv", index=False)
    by_pa.to_csv(output_dir / "structure_regime_by_price_action.csv", index=False)
    by_foundation.to_csv(output_dir / "structure_regime_by_foundation_state.csv", index=False)
    by_hour.to_csv(output_dir / "structure_regime_by_hour.csv", index=False)
    _write_report(enriched, by_mode, by_regime, by_pa, by_foundation, by_hour, output_dir / "structure_regime_report.md")
    return {
        "journal": enriched,
        "by_mode": by_mode,
        "by_regime": by_regime,
        "by_price_action": by_pa,
        "by_foundation": by_foundation,
        "by_hour": by_hour,
    }


def enrich_trades_with_structure(
    trades: pd.DataFrame,
    *,
    structure_root: Path = DEFAULT_STRUCTURE_ROOT,
    days: int = DEFAULT_DAYS,
) -> pd.DataFrame:
    data = trades.copy()
    for col in ["entry_ts", "signal_ts", "bar_ts", "exit_ts"]:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], utc=True, errors="coerce")

    structure_cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    ohlcv_cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    rows: list[dict] = []

    for _, trade in data.iterrows():
        exchange = str(trade.get("exchange", "binance")).lower()
        symbol = str(trade.get("symbol", "")).upper()
        tf = str(trade.get("tf", "15"))
        entry_ts = pd.Timestamp(trade.get("entry_ts"))
        direction = str(trade.get("direction", "")).lower()

        joined = trade.to_dict()
        local = _cached_structure(structure_cache, structure_root, exchange, symbol, tf)
        middle = _cached_structure(structure_cache, structure_root, exchange, symbol, "60")
        context = _cached_structure(structure_cache, structure_root, exchange, symbol, "240")

        local_row = structure_at(local, entry_ts)
        middle_row = structure_at(middle, entry_ts)
        context_row = structure_at(context, entry_ts)
        joined.update(_structure_fields(local_row, "local"))
        joined.update(_structure_fields(middle_row, "middle"))
        joined.update(_structure_fields(context_row, "context"))

        mtf = classify_mtf_mode(
            direction=direction,
            local_regime=joined.get("local_regime", "missing"),
            middle_regime=joined.get("middle_regime", "missing"),
            context_regime=joined.get("context_regime", "missing"),
            local_label=joined.get("local_structure_label", ""),
        )
        joined["mtf_mode"] = mtf
        joined["structure_confirmation"] = classify_structure_confirmation(
            direction=direction,
            local_row=local_row,
            middle_row=middle_row,
            context_row=context_row,
        )

        ohlcv = _cached_ohlcv(ohlcv_cache, exchange, symbol, tf, days)
        joined.update(price_action_snapshot(ohlcv, entry_ts=entry_ts, direction=direction))
        joined["foundation_state"] = classify_foundation_state(
            mtf_mode=joined.get("mtf_mode", "missing_structure"),
            consolidation_state=joined.get("consolidation_state", "unknown"),
            trend_strength=joined.get("trend_strength", "unknown"),
        )
        rows.append(joined)

    out = pd.DataFrame(rows)
    return out.sort_values(["entry_ts", "symbol", "setup_name"], na_position="last").reset_index(drop=True)


def classify_mtf_mode(
    *,
    direction: str,
    local_regime: str,
    middle_regime: str,
    context_regime: str,
    local_label: str = "",
) -> str:
    direction = direction.lower()
    local = _regime(local_regime)
    middle = _regime(middle_regime)
    context = _regime(context_regime)

    if "missing" in {local, middle, context}:
        return "missing_structure"
    if middle == "neutral" or context == "neutral":
        return "range_or_transition"
    if middle != context:
        return "conflict"

    expected = "bull" if direction == "long" else "bear"
    opposite = "bear" if expected == "bull" else "bull"
    if middle == context == expected:
        if local == expected:
            return "trend_aligned"
        if local in {opposite, "neutral"} or local_label in _pullback_labels(direction):
            return "pullback_in_uptrend" if direction == "long" else "pullback_in_downtrend"
    if middle == context == opposite:
        return "countertrend"
    return "mixed"


def classify_structure_confirmation(
    *,
    direction: str,
    local_row: pd.Series | None,
    middle_row: pd.Series | None,
    context_row: pd.Series | None,
) -> str:
    direction = direction.lower()
    local = _regime(None if local_row is None else local_row.get("regime"))
    middle = _regime(None if middle_row is None else middle_row.get("regime"))
    context = _regime(None if context_row is None else context_row.get("regime"))
    expected = "bull" if direction == "long" else "bear"
    if "missing" in {local, middle, context}:
        return "missing_structure"
    local_event = _event_agrees(direction, local_row)
    mtf_agrees = middle == expected and context == expected
    if mtf_agrees and (local == expected or local_event):
        return "mtf_and_local"
    if mtf_agrees:
        return "mtf_only"
    if local == expected or local_event:
        return "local_only"
    if middle == "neutral" or context == "neutral":
        return "range_unconfirmed"
    return "unconfirmed"


def price_action_snapshot(data: pd.DataFrame, *, entry_ts: pd.Timestamp, direction: str) -> dict:
    base = {
        "entry_hour_utc": np.nan,
        "pre_range_atr_8": np.nan,
        "pre_range_atr_16": np.nan,
        "compression_state": "missing_ohlcv",
        "shock_state": "none",
        "shock_alignment": "no_shock",
        "adx_14": np.nan,
        "plus_di_14": np.nan,
        "minus_di_14": np.nan,
        "trend_strength": "unknown",
        "consolidation_state": "unknown",
        "entry_close_position_4": np.nan,
        "pre_return_8_pct": np.nan,
    }
    if data is None or data.empty or "ts" not in data.columns:
        return base

    ohlcv = data.copy()
    ohlcv["ts"] = pd.to_datetime(ohlcv["ts"], utc=True, errors="coerce")
    ohlcv = ohlcv.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    entry = _utc(entry_ts)
    candidates = ohlcv.index[ohlcv["ts"] <= entry].to_list()
    if not candidates:
        return base
    entry_i = int(candidates[-1])
    atr = average_true_range(ohlcv, 14)
    pre_i = max(0, entry_i - 1)

    snap = dict(base)
    snap["entry_hour_utc"] = int(entry.hour)
    snap["pre_range_atr_8"] = range_atr_ratio(ohlcv, atr, pre_i, 8)
    snap["pre_range_atr_16"] = range_atr_ratio(ohlcv, atr, pre_i, 16)
    snap["compression_state"] = compression_bucket(snap["pre_range_atr_16"])
    dmi = directional_movement_index(ohlcv, 14)
    snap["adx_14"] = _series_value(dmi["adx"], pre_i)
    snap["plus_di_14"] = _series_value(dmi["plus_di"], pre_i)
    snap["minus_di_14"] = _series_value(dmi["minus_di"], pre_i)
    snap["trend_strength"] = trend_strength_bucket(snap["adx_14"])
    snap["consolidation_state"] = classify_consolidation_state(
        compression_state=snap["compression_state"],
        trend_strength=snap["trend_strength"],
        pre_range_atr_16=snap["pre_range_atr_16"],
    )
    snap["entry_close_position_4"] = close_position(ohlcv, pre_i, 4)
    snap["pre_return_8_pct"] = pre_return_pct(ohlcv, pre_i, 8)

    shock = recent_shock_state(
        ohlcv,
        entry_i=pre_i,
        atr=atr,
        config=DirectionLayerConfig(shock_lookback_bars=8, shock_range_atr=2.5, shock_body_atr=1.25),
    )
    snap["shock_state"] = shock.get("reason", "none")
    snap["shock_alignment"] = shock_alignment(direction, shock.get("direction", "none"))
    return snap


def compression_bucket(range_atr: float) -> str:
    if not np.isfinite(range_atr):
        return "unknown"
    if range_atr < 2.2:
        return "compressed"
    if range_atr > 5.0:
        return "expanded"
    return "normal"


def directional_movement_index(data: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    close = pd.to_numeric(data["close"], errors="coerce")
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=data.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=data.index)
    tr = pd.concat([(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window, min_periods=max(2, window // 2)).mean()
    plus_di = 100.0 * plus_dm.rolling(window, min_periods=max(2, window // 2)).mean() / atr
    minus_di = 100.0 * minus_dm.rolling(window, min_periods=max(2, window // 2)).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window, min_periods=max(2, window // 2)).mean()
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx})


def trend_strength_bucket(adx: float) -> str:
    if not np.isfinite(adx):
        return "unknown"
    if adx < 18.0:
        return "weak_or_range"
    if adx < 25.0:
        return "transition"
    if adx < 40.0:
        return "trend"
    return "strong_trend"


def classify_consolidation_state(*, compression_state: str, trend_strength: str, pre_range_atr_16: float) -> str:
    compression = str(compression_state)
    strength = str(trend_strength)
    if compression in {"missing_ohlcv", "unknown"} or strength == "unknown":
        return "unknown"
    if compression == "compressed" and strength == "weak_or_range":
        return "tight_range"
    if compression == "normal" and strength == "weak_or_range":
        return "range"
    if compression == "expanded" and strength == "weak_or_range":
        return "volatile_range"
    if compression == "compressed" and strength == "transition":
        return "coiling_transition"
    if strength in {"trend", "strong_trend"} and compression != "compressed":
        return "directional"
    if np.isfinite(pre_range_atr_16) and pre_range_atr_16 < 2.8 and strength == "transition":
        return "range_to_trend_transition"
    return "transition"


def classify_foundation_state(*, mtf_mode: str, consolidation_state: str, trend_strength: str) -> str:
    mtf = str(mtf_mode)
    consolidation = str(consolidation_state)
    strength = str(trend_strength)
    if mtf == "missing_structure" or consolidation == "unknown":
        return "missing"
    if consolidation in {"tight_range", "range", "volatile_range"}:
        return "consolidation"
    if consolidation in {"coiling_transition", "range_to_trend_transition"}:
        return "transition"
    if mtf in {"trend_aligned", "pullback_in_uptrend", "pullback_in_downtrend"} and strength in {"trend", "strong_trend"}:
        return "directional_trend"
    if mtf == "countertrend":
        return "countertrend_risk"
    if mtf in {"range_or_transition", "conflict", "mixed"}:
        return "transition"
    return "mixed"


def shock_alignment(direction: str, shock_direction: str) -> str:
    if shock_direction not in {"bullish", "bearish"}:
        return "no_shock"
    expected = "bullish" if direction == "long" else "bearish"
    return "aligned_shock" if shock_direction == expected else "opposing_shock"


def summarize(data: pd.DataFrame, group_cols: list[str], *, min_trades: int = 10) -> pd.DataFrame:
    rows: list[dict] = []
    for keys, group in data.groupby(group_cols, dropna=False):
        net = pd.to_numeric(group.get("net_r"), errors="coerce").fillna(0.0)
        wins = net[net > 0].sum()
        losses = -net[net < 0].sum()
        pf = float(wins / losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)
        row = {
            **dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,))),
            "trades": int(len(group)),
            "avg_r": float(net.mean()) if len(net) else 0.0,
            "median_r": float(net.median()) if len(net) else 0.0,
            "profit_factor": pf,
            "win_rate": float((net > 0).mean()) if len(net) else 0.0,
            "direction_accuracy": _bool_rate(group, "direction_correct"),
            "bad_direction_rate": _bool_rate(group, "bad_direction"),
            "bad_entry_rate": _bool_rate(group, "bad_entry"),
            "target_too_far_rate": _bool_rate(group, "target_too_far"),
            "stop_after_favorable_rate": _bool_rate(group, "stop_after_favorable"),
            "median_mfe_r": _median(group, "mfe_r"),
            "median_mae_r": _median(group, "mae_r"),
            "research_ready": len(group) >= min_trades,
        }
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["research_ready", "avg_r", "trades"], ascending=[False, False, False]).reset_index(drop=True)


def average_true_range(data: pd.DataFrame, window: int) -> pd.Series:
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    close = pd.to_numeric(data["close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window, min_periods=max(2, window // 2)).mean()


def range_atr_ratio(data: pd.DataFrame, atr: pd.Series, end_i: int, lookback: int) -> float:
    start = max(0, end_i - lookback + 1)
    window = data.iloc[start : end_i + 1]
    if window.empty:
        return np.nan
    atr_now = float(atr.iat[end_i]) if end_i < len(atr) else np.nan
    if not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    return float((window["high"].max() - window["low"].min()) / atr_now)


def close_position(data: pd.DataFrame, end_i: int, lookback: int) -> float:
    start = max(0, end_i - lookback + 1)
    window = data.iloc[start : end_i + 1]
    if window.empty:
        return np.nan
    high = float(window["high"].max())
    low = float(window["low"].min())
    close = float(window["close"].iloc[-1])
    if high <= low:
        return np.nan
    return (close - low) / (high - low)


def pre_return_pct(data: pd.DataFrame, end_i: int, lookback: int) -> float:
    start = max(0, end_i - lookback + 1)
    if end_i <= start:
        return np.nan
    old = float(data["close"].iat[start])
    new = float(data["close"].iat[end_i])
    if old == 0 or not np.isfinite(old):
        return np.nan
    return (new / old) - 1.0


def _structure_fields(row: pd.Series | None, prefix: str) -> dict:
    fields = {
        f"{prefix}_known_after_ts": pd.NaT,
        f"{prefix}_regime": "missing",
        f"{prefix}_structure_label": "",
        f"{prefix}_bos_up": False,
        f"{prefix}_bos_down": False,
        f"{prefix}_choch_up": False,
        f"{prefix}_choch_down": False,
        f"{prefix}_sweep_high": False,
        f"{prefix}_sweep_low": False,
    }
    if row is None:
        return fields
    fields[f"{prefix}_known_after_ts"] = row.get("known_after_ts", pd.NaT)
    fields[f"{prefix}_regime"] = _regime(row.get("regime"))
    fields[f"{prefix}_structure_label"] = str(row.get("structure_label", ""))
    for col in ["bos_up", "bos_down", "choch_up", "choch_down", "sweep_high", "sweep_low"]:
        fields[f"{prefix}_{col}"] = bool(row.get(col, False))
    for col in [
        "long_structural_sl",
        "short_structural_sl",
        "long_target_1",
        "short_target_1",
        "dist_to_long_sl_pct",
        "dist_to_short_sl_pct",
        "dist_to_long_target_pct",
        "dist_to_short_target_pct",
    ]:
        if col in row:
            fields[f"{prefix}_{col}"] = row.get(col, np.nan)
    return fields


def _cached_structure(cache: dict[tuple[str, str, str], pd.DataFrame], root: Path, exchange: str, symbol: str, tf: str) -> pd.DataFrame:
    key = (exchange, symbol, str(tf))
    if key not in cache:
        path = root / exchange / symbol / f"{tf}.parquet"
        cache[key] = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    return cache[key]


def _cached_ohlcv(cache: dict[tuple[str, str, str], pd.DataFrame], exchange: str, symbol: str, tf: str, days: int) -> pd.DataFrame:
    key = (exchange, symbol, str(tf))
    if key not in cache:
        cache[key] = load_crypto(symbol, tf=str(tf), days=days, exchange=exchange, source=DEFAULT_SOURCE)
    return cache[key]


def _event_agrees(direction: str, row: pd.Series | None) -> bool:
    if row is None:
        return False
    if direction == "long":
        return bool(row.get("bos_up", False) or row.get("choch_up", False))
    return bool(row.get("bos_down", False) or row.get("choch_down", False))


def _regime(value: object) -> str:
    if value is None or pd.isna(value):
        return "missing"
    out = str(value).lower()
    return out if out in {"bull", "bear", "neutral"} else ("missing" if out in {"", "nan"} else out)


def _pullback_labels(direction: str) -> set[str]:
    return {"LL", "LH"} if direction == "long" else {"HH", "HL"}


def _bool_rate(group: pd.DataFrame, col: str) -> float:
    if col not in group or group.empty:
        return 0.0
    return float(group[col].astype(bool).mean())


def _median(group: pd.DataFrame, col: str) -> float:
    if col not in group or group.empty:
        return 0.0
    return float(pd.to_numeric(group[col], errors="coerce").median())


def _series_value(series: pd.Series, idx: int) -> float:
    if idx >= len(series):
        return np.nan
    value = float(series.iat[idx])
    return value if np.isfinite(value) else np.nan


def _load_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def _utc(ts: pd.Timestamp) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    if out.tzinfo is None:
        return out.tz_localize("UTC")
    return out.tz_convert("UTC")


def _write_report(
    journal: pd.DataFrame,
    by_mode: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_pa: pd.DataFrame,
    by_foundation: pd.DataFrame,
    by_hour: pd.DataFrame,
    path: Path,
) -> None:
    lines = [
        "# Crypto Structure Regime Journal",
        "",
        "Purpose: explain accepted trades by causal local/middle/context structure and pre-entry price action.",
        "",
        "## Coverage",
        f"- Trades journaled: {len(journal)}",
        f"- Symbols: {journal['symbol'].nunique() if 'symbol' in journal else 0}",
        f"- Entry span: {journal['entry_ts'].min()} .. {journal['entry_ts'].max()}" if "entry_ts" in journal else "- Entry span: unknown",
        "",
        "## Best MTF Modes",
        *_markdown_table(_format_summary(by_mode.head(20))),
        "",
        "## Best Regime Stacks",
        *_markdown_table(_format_summary(by_regime.head(20))),
        "",
        "## Price Action Buckets",
        *_markdown_table(_format_summary(by_pa.head(20))),
        "",
        "## Foundation State Buckets",
        *_markdown_table(_format_summary(by_foundation.head(20))),
        "",
        "## Hour + MTF Buckets",
        *_markdown_table(_format_summary(by_hour.head(25))),
        "",
        "## Interpretation",
        "- `trend_aligned`: local, 60m, and 240m structure agree with trade direction.",
        "- `pullback_in_uptrend/downtrend`: 60m and 240m agree with direction, local structure is neutral/opposed.",
        "- `range_or_transition`: middle or context structure is neutral; trend-follow rules should not be assumed.",
        "- `countertrend`: trade direction opposes both 60m and 240m structure.",
        "- `consolidation_state`: separates actual range compression/weak ADX from trend transition.",
        "- `foundation_state`: combines MTF structure with consolidation so direction gates do not treat all neutral regimes equally.",
        "",
        "## Next Research",
        "- `30/1 approach`: use 30m/60m/240m for global direction, then require 1m or 5m local CHOCH/BOS confirmation before entry.",
        "- London pullback longs need local reclaim confirmation; higher-timeframe uptrend alone is not enough.",
        "- Consolidation gates must be setup-specific: range can help late-US fades but hurts London continuation entries.",
        "- Do not promote stronger ADX blindly; current audit shows `trend` is cleaner than `strong_trend`, likely because extreme trend can mean late/exhausted entry.",
        "- Next validation target: compare kept vs rejected trades for local CHOCH/BOS confirmation without changing legacy stops/targets.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in [
        "avg_r",
        "median_r",
        "profit_factor",
        "win_rate",
        "direction_accuracy",
        "bad_direction_rate",
        "bad_entry_rate",
        "target_too_far_rate",
        "stop_after_favorable_rate",
        "median_mfe_r",
        "median_mae_r",
    ]:
        if col in out:
            out[col] = out[col].map(lambda x: "inf" if x == float("inf") else f"{float(x):.3f}")
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
    parser = argparse.ArgumentParser(description="Build multi-timeframe crypto structure regime journal.")
    parser.add_argument("--trades", default=str(DEFAULT_ACCEPTED_TRADES))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--structure-root", default=str(DEFAULT_STRUCTURE_ROOT))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args()

    result = build_structure_regime_journal(
        Path(args.trades),
        output_dir=Path(args.output_dir),
        structure_root=Path(args.structure_root),
        days=args.days,
    )
    print(f"Journal rows: {len(result['journal'])}")
    print(result["by_mode"].head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

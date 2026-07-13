"""Trend/session matrix for crypto event research.

The current promoted execution bucket is narrow: short-only, 15m, 4H bull
context, late-US session. This module checks whether that is a sensible niche
or whether the engine is simply looking in the wrong place.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.event_atlas import EventAtlasConfig, _bar_delta, build_event_atlas
from backtesting.crypto.index_structure import DEFAULT_SYMBOLS
from backtesting.engine.data import load_data
from backtesting.crypto.config import DEFAULT_DAYS, DEFAULT_SOURCE


@dataclass(frozen=True)
class TrendSessionMatrixConfig:
    days: int = DEFAULT_DAYS
    context_tf: str = "240"
    middle_tf: str = "60"
    ema_fast: int = 21
    ema_slow: int = 55
    min_events: int = 80
    min_symbols: int = 6
    min_exchanges: int = 1
    output_dir: Path = Path("backtesting/results/crypto_trend_session_matrix")


def run_trend_session_matrix(
    *,
    symbols: list[str],
    exchanges: list[str],
    tfs: list[str],
    config: TrendSessionMatrixConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or TrendSessionMatrixConfig()
    rows = []
    for exchange in exchanges:
        for symbol in symbols:
            htf_structure = _load_structure_cache(exchange, symbol, cfg.context_tf)
            global_ema = _ema_context(exchange, symbol, cfg.context_tf, cfg)
            middle_ema = _ema_context(exchange, symbol, cfg.middle_tf, cfg)
            for tf in tfs:
                df = load_data(symbol, tf=tf, days=cfg.days, asset_type="crypto", exchange=exchange, crypto_source=DEFAULT_SOURCE)
                if df.empty:
                    print(f"  {exchange}/{symbol} {tf}: missing data", flush=True)
                    continue
                events = build_event_atlas(
                    df,
                    symbol=symbol,
                    exchange=exchange,
                    tf=tf,
                    config=EventAtlasConfig(),
                    structure=htf_structure,
                    context_tf=cfg.context_tf,
                )
                if events.empty:
                    print(f"  {exchange}/{symbol} {tf}: 0 events", flush=True)
                    continue
                local_ema = _ema_from_frame(df, tf=tf, cfg=cfg).rename(columns={
                    "ema_state": "local_ema_state",
                    "ema_fast": "local_ema_fast",
                    "ema_slow": "local_ema_slow",
                })
                enriched = _attach_ema(events, global_ema, prefix="global")
                enriched = _attach_ema(enriched, middle_ema, prefix="middle")
                enriched = _attach_ema(enriched, local_ema, prefix="local")
                enriched = _classify_trend(enriched)
                rows.append(enriched)
                print(f"  {exchange}/{symbol} {tf}: {len(enriched)} events", flush=True)
    events_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = summarize_matrix(
        events_df,
        min_events=cfg.min_events,
        min_symbols=cfg.min_symbols,
        min_exchanges=cfg.min_exchanges,
    )
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    events_df.to_parquet(cfg.output_dir / "trend_session_events.parquet", index=False)
    summary.to_csv(cfg.output_dir / "trend_session_summary.csv", index=False)
    write_matrix_report(events_df, summary, cfg.output_dir / "trend_session_report.md", cfg)
    return events_df, summary


def summarize_matrix(
    events: pd.DataFrame,
    *,
    min_events: int = 80,
    min_symbols: int = 6,
    min_exchanges: int = 1,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events[events["event"].isin(["bullish_fvg_formation", "bearish_fvg_formation"])].copy()
    group_cols = [
        "tf",
        "session_utc",
        "direction",
        "ctx_240_regime",
        "trend_alignment",
        "global_ema_state",
        "middle_ema_state",
        "local_ema_state",
        "stop_model",
        "target_model",
    ]
    for col in group_cols:
        if col not in data.columns:
            data[col] = "unknown"
    rows = []
    for keys, group in data.groupby(group_cols, dropna=False):
        net = pd.to_numeric(group["net_r"], errors="coerce").dropna()
        if net.empty:
            continue
        wins = net[net > 0]
        losses = net[net < 0]
        span_days = _span_days(group["signal_ts"])
        rows.append({
            **dict(zip(group_cols, keys)),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "exchanges": int(group["exchange"].nunique()),
            "events_per_day": float(len(group) / span_days) if span_days > 0 else np.nan,
            "events_per_symbol_exchange_day": float(len(group) / (span_days * max(group["symbol"].nunique(), 1) * max(group["exchange"].nunique(), 1))) if span_days > 0 else np.nan,
            "avg_r": float(net.mean()),
            "median_r": float(net.median()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "hit_1r_rate": float(group["hit_1r"].mean()),
            "hit_target_rate": float(group["hit_target"].mean()),
            "stop_rate": float(group["hit_stop"].mean()),
            "median_mfe_r": float(group["mfe_r"].median()),
            "median_mae_r": float(group["mae_r"].median()),
            "research_ready": bool(
                len(group) >= min_events
                and group["symbol"].nunique() >= min_symbols
                and group["exchange"].nunique() >= min_exchanges
            ),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["research_ready", "avg_r", "profit_factor", "events"], ascending=[False, False, False, False]).reset_index(drop=True)


def write_matrix_report(events: pd.DataFrame, summary: pd.DataFrame, output_path: Path, cfg: TrendSessionMatrixConfig) -> None:
    lines = [
        "# Crypto Trend/Session Matrix",
        "",
        "Date: 2026-07-13.",
        "",
        "## Scope",
        "",
        f"- Days: `{cfg.days}`.",
        "- Signal timeframes: `5m`, `15m` unless CLI overrides.",
        f"- Global trend helper: `{cfg.context_tf}m EMA {cfg.ema_fast}/{cfg.ema_slow}` plus structure regime.",
        f"- Middle trend helper: `{cfg.middle_tf}m EMA {cfg.ema_fast}/{cfg.ema_slow}`.",
        "- Local trend helper: signal-timeframe EMA 21/55.",
        "- Event family in summary: bullish/bearish FVG formation.",
        "",
    ]
    if events.empty or summary.empty:
        lines.extend(["No events generated.", ""])
        output_path.write_text("\n".join(lines))
        return
    span_days = _span_days(events["signal_ts"])
    lines.extend([
        "## Frequency",
        "",
        f"- Total event rows: `{len(events)}`.",
        f"- FVG event rows: `{len(events[events['event'].isin(['bullish_fvg_formation', 'bearish_fvg_formation'])])}`.",
        f"- Span days: `{span_days:.1f}`.",
        "",
    ])
    top = summary[(summary["research_ready"]) & (summary["profit_factor"] >= 1.2) & (summary["avg_r"] > 0)].head(20)
    lines.extend(["## Top Research-Ready Buckets", ""])
    if top.empty:
        lines.append("No research-ready bucket passed `avg_r > 0` and `PF >= 1.2`.")
    else:
        show = top[[
            "tf", "session_utc", "direction", "ctx_240_regime", "trend_alignment",
            "stop_model", "target_model", "events", "symbols", "exchanges",
            "events_per_symbol_exchange_day", "avg_r", "profit_factor", "hit_target_rate", "stop_rate",
        ]].copy()
        for col in ["events_per_symbol_exchange_day", "avg_r", "profit_factor", "hit_target_rate", "stop_rate"]:
            show[col] = show[col].map(lambda x: f"{x:.3f}")
        lines.extend(_markdown_table(show))
    lines.extend(["", "## Alignment Summary", ""])
    align = _simple_bucket(events[events["event"].isin(["bullish_fvg_formation", "bearish_fvg_formation"])], ["tf", "trend_alignment"])
    lines.extend(_markdown_table(align))
    lines.extend(["", "## Session Summary", ""])
    sess = _simple_bucket(events[events["event"].isin(["bullish_fvg_formation", "bearish_fvg_formation"])], ["tf", "session_utc"])
    lines.extend(_markdown_table(sess))
    lines.extend(["", "## Judgment", ""])
    lines.append("- This matrix is event-level research, not final execution-path validation.")
    lines.append("- If trend-following buckets beat countertrend buckets, the current night countertrend engine should be demoted.")
    lines.append("- If no session outside late-US works, the engine is a niche overnight crypto strategy, not a general intraday engine.")
    lines.append("- If frequency remains below about `0.10` events per symbol/exchange/day after broadening sessions and trend modes, the setup is intrinsically rare.")
    output_path.write_text("\n".join(lines) + "\n")


def _ema_context(exchange: str, symbol: str, tf: str, cfg: TrendSessionMatrixConfig) -> pd.DataFrame:
    df = load_data(symbol, tf=tf, days=cfg.days + 20, asset_type="crypto", exchange=exchange, crypto_source=DEFAULT_SOURCE)
    if df.empty:
        return pd.DataFrame(columns=["known_after_ts", "ema_state", "ema_fast", "ema_slow"])
    return _ema_from_frame(df, tf=tf, cfg=cfg)


def _ema_from_frame(df: pd.DataFrame, *, tf: str, cfg: TrendSessionMatrixConfig) -> pd.DataFrame:
    data = df[["ts", "close"]].copy().sort_values("ts").reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    close = pd.to_numeric(data["close"], errors="coerce")
    fast = close.ewm(span=cfg.ema_fast, adjust=False).mean()
    slow = close.ewm(span=cfg.ema_slow, adjust=False).mean()
    slope = fast.diff()
    state = np.where((close > fast) & (fast >= slow) & (slope >= 0), "bullish",
        np.where((close < fast) & (fast <= slow) & (slope <= 0), "bearish", "mixed"))
    delta = _tf_delta(data, tf)
    return pd.DataFrame({
        "known_after_ts": data["ts"] + delta,
        "ema_state": state,
        "ema_fast": fast,
        "ema_slow": slow,
    }).dropna(subset=["known_after_ts"])


def _attach_ema(events: pd.DataFrame, ema: pd.DataFrame, *, prefix: str) -> pd.DataFrame:
    out = events.copy()
    for col in [f"{prefix}_ema_state", f"{prefix}_ema_fast", f"{prefix}_ema_slow"]:
        if col in out.columns:
            out = out.drop(columns=[col])
    if ema.empty:
        out[f"{prefix}_ema_state"] = "unknown"
        out[f"{prefix}_ema_fast"] = np.nan
        out[f"{prefix}_ema_slow"] = np.nan
        return out
    right = ema.copy().rename(columns={
        "ema_state": f"{prefix}_ema_state",
        "ema_fast": f"{prefix}_ema_fast",
        "ema_slow": f"{prefix}_ema_slow",
    })
    out["signal_ts"] = pd.to_datetime(out["signal_ts"], utc=True, errors="coerce").astype("datetime64[ns, UTC]")
    right["known_after_ts"] = pd.to_datetime(right["known_after_ts"], utc=True, errors="coerce").astype("datetime64[ns, UTC]")
    return pd.merge_asof(
        out.sort_values("signal_ts"),
        right.sort_values("known_after_ts"),
        left_on="signal_ts",
        right_on="known_after_ts",
        direction="backward",
    ).drop(columns=["known_after_ts"], errors="ignore")


def _classify_trend(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    align = []
    for row in out.itertuples(index=False):
        direction = str(getattr(row, "direction", "")).lower()
        desired = "bullish" if direction == "long" else "bearish"
        opposite = "bearish" if direction == "long" else "bullish"
        states = [
            str(getattr(row, "global_ema_state", "unknown")),
            str(getattr(row, "middle_ema_state", "unknown")),
            str(getattr(row, "local_ema_state", "unknown")),
        ]
        htf_regime = str(getattr(row, "ctx_240_regime", "unknown")).lower()
        regime_aligned = (direction == "long" and htf_regime == "bull") or (direction == "short" and htf_regime == "bear")
        if all(s == desired for s in states) and regime_aligned:
            align.append("full_trend")
        elif states[0] == desired and states[1] == desired:
            align.append("global_middle_ema")
        elif states[1] == desired and states[2] == desired:
            align.append("middle_local_ema")
        elif states[0] == opposite or not regime_aligned:
            align.append("counter_global_or_structure")
        else:
            align.append("mixed")
    out["trend_alignment"] = align
    return out


def _simple_bucket(events: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in events.groupby(group_cols, dropna=False):
        net = pd.to_numeric(group["net_r"], errors="coerce").dropna()
        wins = net[net > 0]
        losses = net[net < 0]
        rows.append({
            **dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,))),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "avg_r": f"{net.mean():+.3f}",
            "pf": f"{(wins.sum() / abs(losses.sum())):.3f}" if abs(losses.sum()) > 0 else "inf",
            "stop_rate": f"{group['hit_stop'].mean():.3f}",
        })
    return pd.DataFrame(rows).sort_values(["events"], ascending=False).reset_index(drop=True)


def _span_days(ts: pd.Series) -> float:
    s = pd.to_datetime(ts, utc=True, errors="coerce").dropna()
    if s.empty:
        return 0.0
    return max((s.max() - s.min()).total_seconds() / 86400.0, 1.0)


def _tf_delta(df: pd.DataFrame, tf: str) -> pd.Timedelta:
    if str(tf).isdigit():
        return pd.Timedelta(minutes=int(tf))
    return _bar_delta(df.assign(open=0, high=0, low=0))


def _load_structure_cache(exchange: str, symbol: str, tf: str, root: Path = Path("data/features/structure/L2_R2")) -> pd.DataFrame:
    path = root / exchange / symbol / f"{tf}.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_empty_"]
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run crypto trend/session matrix research.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--tfs", default="5,15")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--output-dir", default=str(TrendSessionMatrixConfig.output_dir))
    parser.add_argument("--min-events", type=int, default=80)
    parser.add_argument("--min-symbols", type=int, default=6)
    parser.add_argument("--min-exchanges", type=int, default=1)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    tfs = [tf.strip() for tf in args.tfs.split(",") if tf.strip()]
    cfg = TrendSessionMatrixConfig(
        days=args.days,
        output_dir=Path(args.output_dir),
        min_events=args.min_events,
        min_symbols=args.min_symbols,
        min_exchanges=args.min_exchanges,
    )
    events, summary = run_trend_session_matrix(symbols=symbols, exchanges=exchanges, tfs=tfs, config=cfg)
    print(f"Events: {len(events)}")
    print(f"Summary rows: {len(summary)}")
    if not summary.empty:
        print(summary.head(30).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

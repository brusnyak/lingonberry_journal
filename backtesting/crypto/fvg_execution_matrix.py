"""Executable FVG retest matrix across sessions and trend states.

The trend/session atlas shows raw FVG events are frequent. This module answers
the next question: after requiring an executable retest, prior-swing stop, and
basic management, which sessions/directions still work?
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.direction_layer import DirectionLayerConfig, has_direction_confirmation, has_opposing_spike
from backtesting.crypto.event_atlas import _atr, _bar_delta, _session_utc, _vol_bucket
from backtesting.crypto.index_structure import DEFAULT_SYMBOLS
from backtesting.crypto.trend_session_matrix import _attach_ema, _classify_trend, _ema_context, _ema_from_frame
from backtesting.engine.data import load_data
from backtesting.features.structure import build_structure_index


@dataclass(frozen=True)
class FvgExecutionMatrixConfig:
    days: int = 60
    crypto_source: str = "exchange"
    tf: str = "15"
    context_tf: str = "240"
    middle_tf: str = "60"
    ema_fast: int = 21
    ema_slow: int = 55
    lookback_bars: int = 24
    horizon_bars: int = 24
    retest_bars: int = 8
    atr_period: int = 14
    min_stop_pct: float = 0.001
    stale_retest_bars: int = 4
    duplicate_zone_tolerance_pct: float = 0.0005
    duplicate_cooldown_bars: int = 12
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    output_dir: Path = Path("backtesting/results/crypto_fvg_execution_matrix")
    direction_config: DirectionLayerConfig = DirectionLayerConfig()


def run_fvg_execution_matrix(
    *,
    symbols: list[str],
    exchanges: list[str],
    config: FvgExecutionMatrixConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or FvgExecutionMatrixConfig()
    rows = []
    for exchange in exchanges:
        for symbol in symbols:
            df = load_data(symbol, tf=cfg.tf, days=cfg.days, asset_type="crypto", exchange=exchange, crypto_source=cfg.crypto_source)
            if df.empty:
                print(f"  {exchange}/{symbol} {cfg.tf}: missing data", flush=True)
                continue
            context = _load_structure_cache(exchange, symbol, cfg.context_tf)
            entry_structure = _load_structure_cache(exchange, symbol, cfg.tf)
            if entry_structure.empty:
                entry_structure = build_structure_index(df)
            trades = evaluate_symbol(df, symbol=symbol, exchange=exchange, context=context, entry_structure=entry_structure, config=cfg)
            if not trades.empty:
                global_ema = _ema_context(exchange, symbol, cfg.context_tf, cfg)
                middle_ema = _ema_context(exchange, symbol, cfg.middle_tf, cfg)
                local_ema = _ema_from_frame(df, tf=cfg.tf, cfg=cfg).rename(columns={
                    "ema_state": "local_ema_state",
                    "ema_fast": "local_ema_fast",
                    "ema_slow": "local_ema_slow",
                })
                trades = _attach_ema(trades, global_ema, prefix="global")
                trades = _attach_ema(trades, middle_ema, prefix="middle")
                trades = _attach_ema(trades, local_ema, prefix="local")
                trades = _classify_trend(trades)
                rows.append(trades)
            print(f"  {exchange}/{symbol} {cfg.tf}: {len(trades)} execution rows", flush=True)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = summarize_execution_matrix(out)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cfg.output_dir / "fvg_execution_trades.parquet", index=False)
    summary.to_csv(cfg.output_dir / "fvg_execution_summary.csv", index=False)
    write_execution_report(out, summary, cfg.output_dir / "fvg_execution_report.md", cfg)
    return out, summary


def evaluate_symbol(
    df: pd.DataFrame,
    *,
    symbol: str,
    exchange: str,
    context: pd.DataFrame,
    entry_structure: pd.DataFrame,
    config: FvgExecutionMatrixConfig | None = None,
) -> pd.DataFrame:
    cfg = config or FvgExecutionMatrixConfig()
    data = _prepare(df)
    if len(data) < cfg.lookback_bars + cfg.horizon_bars + cfg.retest_bars + 5:
        return pd.DataFrame()
    atr = _atr(data, cfg.atr_period)
    atr_pct = atr / data["close"]
    prev_high = data["high"].shift(1).rolling(cfg.lookback_bars).max()
    prev_low = data["low"].shift(1).rolling(cfg.lookback_bars).min()
    rows: list[dict] = []
    seen_zones: dict[tuple[str, int, int], int] = {}
    max_i = len(data) - cfg.horizon_bars - cfg.retest_bars - 2
    for i in range(max(cfg.lookback_bars, 2), max_i):
        if not np.isfinite(atr.iat[i]) or atr.iat[i] <= 0:
            continue
        ctx = _context_row(context, data["ts"].iat[i] + _bar_delta(data))
        base = {
            "exchange": exchange,
            "symbol": symbol,
            "tf": str(cfg.tf),
            "signal_i": i,
            "bar_ts": data["ts"].iat[i],
            "signal_ts": data["ts"].iat[i] + _bar_delta(data),
            "session_utc": _session_utc(data["ts"].iat[i]),
            "vol_bucket": _vol_bucket(float(atr_pct.iat[i])) if np.isfinite(atr_pct.iat[i]) else "unknown",
            "ctx_240_regime": str(ctx.get("regime", "unknown")),
        }
        c1_high = float(data["high"].iat[i - 2])
        c1_low = float(data["low"].iat[i - 2])
        c3_high = float(data["high"].iat[i])
        c3_low = float(data["low"].iat[i])
        if c3_high < c1_low and np.isfinite(prev_high.iat[i]):
            fvg_top = c1_low
            fvg_bottom = c3_high
            if not _is_duplicate_zone("short", i, fvg_top, fvg_bottom, seen_zones, cfg):
                rows.extend(_score_signal(data, i, "short", float(prev_high.iat[i]), fvg_top, fvg_bottom, atr, entry_structure, base, cfg))
        if c3_low > c1_high and np.isfinite(prev_low.iat[i]):
            fvg_top = c3_low
            fvg_bottom = c1_high
            if not _is_duplicate_zone("long", i, fvg_top, fvg_bottom, seen_zones, cfg):
                rows.extend(_score_signal(data, i, "long", float(prev_low.iat[i]), fvg_top, fvg_bottom, atr, entry_structure, base, cfg))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out[~out["invalid"]].reset_index(drop=True)


def summarize_execution_matrix(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    group_cols = [
        "session_utc", "direction", "ctx_240_regime", "trend_alignment",
        "global_ema_state", "middle_ema_state", "local_ema_state",
        "entry_model", "target_model", "management_model", "confirmation_model",
    ]
    rows = []
    for keys, group in trades.groupby(group_cols, dropna=False):
        net = pd.to_numeric(group["net_r"], errors="coerce").dropna()
        wins = net[net > 0]
        losses = net[net < 0]
        span_days = _span_days(group["entry_ts"])
        rows.append({
            **dict(zip(group_cols, keys)),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "exchanges": int(group["exchange"].nunique()),
            "events_per_symbol_day": float(len(group) / (span_days * max(group["symbol"].nunique(), 1))) if span_days > 0 else np.nan,
            "avg_r": float(net.mean()),
            "median_r": float(net.median()),
            "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf,
            "target_rate": float(group["hit_target"].mean()),
            "stop_rate": float(group["hit_stop"].mean()),
            "expiry_rate": float((group["exit_reason"] == "expiry").mean()),
            "hit_1r_rate": float(group["hit_1r"].mean()),
            "median_mfe_r": float(group["mfe_r"].median()),
            "median_mae_r": float(group["mae_r"].median()),
            "research_ready": bool(len(group) >= 60 and group["symbol"].nunique() >= 6),
        })
    return pd.DataFrame(rows).sort_values(["research_ready", "avg_r", "profit_factor", "events"], ascending=[False, False, False, False]).reset_index(drop=True)


def write_execution_report(trades: pd.DataFrame, summary: pd.DataFrame, output_path: Path, cfg: FvgExecutionMatrixConfig) -> None:
    lines = [
        "# Crypto FVG Execution Matrix",
        "",
        "Date: 2026-07-13.",
        "",
        "## Scope",
        "",
        f"- Timeframe: `{cfg.tf}m`.",
        f"- Days: `{cfg.days}`.",
        "- Exchange scope: intended for first-pass single-exchange price-action research.",
        "- Entry models: FVG CE retest, FVG edge retest, next open.",
        "- Confirmation models: raw and causal structure-confirmed.",
        "- Targets: fixed `1.5R`, fixed `2R`.",
        "- Management: hold, BE after half target, partial `1R` + BE after half target.",
        "",
    ]
    if trades.empty or summary.empty:
        lines.append("No trades generated.")
        output_path.write_text("\n".join(lines) + "\n")
        return
    lines.extend([
        "## Frequency",
        "",
        f"- Execution rows: `{len(trades)}`.",
        f"- Unique signals: `{trades[['exchange', 'symbol', 'signal_i', 'direction']].drop_duplicates().shape[0]}`.",
        f"- Symbols: `{trades['symbol'].nunique()}`.",
        "",
        "## Top Research-Ready Buckets",
        "",
    ])
    top = summary[(summary["research_ready"]) & (summary["avg_r"] > 0) & (summary["profit_factor"] >= 1.2)].head(25)
    if top.empty:
        lines.append("No execution bucket passed `avg_r > 0`, `PF >= 1.2`, `events >= 60`, `symbols >= 6`.")
    else:
        show = top[[
            "session_utc", "direction", "ctx_240_regime", "trend_alignment",
            "entry_model", "target_model", "management_model", "confirmation_model",
            "events", "symbols", "events_per_symbol_day", "avg_r", "profit_factor",
            "target_rate", "stop_rate", "expiry_rate",
        ]].copy()
        for col in ["events_per_symbol_day", "avg_r", "profit_factor", "target_rate", "stop_rate", "expiry_rate"]:
            show[col] = show[col].map(lambda x: f"{x:.3f}")
        lines.extend(_markdown_table(show))
    lines.extend(["", "## Session/Direction Aggregate", ""])
    agg = _aggregate_summary(summary, ["session_utc", "direction", "trend_alignment"])
    lines.extend(_markdown_table(agg.head(30)))
    lines.extend(["", "## Judgment", ""])
    lines.append("- If daytime buckets fail here, raw event strength is not executable edge.")
    lines.append("- If a daytime bucket survives here, the old late-US module should stop being treated as the main engine.")
    lines.append("- Frequency target for a general intraday engine should be near daily per active symbol before portfolio throttles.")
    output_path.write_text("\n".join(lines) + "\n")


def _score_signal(
    data: pd.DataFrame,
    i: int,
    direction: str,
    stop: float,
    fvg_top: float,
    fvg_bottom: float,
    atr: pd.Series,
    entry_structure: pd.DataFrame,
    base: dict,
    cfg: FvgExecutionMatrixConfig,
) -> list[dict]:
    ce = (fvg_top + fvg_bottom) / 2.0
    plans = [{"entry_model": "next_open", "entry_i": i + 1, "entry": float(data["open"].iat[i + 1]), "bars_to_entry": 1}]
    if direction == "short":
        plans.extend(_limit_plan(data, i, direction, fvg_top, "fvg_edge_retest", cfg))
        plans.extend(_limit_plan(data, i, direction, ce, "fvg_ce_retest", cfg))
    else:
        plans.extend(_limit_plan(data, i, direction, fvg_bottom, "fvg_edge_retest", cfg))
        plans.extend(_limit_plan(data, i, direction, ce, "fvg_ce_retest", cfg))

    rows = []
    for plan in plans:
        rows.extend(_score_plan(data, i, direction, stop, plan, atr, entry_structure, base, "none", cfg))
        confirmed = _confirmation_model(data, i, direction, plan, atr, entry_structure, cfg)
        if confirmed is not None:
            rows.extend(_score_plan(data, i, direction, stop, plan, atr, entry_structure, base, confirmed, cfg))
    return rows


def _score_plan(
    data: pd.DataFrame,
    signal_i: int,
    direction: str,
    stop: float,
    plan: dict,
    atr: pd.Series,
    entry_structure: pd.DataFrame,
    base: dict,
    confirmation_model: str,
    cfg: FvgExecutionMatrixConfig,
) -> list[dict]:
    entry_i = int(plan["entry_i"])
    entry = float(plan["entry"])
    min_stop = entry * cfg.min_stop_pct
    if direction == "short":
        stop = max(stop, entry + min_stop)
        risk = stop - entry
        if risk <= 0:
            return [{**base, "direction": direction, "entry_model": plan["entry_model"], "invalid": True}]
        targets = {"fixed_1_5r": entry - 1.5 * risk, "fixed_2r": entry - 2.0 * risk}
        fwd = data.iloc[entry_i:entry_i + cfg.horizon_bars]
        mfe_r = (entry - float(fwd["low"].min())) / risk
        mae_r = (entry - float(fwd["high"].max())) / risk
    else:
        stop = min(stop, entry - min_stop)
        risk = entry - stop
        if risk <= 0:
            return [{**base, "direction": direction, "entry_model": plan["entry_model"], "invalid": True}]
        targets = {"fixed_1_5r": entry + 1.5 * risk, "fixed_2r": entry + 2.0 * risk}
        fwd = data.iloc[entry_i:entry_i + cfg.horizon_bars]
        mfe_r = (float(fwd["high"].max()) - entry) / risk
        mae_r = (float(fwd["low"].min()) - entry) / risk
    rows = []
    for target_model, target in targets.items():
        for management_model in ["hold_target_expiry", "be_after_half_target", "partial_1r_be_after_half_target"]:
            outcome = _managed_outcome(fwd, direction, entry, stop, target, risk, cfg, management_model)
            rows.append({
                **base,
                "direction": direction,
                "entry_model": f"{'structure_confirmed_' if confirmation_model != 'none' else ''}{plan['entry_model']}",
                "target_model": target_model,
                "management_model": management_model,
                "entry_ts": data["ts"].iat[entry_i],
                "entry": entry,
                "stop": stop,
                "target": target,
                "risk_price": risk,
                "confirmation_model": confirmation_model,
                "gross_r": outcome["gross_r"],
                "cost_r": outcome["cost_r"],
                "net_r": outcome["net_r"],
                "mfe_r": mfe_r,
                "mae_r": mae_r,
                "hit_1r": outcome["hit_1r"],
                "hit_target": outcome["hit_target"],
                "hit_stop": outcome["hit_stop"],
                "exit_reason": outcome["exit_reason"],
                "bars_to_entry": plan["bars_to_entry"],
                "bars_to_exit": outcome["bars_to_exit"],
                "invalid": False,
            })
    return rows


def _managed_outcome(
    fwd: pd.DataFrame,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    risk: float,
    cfg: FvgExecutionMatrixConfig,
    management_model: str,
) -> dict:
    sign = -1 if direction == "short" else 1
    one_r = entry + sign * risk
    half_target = entry + 0.5 * (target - entry)
    active_stop = stop
    hit_1r = False
    partial_taken = False
    gross_locked = 0.0
    exit_reason = "expiry"
    exit_price = float(fwd["close"].iat[-1])
    bars_to_exit = len(fwd)
    hit_target = False
    hit_stop = False
    for offset, row in enumerate(fwd.itertuples(index=False), start=1):
        high = float(row.high)
        low = float(row.low)
        stop_hit = high >= active_stop if direction == "short" else low <= active_stop
        target_hit = low <= target if direction == "short" else high >= target
        half_hit = low <= half_target if direction == "short" else high >= half_target
        one_r_hit = low <= one_r if direction == "short" else high >= one_r
        if stop_hit:
            exit_reason = "stop" if active_stop != entry else "breakeven"
            exit_price = active_stop
            hit_stop = active_stop != entry
            bars_to_exit = offset
            break
        if target_hit:
            exit_reason = "target"
            exit_price = target
            hit_target = True
            hit_1r = True
            bars_to_exit = offset
            break
        if half_hit and management_model in {"be_after_half_target", "partial_1r_be_after_half_target"}:
            active_stop = entry
        if one_r_hit and not hit_1r:
            hit_1r = True
            if management_model == "partial_1r_be_after_half_target":
                active_stop = entry
                gross_locked = 0.5
                partial_taken = True
    remainder_r = ((entry - exit_price) / risk) if direction == "short" else ((exit_price - entry) / risk)
    gross_r = 0.5 * remainder_r + gross_locked if partial_taken else remainder_r
    exit_fee = cfg.taker_fee if exit_reason in {"stop", "expiry", "breakeven"} else cfg.maker_fee
    cost_r = ((entry * cfg.taker_fee) + (exit_price * exit_fee)) / risk
    if partial_taken:
        cost_r += (one_r * cfg.maker_fee) / risk * 0.5
    return {
        "gross_r": gross_r,
        "cost_r": cost_r,
        "net_r": gross_r - cost_r,
        "hit_1r": hit_1r,
        "hit_target": hit_target,
        "hit_stop": hit_stop,
        "exit_reason": exit_reason,
        "bars_to_exit": bars_to_exit,
    }


def _limit_plan(data: pd.DataFrame, i: int, direction: str, entry_price: float, name: str, cfg: FvgExecutionMatrixConfig) -> list[dict]:
    end = min(i + cfg.retest_bars + 1, len(data) - cfg.horizon_bars - 1)
    for j in range(i + 1, end + 1):
        if direction == "short" and float(data["high"].iat[j]) >= entry_price:
            return [{"entry_model": name, "entry_i": j, "entry": entry_price, "bars_to_entry": j - i}]
        if direction == "long" and float(data["low"].iat[j]) <= entry_price:
            return [{"entry_model": name, "entry_i": j, "entry": entry_price, "bars_to_entry": j - i}]
    return []


def _confirmation_model(
    data: pd.DataFrame,
    signal_i: int,
    direction: str,
    plan: dict,
    atr: pd.Series,
    entry_structure: pd.DataFrame,
    cfg: FvgExecutionMatrixConfig,
) -> str | None:
    if int(plan["bars_to_entry"]) > cfg.stale_retest_bars:
        return None
    entry_i = int(plan["entry_i"])
    spike, _reason = has_opposing_spike(data, direction=direction, entry_i=entry_i, atr=atr, config=cfg.direction_config)
    if spike:
        return None
    ok, reason, _confirmation_ts = has_direction_confirmation(
        entry_structure,
        direction=direction,
        signal_ts=data["ts"].iat[signal_i] + _bar_delta(data),
        entry_ts=data["ts"].iat[entry_i],
        bar_delta=_bar_delta(data),
        config=cfg.direction_config,
    )
    return reason if ok else None


def _context_row(structure: pd.DataFrame, signal_ts: pd.Timestamp) -> pd.Series:
    if structure is None or structure.empty or "known_after_ts" not in structure.columns:
        return pd.Series(dtype=object)
    s = structure.copy()
    s["known_after_ts"] = pd.to_datetime(s["known_after_ts"], utc=True, errors="coerce")
    s = s[s["known_after_ts"] <= pd.Timestamp(signal_ts)].dropna(subset=["known_after_ts"]).sort_values("known_after_ts")
    if s.empty:
        return pd.Series(dtype=object)
    return s.iloc[-1]


def _is_duplicate_zone(direction: str, i: int, fvg_top: float, fvg_bottom: float, seen_zones: dict[tuple[str, int, int], int], cfg: FvgExecutionMatrixConfig) -> bool:
    tolerance = max(abs(fvg_top) * cfg.duplicate_zone_tolerance_pct, 1e-12)
    key = (direction, round(fvg_top / tolerance), round(fvg_bottom / tolerance))
    last_i = seen_zones.get(key)
    if last_i is not None and i - last_i <= cfg.duplicate_cooldown_bars:
        return True
    seen_zones[key] = i
    return False


def _aggregate_summary(summary: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    ready = summary[summary["research_ready"]].copy()
    for keys, group in ready.groupby(group_cols, dropna=False):
        w = group["events"].astype(float)
        rows.append({
            **dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,))),
            "events": int(w.sum()),
            "buckets": int(len(group)),
            "weighted_avg_r": f"{((group['avg_r'] * w).sum() / w.sum()):+.3f}",
            "weighted_stop": f"{((group['stop_rate'] * w).sum() / w.sum()):.3f}",
            "max_avg_r": f"{group['avg_r'].max():+.3f}",
            "max_pf": f"{group['profit_factor'].replace(np.inf, np.nan).max():.3f}",
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("events", ascending=False).reset_index(drop=True)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    data = df[["ts", "open", "high", "low", "close"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna().sort_values("ts").reset_index(drop=True)


def _span_days(ts: pd.Series) -> float:
    s = pd.to_datetime(ts, utc=True, errors="coerce").dropna()
    if s.empty:
        return 0.0
    return max((s.max() - s.min()).total_seconds() / 86400.0, 1.0)


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
    parser = argparse.ArgumentParser(description="Run executable FVG retest matrix across sessions.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--exchange", default="binance", choices=["binance", "bybit", "both"])
    parser.add_argument("--tf", default="15")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--output-dir", default=str(FvgExecutionMatrixConfig.output_dir))
    parser.add_argument("--source", default="exchange", choices=["exchange", "legacy", "merged"],
                         help="'exchange' caps history to exchange-scoped files (~90-120d); "
                              "'merged' pulls in deep legacy history (multi-year) too.")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    cfg = FvgExecutionMatrixConfig(days=args.days, tf=args.tf, output_dir=Path(args.output_dir), crypto_source=args.source)
    trades, summary = run_fvg_execution_matrix(symbols=symbols, exchanges=exchanges, config=cfg)
    print(f"Execution rows: {len(trades)}")
    print(f"Summary rows: {len(summary)}")
    if not summary.empty:
        print(summary.head(30).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

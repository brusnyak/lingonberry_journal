"""Rolling validation for event-atlas buckets.

The atlas tells us which event-plan-context combinations look positive in a
sample. This module checks whether those buckets survive rolling windows and
basic concentration tests before they are promoted to strategy construction.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BUCKET_COLS = [
    "event",
    "direction",
    "stop_model",
    "target_model",
    "ctx_240_regime",
    "session_utc",
    "vol_bucket",
]


@dataclass(frozen=True)
class ValidationGate:
    min_events: int = 100
    min_windows: int = 4
    min_pf: float = 1.20
    min_avg_net_r: float = 0.05
    min_median_window_r: float = 0.0
    min_positive_window_rate: float = 0.55
    max_concentration: float = 0.60
    min_target_r: float = 1.5
    min_median_target_r: float = 1.8
    min_median_risk_pct: float = 0.0015


def validate_event_buckets(
    events: pd.DataFrame,
    *,
    bucket_cols: list[str] | None = None,
    window_days: int = 14,
    step_days: int = 7,
    gate: ValidationGate | None = None,
) -> pd.DataFrame:
    """Return rolling validation stats for each event/context bucket."""
    if events.empty:
        return pd.DataFrame()
    cfg = gate or ValidationGate()
    bucket_cols = bucket_cols or [c for c in DEFAULT_BUCKET_COLS if c in events.columns]
    data = _prepare_events(events, bucket_cols)
    if "target_r" in data.columns:
        data = data[data["target_r"] >= cfg.min_target_r].reset_index(drop=True)
    if data.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for keys, group in data.groupby(bucket_cols, dropna=False):
        if len(group) < cfg.min_events:
            continue
        windows = _rolling_windows(group, window_days=window_days, step_days=step_days)
        if windows.empty:
            continue
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        gross_loss = abs(float(losses.sum()))
        pf = float(wins.sum() / gross_loss) if gross_loss > 0 else np.inf
        symbol_share = float(group["symbol"].value_counts(normalize=True).max()) if "symbol" in group else 1.0
        exchange_share = float(group["exchange"].value_counts(normalize=True).max()) if "exchange" in group else 1.0
        positive_window_rate = float((windows["avg_net_r"] > 0).mean())
        median_target_r = float(group["target_r"].median()) if "target_r" in group.columns else np.nan
        median_risk_pct = float(group["risk_pct"].median()) if "risk_pct" in group.columns else np.nan
        passed = (
            len(group) >= cfg.min_events
            and len(windows) >= cfg.min_windows
            and pf >= cfg.min_pf
            and float(net.mean()) >= cfg.min_avg_net_r
            and float(windows["avg_net_r"].median()) >= cfg.min_median_window_r
            and positive_window_rate >= cfg.min_positive_window_rate
            and max(symbol_share, exchange_share) <= cfg.max_concentration
            and (not np.isfinite(median_target_r) or median_target_r >= cfg.min_median_target_r)
            and (not np.isfinite(median_risk_pct) or median_risk_pct >= cfg.min_median_risk_pct)
        )
        rows.append({
            **dict(zip(bucket_cols, keys)),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()) if "symbol" in group else 0,
            "exchanges": int(group["exchange"].nunique()) if "exchange" in group else 0,
            "avg_net_r": float(net.mean()),
            "median_net_r": float(net.median()),
            "profit_factor": pf,
            "windows": int(len(windows)),
            "positive_window_rate": positive_window_rate,
            "median_window_avg_r": float(windows["avg_net_r"].median()),
            "worst_window_avg_r": float(windows["avg_net_r"].min()),
            "best_window_avg_r": float(windows["avg_net_r"].max()),
            "median_window_events": int(windows["events"].median()),
            "min_window_events": int(windows["events"].min()),
            "median_target_r": median_target_r,
            "median_risk_pct": median_risk_pct,
            "max_symbol_share": symbol_share,
            "max_exchange_share": exchange_share,
            "passed_gate": bool(passed),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["passed_gate", "avg_net_r", "positive_window_rate", "events"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def walk_forward_validate_buckets(
    events: pd.DataFrame,
    *,
    bucket_cols: list[str] | None = None,
    discovery_days: int = 30,
    holdout_days: int = 30,
    gate: ValidationGate | None = None,
) -> pd.DataFrame:
    """Select buckets on discovery, then score the same buckets on holdout.

    This is intentionally simple and harsh: a bucket is only interesting if it
    passes discovery gates and remains positive on the immediately following
    holdout period without re-optimization.
    """
    if events.empty:
        return pd.DataFrame()
    cfg = gate or ValidationGate()
    bucket_cols = bucket_cols or [c for c in DEFAULT_BUCKET_COLS if c in events.columns]
    data = _prepare_events(events, bucket_cols)
    if "target_r" in data.columns:
        data = data[data["target_r"] >= cfg.min_target_r].reset_index(drop=True)
    if data.empty:
        return pd.DataFrame()

    first = data["entry_ts"].min().normalize()
    last = data["entry_ts"].max().normalize()
    rows: list[dict] = []
    start = first
    fold = 0
    while start + pd.Timedelta(days=discovery_days + holdout_days) <= last + pd.Timedelta(days=1):
        discovery_end = start + pd.Timedelta(days=discovery_days)
        holdout_end = discovery_end + pd.Timedelta(days=holdout_days)
        discovery = data[(data["entry_ts"] >= start) & (data["entry_ts"] < discovery_end)]
        holdout = data[(data["entry_ts"] >= discovery_end) & (data["entry_ts"] < holdout_end)]
        if discovery.empty or holdout.empty:
            start += pd.Timedelta(days=holdout_days)
            fold += 1
            continue

        selected = validate_event_buckets(
            discovery,
            bucket_cols=bucket_cols,
            window_days=max(7, min(14, discovery_days // 2)),
            step_days=max(3, min(7, discovery_days // 4)),
            gate=cfg,
        )
        selected = selected[selected["passed_gate"]]
        for _, bucket in selected.iterrows():
            mask = pd.Series(True, index=holdout.index)
            for col in bucket_cols:
                mask &= holdout[col].astype(str) == str(bucket[col])
            h = holdout[mask]
            if h.empty:
                holdout_stats = _empty_stats()
            else:
                holdout_stats = _bucket_stats(h)
            passed_holdout = (
                holdout_stats["events"] >= max(20, cfg.min_events // 4)
                and holdout_stats["profit_factor"] >= 1.0
                and holdout_stats["avg_net_r"] > 0
                and holdout_stats["median_net_r"] >= -0.25
            )
            rows.append({
                "fold": fold,
                "discovery_start": start,
                "discovery_end": discovery_end,
                "holdout_start": discovery_end,
                "holdout_end": holdout_end,
                **{col: bucket[col] for col in bucket_cols},
                "discovery_events": int(bucket["events"]),
                "discovery_avg_net_r": float(bucket["avg_net_r"]),
                "discovery_pf": float(bucket["profit_factor"]),
                "discovery_positive_window_rate": float(bucket["positive_window_rate"]),
                "holdout_events": int(holdout_stats["events"]),
                "holdout_avg_net_r": float(holdout_stats["avg_net_r"]),
                "holdout_median_net_r": float(holdout_stats["median_net_r"]),
                "holdout_pf": float(holdout_stats["profit_factor"]),
                "holdout_symbols": int(holdout_stats["symbols"]),
                "holdout_exchanges": int(holdout_stats["exchanges"]),
                "passed_holdout": bool(passed_holdout),
            })
        start += pd.Timedelta(days=holdout_days)
        fold += 1
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["passed_holdout", "holdout_avg_net_r", "discovery_avg_net_r"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _rolling_windows(group: pd.DataFrame, *, window_days: int, step_days: int) -> pd.DataFrame:
    g = group.sort_values("entry_ts").reset_index(drop=True)
    if g.empty:
        return pd.DataFrame()
    first = g["entry_ts"].min().normalize()
    last = g["entry_ts"].max().normalize()
    rows: list[dict] = []
    start = first
    while start + pd.Timedelta(days=window_days) <= last:
        end = start + pd.Timedelta(days=window_days)
        w = g[(g["entry_ts"] >= start) & (g["entry_ts"] < end)]
        if not w.empty:
            net = w["net_r"].astype(float)
            wins = net[net > 0]
            losses = net[net < 0]
            gross_loss = abs(float(losses.sum()))
            pf = float(wins.sum() / gross_loss) if gross_loss > 0 else np.inf
            rows.append({
                "start": start,
                "end": end,
                "events": int(len(w)),
                "avg_net_r": float(net.mean()),
                "median_net_r": float(net.median()),
                "profit_factor": pf,
            })
        start += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def _bucket_stats(group: pd.DataFrame) -> dict:
    net = group["net_r"].astype(float)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_loss = abs(float(losses.sum()))
    pf = float(wins.sum() / gross_loss) if gross_loss > 0 else np.inf
    return {
        "events": int(len(group)),
        "symbols": int(group["symbol"].nunique()) if "symbol" in group else 0,
        "exchanges": int(group["exchange"].nunique()) if "exchange" in group else 0,
        "avg_net_r": float(net.mean()) if len(net) else 0.0,
        "median_net_r": float(net.median()) if len(net) else 0.0,
        "profit_factor": pf,
    }


def _empty_stats() -> dict:
    return {
        "events": 0,
        "symbols": 0,
        "exchanges": 0,
        "avg_net_r": 0.0,
        "median_net_r": 0.0,
        "profit_factor": 0.0,
    }


def _prepare_events(events: pd.DataFrame, bucket_cols: list[str]) -> pd.DataFrame:
    required = {"entry_ts", "net_r", *bucket_cols}
    missing = [c for c in required if c not in events.columns]
    if missing:
        raise ValueError(f"events missing required columns: {missing}")
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data["net_r"] = pd.to_numeric(data["net_r"], errors="coerce")
    if "target_r" in data.columns:
        data["target_r"] = pd.to_numeric(data["target_r"], errors="coerce")
    if "risk_price" in data.columns and "entry" in data.columns:
        data["risk_price"] = pd.to_numeric(data["risk_price"], errors="coerce")
        data["entry"] = pd.to_numeric(data["entry"], errors="coerce")
        data["risk_pct"] = data["risk_price"] / data["entry"].abs()
    for col in bucket_cols:
        data[col] = data[col].fillna("unknown")
    return data.dropna(subset=["entry_ts", "net_r"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate crypto event-atlas buckets across rolling windows.")
    parser.add_argument("--events", default="backtesting/results/event_atlas/crypto_event_atlas.csv")
    parser.add_argument("--output", default="backtesting/results/event_atlas/crypto_event_bucket_validation.csv")
    parser.add_argument("--walk-forward-output", default="")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--step-days", type=int, default=7)
    parser.add_argument("--min-events", type=int, default=100)
    parser.add_argument("--min-windows", type=int, default=4)
    parser.add_argument("--min-pf", type=float, default=1.20)
    parser.add_argument("--min-avg-r", type=float, default=0.05)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.55)
    parser.add_argument("--min-target-r", type=float, default=1.5)
    parser.add_argument("--min-median-target-r", type=float, default=1.8)
    parser.add_argument("--min-median-risk-pct", type=float, default=0.0015)
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--discovery-days", type=int, default=30)
    parser.add_argument("--holdout-days", type=int, default=30)
    args = parser.parse_args()

    events_path = Path(args.events)
    if not events_path.exists():
        raise SystemExit(f"events file not found: {events_path}")
    events = pd.read_csv(events_path)
    result = validate_event_buckets(
        events,
        window_days=args.window_days,
        step_days=args.step_days,
        gate=ValidationGate(
            min_events=args.min_events,
            min_windows=args.min_windows,
            min_pf=args.min_pf,
            min_avg_net_r=args.min_avg_r,
            min_positive_window_rate=args.min_positive_window_rate,
            min_target_r=args.min_target_r,
            min_median_target_r=args.min_median_target_r,
            min_median_risk_pct=args.min_median_risk_pct,
        ),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(f"Validated buckets: {len(result)}")
    if not result.empty:
        print(result.head(30).to_string(index=False))
    print(f"Saved to {out}")
    if args.walk_forward:
        wf = walk_forward_validate_buckets(
            events,
            discovery_days=args.discovery_days,
            holdout_days=args.holdout_days,
            gate=ValidationGate(
                min_events=args.min_events,
                min_windows=args.min_windows,
                min_pf=args.min_pf,
                min_avg_net_r=args.min_avg_r,
                min_positive_window_rate=args.min_positive_window_rate,
                min_target_r=args.min_target_r,
                min_median_target_r=args.min_median_target_r,
                min_median_risk_pct=args.min_median_risk_pct,
            ),
        )
        wf_out = Path(args.walk_forward_output or str(out).replace(".csv", "_walk_forward.csv"))
        wf.to_csv(wf_out, index=False)
        print(f"Walk-forward rows: {len(wf)}")
        if not wf.empty:
            print(wf.head(30).to_string(index=False))
        print(f"Walk-forward saved to {wf_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

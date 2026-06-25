#!/usr/bin/env python3
"""No-lookahead crypto structure pullback lab.

Uses cached structure indexes from data/features/structure and runs a small,
repeatable futures challenge matrix. This is research code: if it overtrades or
fails costs, the idea dies instead of being promoted into production strategy.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.crypto_reports import BacktestContext, build_report_tables
from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.runner import run


FEATURE_ROOT = ROOT / "data" / "features" / "structure" / "L2_R2"
RESULT_ROOT = ROOT / "backtesting" / "results"
CORE_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT")
EXCHANGES = ("binance", "bybit")


@dataclass(frozen=True)
class PullbackConfig:
    entry_tf: str = "5"
    structure_tf: str = "30"
    htf_tf: str = "240"
    rr: float = 2.0
    risk_pct: float = 0.02
    max_stop_pct: float = 0.012
    min_stop_pct: float = 0.001
    pullback_ema: int = 20
    trend_ema: int = 50
    max_trades_per_leg: int = 1
    warmup_days: int = 10


class StructurePullbackV1(Strategy):
    """First pullback after confirmed 30m structure impulse."""

    def __init__(self, cfg: PullbackConfig):
        self.cfg = cfg
        self.df: pd.DataFrame | None = None
        self.traded_by_leg: dict[int, int] = {}

    def init(self, data: dict[str, object]) -> None:
        self.df = data[self.cfg.entry_tf].reset_index(drop=True)
        self.traded_by_leg = {}

    def next(self, bar: BarData, state: EngineState) -> Signal | None:
        if self.df is None or bar.index < max(self.cfg.trend_ema + 2, 3):
            return None
        if state.has_open_position:
            return None

        row = self.df.iloc[bar.index]
        prev = self.df.iloc[bar.index - 1]
        prev2 = self.df.iloc[bar.index - 2]
        if not bool(row.get("can_trade", False)):
            return None

        leg_id = int(prev.get("struct_leg_id", 0) or 0)
        leg_dir = int(prev.get("struct_leg_dir", 0) or 0)
        if leg_id <= 0 or leg_dir == 0:
            return None
        if self.traded_by_leg.get(leg_id, 0) >= self.cfg.max_trades_per_leg:
            return None

        if leg_dir > 0 and self._long_setup(prev, prev2):
            signal = self._build_signal(Direction.LONG, bar.open, prev, leg_id)
        elif leg_dir < 0 and self._short_setup(prev, prev2):
            signal = self._build_signal(Direction.SHORT, bar.open, prev, leg_id)
        else:
            return None

        if signal is not None:
            self.traded_by_leg[leg_id] = self.traded_by_leg.get(leg_id, 0) + 1
        return signal

    def _long_setup(self, prev: pd.Series, prev2: pd.Series) -> bool:
        return (
            prev.get("struct_regime") == "bull"
            and prev.get("htf_regime") != "bear"
            and prev["close"] > prev["ema20"]
            and prev["ema20"] > prev["ema50"]
            and prev["close_30"] > prev["ema50_30"]
            and prev["close_240"] > prev["ema50_240"]
            and (prev2["close"] <= prev2["ema20"] or prev2["low"] <= prev2["ema20"] * 1.001)
            and prev["close"] > prev["open"]
        )

    def _short_setup(self, prev: pd.Series, prev2: pd.Series) -> bool:
        return (
            prev.get("struct_regime") == "bear"
            and prev.get("htf_regime") != "bull"
            and prev["close"] < prev["ema20"]
            and prev["ema20"] < prev["ema50"]
            and prev["close_30"] < prev["ema50_30"]
            and prev["close_240"] < prev["ema50_240"]
            and (prev2["close"] >= prev2["ema20"] or prev2["high"] >= prev2["ema20"] * 0.999)
            and prev["close"] < prev["open"]
        )

    def _build_signal(
        self,
        direction: Direction,
        entry: float,
        prev: pd.Series,
        leg_id: int,
    ) -> Signal | None:
        if not np.isfinite(entry) or entry <= 0:
            return None

        if direction == Direction.LONG:
            struct_sl = float(prev.get("struct_long_sl", np.nan))
            fallback_sl = float(prev.get("rolling_low_12", np.nan))
            raw_sl = struct_sl if np.isfinite(struct_sl) and struct_sl < entry else fallback_sl
            if not np.isfinite(raw_sl) or raw_sl >= entry:
                return None
            sl = max(raw_sl, entry * (1.0 - self.cfg.max_stop_pct))
            stop_pct = (entry - sl) / entry
            tp1 = entry + self.cfg.rr * (entry - sl)
        else:
            struct_sl = float(prev.get("struct_short_sl", np.nan))
            fallback_sl = float(prev.get("rolling_high_12", np.nan))
            raw_sl = struct_sl if np.isfinite(struct_sl) and struct_sl > entry else fallback_sl
            if not np.isfinite(raw_sl) or raw_sl <= entry:
                return None
            sl = min(raw_sl, entry * (1.0 + self.cfg.max_stop_pct))
            stop_pct = (sl - entry) / entry
            tp1 = entry - self.cfg.rr * (sl - entry)

        if stop_pct < self.cfg.min_stop_pct or stop_pct > self.cfg.max_stop_pct:
            return None

        return Signal(
            direction=direction,
            entry=entry,
            sl=sl,
            tp1=tp1,
            risk_pct=self.cfg.risk_pct,
            tp1_frac=1.0,
            tp2_frac=0.0,
            trail=False,
            label=f"struct_pullback_v1 leg={leg_id} rr={self.cfg.rr}",
        )


def load_structure(exchange: str, symbol: str, tf: str) -> pd.DataFrame:
    path = FEATURE_ROOT / exchange / symbol / f"{tf}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing structure index: {path}")
    df = pd.read_parquet(path)
    df["known_after_ts"] = pd.to_datetime(df["known_after_ts"], utc=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.sort_values("known_after_ts").reset_index(drop=True)


def prepare_structure_context(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = df.copy()
    event_dir = np.select(
        [out["bos_up"] | out["choch_up"], out["bos_down"] | out["choch_down"]],
        [1, -1],
        default=0,
    )
    out[f"{name}_event_dir"] = event_dir
    out[f"{name}_leg_id"] = (event_dir != 0).cumsum()
    out[f"{name}_leg_dir"] = pd.Series(event_dir).replace(0, np.nan).ffill().fillna(0).astype(int)
    keep = [
        "known_after_ts",
        "regime",
        "long_structural_sl",
        "short_structural_sl",
        "long_target_1",
        "short_target_1",
        f"{name}_event_dir",
        f"{name}_leg_id",
        f"{name}_leg_dir",
    ]
    keep = [c for c in keep if c in out.columns]
    out = out[keep].copy()
    rename = {
        "regime": f"{name}_regime",
        "long_structural_sl": f"{name}_long_sl",
        "short_structural_sl": f"{name}_short_sl",
        "long_target_1": f"{name}_long_target",
        "short_target_1": f"{name}_short_target",
    }
    return out.rename(columns=rename)


def prepare_ohlcv_context(exchange: str, symbol: str, tf: str, days: int, cfg: PullbackConfig, prefix: str) -> pd.DataFrame:
    df = load_data(symbol, tf=tf, days=days + cfg.warmup_days, asset_type="crypto", exchange=exchange)
    if df.empty:
        raise FileNotFoundError(f"missing candles: {exchange} {symbol} {tf}")
    df = df.sort_values("ts").reset_index(drop=True)
    df[f"ema20_{prefix}"] = df["close"].ewm(span=cfg.pullback_ema, adjust=False).mean()
    df[f"ema50_{prefix}"] = df["close"].ewm(span=cfg.trend_ema, adjust=False).mean()
    return df[["ts", "close", f"ema20_{prefix}", f"ema50_{prefix}"]].rename(
        columns={"ts": f"ts_{prefix}", "close": f"close_{prefix}"}
    )


def prepare_entry_data(exchange: str, symbol: str, days: int, cfg: PullbackConfig) -> pd.DataFrame:
    entry = load_data(
        symbol,
        tf=cfg.entry_tf,
        days=days + cfg.warmup_days,
        asset_type="crypto",
        exchange=exchange,
    )
    if entry.empty:
        raise FileNotFoundError(f"missing entry candles: {exchange} {symbol} {cfg.entry_tf}")
    entry = entry.sort_values("ts").reset_index(drop=True)
    entry["ema20"] = entry["close"].ewm(span=cfg.pullback_ema, adjust=False).mean()
    entry["ema50"] = entry["close"].ewm(span=cfg.trend_ema, adjust=False).mean()
    entry["rolling_low_12"] = entry["low"].rolling(12).min().shift(1)
    entry["rolling_high_12"] = entry["high"].rolling(12).max().shift(1)

    struct_30 = prepare_structure_context(load_structure(exchange, symbol, cfg.structure_tf), "struct")
    struct_240 = prepare_structure_context(load_structure(exchange, symbol, cfg.htf_tf), "htf")
    ctx_30 = prepare_ohlcv_context(exchange, symbol, cfg.structure_tf, days, cfg, "30")
    ctx_240 = prepare_ohlcv_context(exchange, symbol, cfg.htf_tf, days, cfg, "240")

    merged = pd.merge_asof(
        entry.sort_values("ts"),
        struct_30,
        left_on="ts",
        right_on="known_after_ts",
        direction="backward",
    ).drop(columns=["known_after_ts"], errors="ignore")
    merged = pd.merge_asof(
        merged.sort_values("ts"),
        struct_240,
        left_on="ts",
        right_on="known_after_ts",
        direction="backward",
    ).drop(columns=["known_after_ts"], errors="ignore")
    merged = pd.merge_asof(
        merged.sort_values("ts"),
        ctx_30.sort_values("ts_30"),
        left_on="ts",
        right_on="ts_30",
        direction="backward",
    )
    merged = pd.merge_asof(
        merged.sort_values("ts"),
        ctx_240.sort_values("ts_240"),
        left_on="ts",
        right_on="ts_240",
        direction="backward",
    )

    end_ts = merged["ts"].max()
    start_trade_ts = end_ts - pd.Timedelta(days=days)
    merged["can_trade"] = merged["ts"] >= start_trade_ts
    return merged.reset_index(drop=True)


def load_costs(exchange: str, symbol: str, leverage: float) -> CryptoCosts:
    specs_path = ROOT / "data" / "market_data" / "crypto" / exchange / "market_specs.parquet"
    kwargs = {}
    if specs_path.exists():
        specs = pd.read_parquet(specs_path)
        row = specs[(specs["symbol"] == symbol) | (specs["id"] == symbol)]
        if not row.empty:
            rec = row.iloc[0]
            amount_precision = rec.get("amount_precision")
            price_precision = rec.get("price_precision")
            kwargs["min_qty"] = float(rec.get("min_qty") or 0.0)
            kwargs["min_notional"] = float(rec.get("min_notional") or 0.0)
            if pd.notna(amount_precision):
                kwargs["qty_step"] = float(amount_precision)
            if pd.notna(price_precision):
                kwargs["tick_size"] = float(price_precision)

    funding = load_funding_rate(symbol, exchange=exchange)
    return CryptoCosts(leverage=leverage, funding_df=funding, **kwargs)


def run_case(exchange: str, symbol: str, days: int, cfg: PullbackConfig, leverage: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = {cfg.entry_tf: prepare_entry_data(exchange, symbol, days, cfg)}
    result = run(
        StructurePullbackV1(cfg),
        data,
        entry_tf=cfg.entry_tf,
        costs=load_costs(exchange, symbol, leverage),
        initial_equity=20.0,
        max_open_positions=1,
    )
    context = BacktestContext(
        strategy="crypto_structure_pullback_v1",
        symbol=symbol,
        exchange=exchange,
        timeframe=cfg.entry_tf,
        duration_days=days,
    )
    summary, trades = build_report_tables(result, context, windows=(30, 60, 90))
    summary["rr_target"] = cfg.rr
    summary["risk_pct"] = cfg.risk_pct
    summary["leverage"] = leverage
    summary["max_stop_pct"] = cfg.max_stop_pct
    if not trades.empty:
        trades["duration_days"] = days
        trades["rr_target"] = cfg.rr
        trades["risk_pct"] = cfg.risk_pct
        trades["leverage"] = leverage
    return summary, trades


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(CORE_SYMBOLS))
    parser.add_argument("--exchanges", default=",".join(EXCHANGES))
    parser.add_argument("--windows", default="30,60,90")
    parser.add_argument("--entry-tf", default="5")
    parser.add_argument("--rr", type=float, default=2.0)
    parser.add_argument("--risk-pct", type=float, default=0.02)
    parser.add_argument("--max-stop-pct", type=float, default=0.012)
    parser.add_argument("--leverage", type=float, default=50.0)
    parser.add_argument("--out-prefix", default="crypto_structure_pullback_v1")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg = PullbackConfig(
        entry_tf=args.entry_tf,
        rr=args.rr,
        risk_pct=args.risk_pct,
        max_stop_pct=args.max_stop_pct,
    )
    symbols = parse_csv(args.symbols)
    exchanges = parse_csv(args.exchanges)
    windows = [int(x) for x in parse_csv(args.windows)]

    summaries = []
    trades = []
    for exchange in exchanges:
        for symbol in symbols:
            for days in windows:
                try:
                    summary, trade_df = run_case(exchange, symbol, days, cfg, args.leverage)
                except Exception as exc:
                    summaries.append(pd.DataFrame([{
                        "strategy": "crypto_structure_pullback_v1",
                        "exchange": exchange,
                        "symbol": symbol,
                        "timeframe": cfg.entry_tf,
                        "duration_days": days,
                        "window_days": days,
                        "error": str(exc),
                    }]))
                    continue
                summaries.append(summary[summary["window_days"] == days].copy())
                if not trade_df.empty:
                    trades.append(trade_df)
                print(
                    f"{exchange} {symbol} {days}d: "
                    f"trades={int(summary.loc[summary['window_days'].eq(days), 'trades'].iloc[0])} "
                    f"pnl={float(summary.loc[summary['window_days'].eq(days), 'pnl'].iloc[0]):.2f} "
                    f"dd={float(summary.loc[summary['window_days'].eq(days), 'max_dd_pct'].iloc[0]):.1%}"
                )

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    summary_out = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    trades_out = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    summary_path = RESULT_ROOT / f"{args.out_prefix}_summary.csv"
    trades_path = RESULT_ROOT / f"{args.out_prefix}_trades.csv"
    summary_out.to_csv(summary_path, index=False)
    trades_out.to_csv(trades_path, index=False)
    print(f"wrote {summary_path}")
    print(f"wrote {trades_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

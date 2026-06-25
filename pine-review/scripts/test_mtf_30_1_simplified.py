"""
Simplified 30m/1m MTF strategy:
- 30m bias from structure breaks + premium/discount context
- 1m entries on OB/FVG reaction
- TP at pivot liquidity (swings), fallback to 50% FVG midpoint
- Exits: TP, SL, or time-based only (no opposite-signal exits)
"""
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

import pandas as pd

# Add backend root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure
from src.features.technicals import calculate_all_technicals


@dataclass
class EntryZone:
    zone_type: str
    top: float
    bottom: float
    source_index: int


def latest_break_direction(structure_30m: Dict, df_30m: pd.DataFrame, idx_30m: int) -> str:
    """Return bullish/bearish/neutral based on latest 30m structure break up to idx."""
    latest = None
    for brk in structure_30m["structure_breaks"]:
        if brk.index <= idx_30m:
            latest = brk
        else:
            break
    if latest is None:
        trend = structure_30m.get("current_trend", "neutral")
        if trend in ("bullish", "bearish"):
            return trend
        # Fallback directional bias when no break exists in recent sample.
        if idx_30m >= 50:
            ema = df_30m["close"].ewm(span=50, adjust=False).mean().iloc[idx_30m]
            return "bullish" if df_30m["close"].iloc[idx_30m] >= ema else "bearish"
        return "neutral"
    return latest.direction


def premium_discount_allows_trade(
    structure_30m: Dict, idx_30m: int, price: float, direction: str
) -> bool:
    """Require longs in discount half and shorts in premium half."""
    latest_zone = None
    for zone in structure_30m.get("premium_discount_zones", []):
        if zone.end_index <= idx_30m:
            latest_zone = zone
        else:
            break
    if latest_zone is None:
        return True
    if direction == "bullish":
        return price <= latest_zone.equilibrium
    return price >= latest_zone.equilibrium


def find_entry_zone_1m(
    df_1m: pd.DataFrame, structure_1m: Dict, i: int, direction: str, lookback: int = 900
) -> Optional[EntryZone]:
    """
    Find active 1m OB/FVG reaction zone in trade direction.
    Uses only zones created before current index.
    """
    bar = df_1m.iloc[i]
    zones: List[EntryZone] = []

    min_idx = max(0, i - lookback)

    if direction == "bullish":
        for fvg in structure_1m["fvgs"]:
            if fvg.index < min_idx:
                continue
            if fvg.type == "bullish" and fvg.index < i and bar["low"] <= fvg.top and bar["high"] >= fvg.bottom:
                zones.append(EntryZone("fvg", fvg.top, fvg.bottom, fvg.index))
        for ob in structure_1m["order_blocks"]:
            if ob.index < min_idx:
                continue
            if ob.type == "bullish" and ob.index < i and bar["low"] <= ob.top and bar["high"] >= ob.bottom:
                zones.append(EntryZone("ob", ob.top, ob.bottom, ob.index))
    else:
        for fvg in structure_1m["fvgs"]:
            if fvg.index < min_idx:
                continue
            if fvg.type == "bearish" and fvg.index < i and bar["high"] >= fvg.bottom and bar["low"] <= fvg.top:
                zones.append(EntryZone("fvg", fvg.top, fvg.bottom, fvg.index))
        for ob in structure_1m["order_blocks"]:
            if ob.index < min_idx:
                continue
            if ob.type == "bearish" and ob.index < i and bar["high"] >= ob.bottom and bar["low"] <= ob.top:
                zones.append(EntryZone("ob", ob.top, ob.bottom, ob.index))

    if not zones:
        return None

    price = bar["close"]
    zones.sort(key=lambda z: abs(((z.top + z.bottom) / 2) - price))
    return zones[0]


def find_tp_from_liquidity_or_fvg_mid(
    structure_1m: Dict, i: int, entry_price: float, direction: str, lookback: int = 1500
) -> Tuple[Optional[float], Optional[str]]:
    """Pivot liquidity target first, fallback to nearest 50% FVG midpoint."""
    min_idx = max(0, i - lookback)

    if direction == "bullish":
        highs = [s.price for s in structure_1m["swing_highs"] if min_idx <= s.index < i and s.price > entry_price]
        if highs:
            return min(highs), "pivot_high_liquidity"
        mids = [((f.top + f.bottom) / 2) for f in structure_1m["fvgs"] if min_idx <= f.index < i and ((f.top + f.bottom) / 2) > entry_price]
        if mids:
            return min(mids), "fvg_50_mid"
    else:
        lows = [s.price for s in structure_1m["swing_lows"] if min_idx <= s.index < i and s.price < entry_price]
        if lows:
            return max(lows), "pivot_low_liquidity"
        mids = [((f.top + f.bottom) / 2) for f in structure_1m["fvgs"] if min_idx <= f.index < i and ((f.top + f.bottom) / 2) < entry_price]
        if mids:
            return max(mids), "fvg_50_mid"
    return None, None


def run_single_symbol(
    symbol: str,
    min_rr: float = 1.2,
    risk_per_trade: float = 0.01,
    max_bars_in_trade: int = 180,
    limit_1m: int = 3000,
    limit_30m: int = 2000,
    cooldown_bars: int = 5,
    use_premium_discount_filter: bool = False,
) -> Dict:
    loader = DataLoader()

    df_1m = loader.load(symbol, "1", limit=limit_1m, prefer_parquet=True).copy()
    df_30m = loader.load(symbol, "30", limit=limit_30m, prefer_parquet=True).copy()
    df_1m = calculate_all_technicals(df_1m, normalize=False)

    structure_1m = analyze_market_structure(df_1m, volume_filter=False)
    structure_30m = analyze_market_structure(df_30m, volume_filter=False)

    engine = BacktestEngine(
        initial_capital=20000.0,
        commission=0.001,
        risk_per_trade=risk_per_trade,
        position_sizing="risk_pct",
        slippage=0.0002,
    )

    htf_index = df_30m.index
    trade_meta: List[Dict] = []
    open_meta: Optional[Dict] = None
    last_exit_i = -cooldown_bars - 1
    prev_closed_count = 0

    for i in range(len(df_1m)):
        now = df_1m.index[i]
        bar = df_1m.iloc[i]

        engine.update(now, bar["high"], bar["low"], bar["close"])
        if len(engine.closed_trades) > prev_closed_count:
            prev_closed_count = len(engine.closed_trades)
            if open_meta is not None:
                t = engine.closed_trades[-1]
                open_meta["exit_reason"] = t.exit_reason
                open_meta["pnl_pct"] = t.pnl_pct
                trade_meta.append(open_meta)
                open_meta = None
                last_exit_i = i

        if engine.current_trade is not None and open_meta is not None:
            bars_open = i - open_meta["entry_idx"]
            if bars_open >= max_bars_in_trade:
                engine.close_trade(now, bar["close"], "time_exit")
                prev_closed_count = len(engine.closed_trades)
                t = engine.closed_trades[-1]
                open_meta["exit_reason"] = t.exit_reason
                open_meta["pnl_pct"] = t.pnl_pct
                trade_meta.append(open_meta)
                open_meta = None
                last_exit_i = i
            continue

        if i - last_exit_i <= cooldown_bars:
            continue
        if i < 50 or pd.isna(bar.get("atr", float("nan"))):
            continue

        idx_30m = htf_index.searchsorted(now, side="right") - 1
        if idx_30m < 20:
            continue

        bias = latest_break_direction(structure_30m, df_30m, idx_30m)
        if bias not in ("bullish", "bearish"):
            continue
        if use_premium_discount_filter and not premium_discount_allows_trade(structure_30m, idx_30m, bar["close"], bias):
            continue

        zone = find_entry_zone_1m(df_1m, structure_1m, i, bias)
        if zone is None:
            continue

        tp, tp_source = find_tp_from_liquidity_or_fvg_mid(structure_1m, i, bar["close"], bias)
        if tp is None:
            continue

        atr = float(bar["atr"])
        if bias == "bullish":
            sl = zone.bottom - atr * 0.4
            direction = "long"
            risk = bar["close"] - sl
            reward = tp - bar["close"]
        else:
            sl = zone.top + atr * 0.4
            direction = "short"
            risk = sl - bar["close"]
            reward = bar["close"] - tp

        if risk <= 0 or reward <= 0:
            continue
        planned_rr = reward / risk
        if planned_rr < min_rr:
            continue

        engine.open_trade(
            time=now,
            price=float(bar["close"]),
            direction=direction,
            stop_loss=float(sl),
            take_profit=float(tp),
        )
        open_meta = {
            "entry_idx": i,
            "entry_time": now,
            "direction": direction,
            "entry_zone": zone.zone_type,
            "tp_source": tp_source,
            "planned_rr": planned_rr,
        }

    if engine.current_trade is not None and open_meta is not None:
        engine.close_trade(df_1m.index[-1], float(df_1m["close"].iloc[-1]), "end_of_data")
        t = engine.closed_trades[-1]
        open_meta["exit_reason"] = t.exit_reason
        open_meta["pnl_pct"] = t.pnl_pct
        trade_meta.append(open_meta)

    result = engine.run(df_1m.iloc[:0], lambda e, d, i: None) if False else None
    _ = result  # keep linter quiet in local editors

    summary = {
        "symbol": symbol,
        "trades": len(engine.closed_trades),
        "win_rate": 0.0,
        "total_return_pct": ((engine.capital - engine.initial_capital) / engine.initial_capital) * 100,
        "max_drawdown": 0.0,
        "avg_rr_realized": 0.0,
        "avg_rr_planned": 0.0,
        "exit_reasons": {},
    }

    if engine.equity_curve:
        eq = pd.Series([x[1] for x in engine.equity_curve], index=[x[0] for x in engine.equity_curve])
        peak = eq.cummax()
        dd = ((eq - peak) / peak * 100).min()
        summary["max_drawdown"] = abs(float(dd))

    if engine.closed_trades:
        winners = [t for t in engine.closed_trades if t.pnl is not None and t.pnl > 0]
        summary["win_rate"] = len(winners) / len(engine.closed_trades) * 100

        rr_vals = []
        for t in engine.closed_trades:
            if t.pnl is None or t.stop_loss is None:
                continue
            if t.direction == "long":
                unit_risk = t.entry_price - t.stop_loss
            else:
                unit_risk = t.stop_loss - t.entry_price
            if unit_risk > 0:
                rr_vals.append(abs((t.pnl / t.size) / unit_risk))
        if rr_vals:
            summary["avg_rr_realized"] = float(pd.Series(rr_vals).mean())

        meta_df = pd.DataFrame(trade_meta)
        if not meta_df.empty and "planned_rr" in meta_df.columns:
            summary["avg_rr_planned"] = float(meta_df["planned_rr"].mean())
        if not meta_df.empty and "exit_reason" in meta_df.columns:
            summary["exit_reasons"] = meta_df["exit_reason"].value_counts().to_dict()

    return summary


def run_market_suite() -> pd.DataFrame:
    symbols = [
        "BTCUSD",
        "ETHUSD",
        "EURUSD",
        "GBPUSD",
        "XAUUSD",
        "USA500IDXUSD",
    ]
    rows = []
    for sym in symbols:
        try:
            rows.append(run_single_symbol(sym))
        except Exception as exc:
            rows.append(
                {
                    "symbol": sym,
                    "trades": 0,
                    "win_rate": 0.0,
                    "total_return_pct": 0.0,
                    "max_drawdown": 0.0,
                    "avg_rr_realized": 0.0,
                    "avg_rr_planned": 0.0,
                    "exit_reasons": {"error": str(exc)},
                }
            )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Test simplified 30m/1m MTF strategy.")
    parser.add_argument("--symbol", type=str, default=None, help="Single symbol, e.g. BTCUSD")
    parser.add_argument("--limit", type=int, default=3000, help="Number of 1m bars to load")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("SIMPLIFIED 30m/1m MTF STRATEGY (OB/FVG ENTRIES, LIQUIDITY TP)")
    print("=" * 70)

    if args.symbol:
        result = run_single_symbol(args.symbol, limit_1m=args.limit)
        print(pd.DataFrame([result]).to_string(index=False))
    else:
        results = run_market_suite()
        print(results[["symbol", "trades", "win_rate", "avg_rr_planned", "avg_rr_realized", "total_return_pct", "max_drawdown"]].to_string(index=False))
        print("\nExit reason snapshots:")
        for _, row in results.iterrows():
            print(f"  {row['symbol']}: {row['exit_reasons']}")


if __name__ == "__main__":
    main()

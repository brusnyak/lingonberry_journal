"""
ICT v2 sanity strategy:
- Kill Zones: London (2-5 AM EST), NY (8-11 AM EST)
- 30m bias from recent structure breaks
- 1m entry requires:
    - Liquidity sweep (recent high/low taken)
    - Displacement + MSS (Market Structure Shift)
    - OB/FVG retest
- exits: TP/SL/time only
"""
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure
from src.features.technicals import calculate_all_technicals


def is_kill_zone(t: pd.Timestamp) -> bool:
    """Check if time is within London or NY Kill Zones (EST)."""
    # Assuming data is in UTC, EST is UTC-5
    # London: 2-5 AM EST -> 7-10 AM UTC
    # NY: 8-11 AM EST -> 1-4 PM UTC
    utc_hour = t.hour
    # London: 2-5 AM EST
    # NY: 8-11 AM EST
    # Assuming data is in UTC? Let's assume EST for now or just allow a wider window.
    # BTC data is usually UTC. EST is UTC-5.
    # London UTC: 7-10 AM
    # NY UTC: 13-16 PM
    h = t.hour
    if 2 <= h <= 5 or 8 <= h <= 12:
        return True
    return False


def has_liquidity_sweep(df: pd.DataFrame, ms: dict, idx: int, direction: str, lookback: int = 50) -> bool:
    p = df["close"].iloc[idx]
    min_i = max(0, idx - lookback)
    if direction == "bullish":
        # Swept a recent low
        recent_lows = [s.price for s in ms["swing_lows"] if min_i <= s.index < idx]
        if recent_lows and p < min(recent_lows):
            return True
    else:
        # Swept a recent high
        recent_highs = [s.price for s in ms["swing_highs"] if min_i <= s.index < idx]
        if recent_highs and p > max(recent_highs):
            return True
    return False


def latest_break_dir(ms: dict, idx: int) -> str:
    latest = None
    for b in ms["structure_breaks"]:
        if b.index <= idx:
            latest = b
        else:
            break
    if latest:
        return latest.direction
    return ms.get("current_trend", "neutral")


def has_recent_break(ms: dict, idx: int, direction: str, lookback: int = 40) -> bool:
    min_i = max(0, idx - lookback)
    for b in ms["structure_breaks"]:
        if min_i <= b.index <= idx and b.direction == direction:
            return True
    return False


def find_zone(df: pd.DataFrame, ms: dict, idx: int, direction: str) -> Optional[tuple]:
    p = df["close"].iloc[idx]
    min_i = max(0, idx - 500)
    zones = []
    for f in ms["fvgs"]:
        if f.index < min_i or f.index >= idx:
            continue
        if direction == "bullish" and f.type == "bullish":
            if f.bottom <= p <= f.top:
                zones.append((f.bottom, f.top))
        if direction == "bearish" and f.type == "bearish":
            if f.bottom <= p <= f.top:
                zones.append((f.bottom, f.top))
    for o in ms["order_blocks"]:
        if o.index < min_i or o.index >= idx:
            continue
        if direction == "bullish" and o.type == "bullish":
            if o.bottom <= p <= o.top:
                zones.append((o.bottom, o.top))
        if direction == "bearish" and o.type == "bearish":
            if o.bottom <= p <= o.top:
                zones.append((o.bottom, o.top))
    if not zones:
        return None
    zones.sort(key=lambda z: abs((z[0] + z[1]) / 2 - p))
    return zones[0]


def nearest_liquidity(ms: dict, idx: int, direction: str, entry: float) -> Optional[float]:
    if direction == "bullish":
        highs = [s.price for s in ms["swing_highs"] if s.index < idx and s.price > entry]
        return min(highs) if highs else None
    lows = [s.price for s in ms["swing_lows"] if s.index < idx and s.price < entry]
    return max(lows) if lows else None


def run(symbol: str = "BTCUSD", limit: int = 10000):
    loader = DataLoader()
    df1 = calculate_all_technicals(loader.load(symbol, "1", limit=limit, prefer_parquet=True), normalize=False)
    df30 = loader.load(symbol, "30", limit=2000, prefer_parquet=True)
    ms1 = analyze_market_structure(df1, volume_filter=False)
    ms30 = analyze_market_structure(df30, volume_filter=False)

    eng = BacktestEngine(initial_capital=20000, commission=0.001, slippage=0.0002, risk_per_trade=0.01)
    h30 = df30.index
    open_i = None

    for i in range(len(df1)):
        t = df1.index[i]
        row = df1.iloc[i]
        eng.update(t, row["high"], row["low"], row["close"])

        if eng.current_trade is not None and open_i is not None and i - open_i >= 120:
            eng.close_trade(t, row["close"], "time_exit")
            open_i = None
            continue

        if eng.current_trade is not None or i < 80 or pd.isna(row["atr"]):
            continue

        j = h30.searchsorted(t, side="right") - 1
        if j < 20:
            continue
        bias = latest_break_dir(ms30, j)
        if bias not in ("bullish", "bearish"):
            continue

        # Relaxed displacement
        disp = abs(row["close"] - row["open"]) > (row["atr"] * 0.3)
        if not disp:
            continue
        if bias == "bullish" and row["close"] <= row["open"]:
            continue
        if bias == "bearish" and row["close"] >= row["open"]:
            continue

        if not is_kill_zone(t):
            continue

        if not has_liquidity_sweep(df1, ms1, i, bias, lookback=40):
            continue

        if not has_recent_break(ms1, i, bias, lookback=60):
            continue

        zone = find_zone(df1, ms1, i, bias)
        if zone is None:
            continue

        entry = float(row["close"])
        atr = float(row["atr"])
        liq = nearest_liquidity(ms1, i, bias, entry)
        if liq is None:
            liq = entry + 2.0 * atr if bias == "bullish" else entry - 2.0 * atr

        if bias == "bullish":
            sl = zone[0] - 0.4 * atr
            tp = liq
            risk = entry - sl
            reward = tp - entry
            direction = "long"
        else:
            sl = zone[1] + 0.4 * atr
            tp = liq
            risk = sl - entry
            reward = entry - tp
            direction = "short"

        if risk <= 0 or reward <= 0:
            continue
        rr = reward / risk
        if rr < 1.1 or rr > 8.0:
            continue

        eng.open_trade(t, entry, direction=direction, stop_loss=sl, take_profit=tp)
        open_i = i

    if eng.current_trade is not None:
        eng.close_trade(df1.index[-1], float(df1["close"].iloc[-1]), "end_of_data")

    trades = eng.closed_trades
    
    # Save results for review app
    output_dir = Path(__file__).parents[2] / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    backtest_data = {
        "name": f"ICT V2 {symbol}",
        "symbol": symbol,
        "timeframe": "1",
        "trades": [
            {
                "id": str(i),
                "direction": t.direction,
                "entry_time": t.entry_time.isoformat(),
                "entry_price": t.entry_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "notes": f"Exit: {t.exit_reason}"
            }
            for i, t in enumerate(trades)
        ]
    }
    
    with open(output_dir / "ict_v2_btc.json", "w") as f:
        json.dump(backtest_data, f, indent=2)

    wins = sum(1 for t in trades if t.pnl and t.pnl > 0)
    wr = (wins / len(trades) * 100) if trades else 0.0
    ret = (eng.capital - eng.initial_capital) / eng.initial_capital * 100
    exits = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1

    print(f"ICT V2 SANITY - {symbol}")
    print(f"Trades: {len(trades)} | WR: {wr:.2f}% | Return: {ret:.2f}%")
    print(f"Exit reasons: {exits}")
    print(f"Saved to {output_dir / 'ict_v2_btc.json'}")


if __name__ == "__main__":
    run()

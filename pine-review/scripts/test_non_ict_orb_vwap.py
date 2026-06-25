import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date_key = out.index.date
    out["pv"] = out["close"] * out["volume"]
    out["cum_pv"] = out.groupby(date_key)["pv"].cumsum()
    out["cum_vol"] = out.groupby(date_key)["volume"].cumsum().replace(0, 1)
    out["vwap"] = out["cum_pv"] / out["cum_vol"]
    return out.drop(columns=["pv", "cum_pv", "cum_vol"])


def run(symbol: str = "BTCUSD", limit: int = 5000):
    loader = DataLoader()
    df = calculate_all_technicals(loader.load(symbol, "1", limit=limit, prefer_parquet=True), normalize=False)
    df = add_vwap(df)

    eng = BacktestEngine(initial_capital=20000, commission=0.001, slippage=0.0002, risk_per_trade=0.01)
    day_groups = df.groupby(df.index.date)
    open_idx = None

    for day, day_df in day_groups:
        day_df = day_df.copy()
        if len(day_df) < 120:
            continue
        orb = day_df.iloc[:30]
        orb_high = orb["high"].max()
        orb_low = orb["low"].min()

        for i in range(30, len(day_df)):
            t = day_df.index[i]
            row = day_df.iloc[i]
            eng.update(t, row["high"], row["low"], row["close"])

            if eng.current_trade is not None and open_idx is not None and i - open_idx >= 90:
                eng.close_trade(t, row["close"], "time_exit")
                open_idx = None
                continue

            if eng.current_trade is not None or pd.isna(row["atr"]) or row["atr"] <= 0:
                continue

            # Long breakout with VWAP alignment and volume confirmation.
            vol_avg = day_df["volume"].iloc[max(0, i-5):i].mean()
            vol_conf = row["volume"] > (vol_avg * 1.2)

            if row["close"] > orb_high and row["close"] > row["vwap"] and vol_conf:
                entry = float(row["close"])
                sl = entry - (1.2 * float(row["atr"]))
                tp = entry + (2.0 * float(row["atr"]))
                eng.open_trade(t, entry, direction="long", stop_loss=sl, take_profit=tp)
                open_idx = i
                continue

            # Short breakout with VWAP alignment and volume confirmation.
            if row["close"] < orb_low and row["close"] < row["vwap"] and vol_conf:
                entry = float(row["close"])
                sl = entry + (1.2 * float(row["atr"]))
                tp = entry - (2.0 * float(row["atr"]))
                eng.open_trade(t, entry, direction="short", stop_loss=sl, take_profit=tp)
                open_idx = i

    if eng.current_trade is not None:
        eng.close_trade(df.index[-1], float(df["close"].iloc[-1]), "end_of_data")

    trades = eng.closed_trades
    
    # Save results for review app
    output_dir = Path(__file__).parents[2] / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    backtest_data = {
        "name": f"ORB+VWAP {symbol}",
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
    
    with open(output_dir / "orb_vwap_btc.json", "w") as f:
        json.dump(backtest_data, f, indent=2)

    wins = sum(1 for t in trades if t.pnl and t.pnl > 0)
    wr = (wins / len(trades) * 100) if trades else 0.0
    ret = (eng.capital - eng.initial_capital) / eng.initial_capital * 100
    exits = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1

    print(f"NON-ICT ORB+VWAP - {symbol}")
    print(f"Trades: {len(trades)} | WR: {wr:.2f}% | Return: {ret:.2f}%")
    print(f"Exit reasons: {exits}")
    print(f"Saved to {output_dir / 'orb_vwap_btc.json'}")


if __name__ == "__main__":
    run()


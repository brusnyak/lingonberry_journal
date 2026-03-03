#!/usr/bin/env python3
"""Test trade logging with 3-timeframe chart generation"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import journal_db
from bot.tradingview_chart import create_tradingview_chart, save_chart
from infra.market_data import load_ohlcv_with_cache
from datetime import timedelta

# Trade details
TRADE = {
    'symbol': 'EURUSD',
    'direction': 'SHORT',  # TP below entry
    'entry_price': 1.17383,
    'sl_price': 1.17480,
    'tp_price': 1.16900,
    'entry_time': '12:45',  # Today
    'account_balance': 47746.20,
    'risk_pct': 0.6,
    'notes': 'Followed trend down, entered after CHOCH + BOS confirmation',
    'mood': 'confident',
}

def calculate_position_size(balance, risk_pct, entry, sl):
    """Calculate position size based on risk"""
    risk_amount = balance * (risk_pct / 100)
    risk_pips = abs(entry - sl) * 10000  # Convert to pips
    pip_value = 10  # $10 per pip for 1 lot EURUSD
    lots = risk_amount / (risk_pips * pip_value)
    return round(lots, 2)

def fetch_and_chart(symbol, timeframe, entry_time, entry_price, sl_price, tp_price, direction):
    """Fetch data and create chart"""
    print(f"\n📊 Generating {timeframe} chart...")
    
    # Calculate date range
    end = datetime.now(timezone.utc)
    if timeframe == 'H4':
        start = end - timedelta(days=14)
    elif timeframe == 'M30':
        start = end - timedelta(days=7)
    else:  # M5
        start = end - timedelta(days=3)
    
    # Fetch data
    df = load_ohlcv_with_cache(
        symbol=symbol,
        asset_type='forex',
        timeframe=timeframe,
        start=start,
        end=end,
        ttl_seconds=3600
    )
    
    if df.empty:
        print(f"❌ No data for {timeframe}")
        return None
    
    print(f"   Fetched {len(df)} bars")
    
    # Rename ts to datetime for chart
    df = df.rename(columns={'ts': 'datetime'})
    
    # Create chart
    fig = create_tradingview_chart(
        df=df,
        title=f'{symbol} - {direction} - {timeframe}',
        show_volume=False,
        figsize=(16, 9),
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        direction=direction.lower()
    )
    
    # Save
    output_dir = Path('data/reports')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chart_path = output_dir / f'trade_{symbol}_{direction}_{timeframe}_{timestamp}.png'
    save_chart(fig, str(chart_path), dpi=150)
    
    print(f"   ✅ Saved: {chart_path.name}")
    return str(chart_path)

def main():
    print("=" * 60)
    print("Trade Logging Test")
    print("=" * 60)
    
    # Calculate position size
    lots = calculate_position_size(
        TRADE['account_balance'],
        TRADE['risk_pct'],
        TRADE['entry_price'],
        TRADE['sl_price']
    )
    
    print(f"\n📝 Trade Details:")
    print(f"   Symbol: {TRADE['symbol']}")
    print(f"   Direction: {TRADE['direction']}")
    print(f"   Entry: {TRADE['entry_price']}")
    print(f"   SL: {TRADE['sl_price']}")
    print(f"   TP: {TRADE['tp_price']}")
    print(f"   Position Size: {lots} lots")
    print(f"   Risk: {TRADE['risk_pct']}% (${TRADE['account_balance'] * TRADE['risk_pct'] / 100:.2f})")
    
    # Calculate RR
    risk = abs(TRADE['entry_price'] - TRADE['sl_price'])
    reward = abs(TRADE['tp_price'] - TRADE['entry_price'])
    rr = reward / risk if risk > 0 else 0
    print(f"   RR Ratio: 1:{rr:.2f}")
    
    # Parse entry time (today at specified time)
    now = datetime.now(timezone.utc)
    hh, mm = TRADE['entry_time'].split(':')
    entry_dt = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    
    print(f"\n⏰ Entry Time: {entry_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    
    # Generate 3-timeframe charts
    print(f"\n📈 Generating Charts...")
    chart_paths = []
    
    for tf in ['H4', 'M30', 'M5']:
        path = fetch_and_chart(
            symbol=TRADE['symbol'],
            timeframe=tf,
            entry_time=entry_dt,
            entry_price=TRADE['entry_price'],
            sl_price=TRADE['sl_price'],
            tp_price=TRADE['tp_price'],
            direction=TRADE['direction']
        )
        if path:
            chart_paths.append(path)
    
    print(f"\n✅ Generated {len(chart_paths)} charts")
    
    # Log to database
    print(f"\n💾 Logging to database...")
    journal_db.init_db()
    
    accounts = journal_db.get_accounts()
    if not accounts:
        print("❌ No account found. Creating default account...")
        account_id = journal_db.create_account(
            name="Demo Account",
            currency="USD",
            initial_balance=TRADE['account_balance']
        )
    else:
        account_id = accounts[0]['id']
    
    trade_id = journal_db.create_trade(
        account_id=account_id,
        symbol=TRADE['symbol'],
        direction=TRADE['direction'],
        entry_price=TRADE['entry_price'],
        position_size=lots,
        ts_open=entry_dt.isoformat(),
        asset_type='forex',
        sl_price=TRADE['sl_price'],
        tp_price=TRADE['tp_price'],
        notes=f"{TRADE['notes']} | mood:{TRADE['mood']}",
        provider='manual'
    )
    
    # Save chart paths
    if chart_paths:
        journal_db.set_trade_chart_paths(trade_id, chart_paths)
    
    print(f"✅ Trade #{trade_id} logged!")
    
    print("\n" + "=" * 60)
    print("✅ Complete!")
    print("=" * 60)
    print(f"\nTrade ID: {trade_id}")
    print(f"Charts: {len(chart_paths)}")
    for path in chart_paths:
        print(f"  - {Path(path).name}")

if __name__ == '__main__':
    main()

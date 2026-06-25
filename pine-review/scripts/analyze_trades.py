"""
Comprehensive Trade Analysis Script

Analyzes ML strategy trades to understand:
- Trade timing and frequency
- Entry/exit quality (ICT context)
- Stop loss and take profit placement
- Risk-reward ratios
- Time in trade
- Win/loss patterns
"""

import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.join(script_dir, '..')
sys.path.insert(0, parent_dir)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure
from src.ml.features import prepare_ml_features
from src.ml.lorentzian import LorentzianClassifier, create_labels
from src.backtest.engine import BacktestEngine, BacktestResult


def load_data(symbol: str = 'BTCUSD', timeframe: str = '15', limit: int = 5000) -> pd.DataFrame:
    """Load and prepare data."""
    print(f"\n{'='*60}")
    print(f"Loading {symbol} {timeframe}min data...")
    print(f"{'='*60}")
    
    loader = DataLoader()
    df = loader.load(symbol, timeframe, limit=limit)
    df = calculate_all_technicals(df)
    
    # Calculate date range
    start_date = df.index[0]
    end_date = df.index[-1]
    days = (end_date - start_date).days
    
    print(f"\nData Range:")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    print(f"  Duration: {days} days ({days/30:.1f} months)")
    print(f"  Bars: {len(df)}")
    
    return df


def calculate_atr_stop_loss(df: pd.DataFrame, atr_multiplier: float = 2.0) -> pd.Series:
    """Calculate ATR-based stop loss distance."""
    return df['atr'] * atr_multiplier


def ml_strategy_with_analysis(df: pd.DataFrame, features_norm: pd.DataFrame,
                               k: int = 15, lookback: int = 2000,
                               min_confidence: float = 0.0) -> tuple:
    """
    Run ML strategy and collect detailed trade information.
    
    Returns:
        (signals DataFrame, trades list with detailed info)
    """
    # Analyze market structure once
    print("Analyzing market structure...")
    ms = analyze_market_structure(df)
    
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Initialize classifier
    clf = LorentzianClassifier(k=k, lookback=lookback)
    
    # Generate predictions
    predictions = clf.predict_series(features_norm, labels, start_idx=lookback)
    
    # Align predictions with df
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0
    signals['confidence'] = 0.0
    
    signals.loc[predictions.index, 'signal'] = predictions['signal']
    signals.loc[predictions.index, 'confidence'] = predictions['confidence']
    
    # Filter by confidence
    signals.loc[signals['confidence'] < min_confidence, 'signal'] = 0
    
    # Calculate ATR stops
    signals['atr_stop'] = calculate_atr_stop_loss(df, atr_multiplier=2.0)
    
    # Collect detailed trade info
    trades = []
    in_position = False
    entry_idx = None
    entry_price = None
    entry_signal = None
    stop_loss = None
    
    print("Simulating trades...")
    for i in range(len(df)):
        if in_position:
            # Check exit conditions
            current_price = df.iloc[i]['close']
            
            # Stop loss hit
            if entry_signal == 1 and current_price <= stop_loss:
                exit_reason = 'stop_loss'
                exit_price = stop_loss
            elif entry_signal == -1 and current_price >= stop_loss:
                exit_reason = 'stop_loss'
                exit_price = stop_loss
            # Opposite signal
            elif signals.iloc[i]['signal'] == -entry_signal:
                exit_reason = 'opposite_signal'
                exit_price = current_price
            else:
                continue
            
            # Record trade
            pnl_pct = ((exit_price - entry_price) / entry_price) * entry_signal * 100
            bars_in_trade = i - entry_idx
            
            # Get ICT context at entry (pass pre-analyzed market structure)
            ict_context = analyze_ict_context_fast(df, ms, entry_idx, 'long' if entry_signal == 1 else 'short')
            
            trades.append({
                'entry_idx': entry_idx,
                'entry_time': df.index[entry_idx],
                'entry_price': entry_price,
                'exit_idx': i,
                'exit_time': df.index[i],
                'exit_price': exit_price,
                'direction': 'long' if entry_signal == 1 else 'short',
                'pnl_pct': pnl_pct,
                'bars_in_trade': bars_in_trade,
                'exit_reason': exit_reason,
                'stop_loss': stop_loss,
                'confidence': signals.iloc[entry_idx]['confidence'],
                **ict_context
            })
            
            in_position = False
            entry_idx = None
            entry_price = None
            entry_signal = None
            stop_loss = None
        
        else:
            # Check entry conditions
            if signals.iloc[i]['signal'] != 0:
                in_position = True
                entry_idx = i
                entry_price = df.iloc[i]['close']
                entry_signal = signals.iloc[i]['signal']
                
                # Set stop loss
                atr_stop = signals.iloc[i]['atr_stop']
                if entry_signal == 1:
                    stop_loss = entry_price - atr_stop
                else:
                    stop_loss = entry_price + atr_stop
    
    return signals, trades


def analyze_ict_context_fast(df: pd.DataFrame, ms: dict, trade_idx: int, direction: str) -> dict:
    """
    Analyze ICT context at trade entry (using pre-analyzed market structure).
    
    Returns dict with:
    - near_fvg: bool
    - near_ob: bool
    - near_liquidity: bool
    - premium_discount: str
    - confluence_score: float
    """
    # Get current bar data
    bar = df.iloc[trade_idx]
    price = bar['close']
    
    context = {
        'near_fvg': False,
        'near_ob': False,
        'near_liquidity': False,
        'premium_discount': 'neutral',
        'confluence_score': 0,
        'fvg_type': None,
        'ob_type': None,
        'liquidity_distance': None
    }
    
    # Check FVGs
    for fvg in ms['fvgs']:
        if fvg.index <= trade_idx:
            # Check if price is near FVG
            fvg_mid = (fvg.top + fvg.bottom) / 2
            distance_pct = abs(price - fvg_mid) / price
            if distance_pct < 0.01:  # Within 1%
                context['near_fvg'] = True
                context['fvg_type'] = fvg.type
                break
    
    # Check Order Blocks
    for ob in ms['order_blocks']:
        if ob.index <= trade_idx:
            # Check if price is near OB
            ob_mid = (ob.top + ob.bottom) / 2
            distance_pct = abs(price - ob_mid) / price
            if distance_pct < 0.01:  # Within 1%
                context['near_ob'] = True
                context['ob_type'] = ob.type
                break
    
    # Check Liquidity
    min_distance = float('inf')
    for liq in ms['liquidity_levels']:
        if liq.start_index <= trade_idx and not liq.swept:
            distance_pct = abs(price - liq.price) / price
            if distance_pct < min_distance:
                min_distance = distance_pct
    
    if min_distance < 0.02:  # Within 2%
        context['near_liquidity'] = True
        context['liquidity_distance'] = min_distance
    
    # Check Premium/Discount
    for zone in ms['premium_discount_zones']:
        if zone.start_index <= trade_idx <= zone.end_index:
            if price > zone.equilibrium:
                context['premium_discount'] = 'premium'
            else:
                context['premium_discount'] = 'discount'
            break
    
    # Calculate confluence score
    if context['near_fvg']:
        context['confluence_score'] += 2
    if context['near_ob']:
        context['confluence_score'] += 2
    if context['near_liquidity']:
        context['confluence_score'] += 1
    if (direction == 'long' and context['premium_discount'] == 'discount') or \
       (direction == 'short' and context['premium_discount'] == 'premium'):
        context['confluence_score'] += 2
    
    return context


def analyze_trade_patterns(trades: list, df: pd.DataFrame):
    """Analyze patterns in trades."""
    if not trades:
        print("\nNo trades to analyze!")
        return
    
    trades_df = pd.DataFrame(trades)
    
    print(f"\n{'='*60}")
    print(f"TRADE ANALYSIS")
    print(f"{'='*60}")
    
    # Basic stats
    total_trades = len(trades_df)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    print(f"\nBasic Statistics:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Winners: {len(winners)} ({len(winners)/total_trades*100:.1f}%)")
    print(f"  Losers: {len(losers)} ({len(losers)/total_trades*100:.1f}%)")
    print(f"  Avg PnL: {trades_df['pnl_pct'].mean():.2f}%")
    print(f"  Avg Winner: {winners['pnl_pct'].mean():.2f}%")
    print(f"  Avg Loser: {losers['pnl_pct'].mean():.2f}%")
    
    # Risk-Reward Analysis
    print(f"\nRisk-Reward Analysis:")
    avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
    avg_loss = abs(losers['pnl_pct'].mean()) if len(losers) > 0 else 1
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    print(f"  Avg Win: {avg_win:.2f}%")
    print(f"  Avg Loss: {avg_loss:.2f}%")
    print(f"  RR Ratio: {rr_ratio:.2f}:1")
    
    # Time Analysis
    print(f"\nTime Analysis:")
    print(f"  Avg Bars in Trade: {trades_df['bars_in_trade'].mean():.1f}")
    print(f"  Min Bars: {trades_df['bars_in_trade'].min()}")
    print(f"  Max Bars: {trades_df['bars_in_trade'].max()}")
    
    # Calculate time in hours (assuming 15min bars)
    avg_hours = trades_df['bars_in_trade'].mean() * 0.25
    print(f"  Avg Time in Trade: {avg_hours:.1f} hours")
    
    # Trade frequency
    date_range = (df.index[-1] - df.index[0]).days
    trades_per_week = (total_trades / date_range) * 7
    print(f"\nTrade Frequency:")
    print(f"  Total Days: {date_range}")
    print(f"  Trades per Week: {trades_per_week:.1f}")
    
    # Direction analysis
    longs = trades_df[trades_df['direction'] == 'long']
    shorts = trades_df[trades_df['direction'] == 'short']
    print(f"\nDirection Analysis:")
    print(f"  Longs: {len(longs)} ({len(longs)/total_trades*100:.1f}%)")
    print(f"  Shorts: {len(shorts)} ({len(shorts)/total_trades*100:.1f}%)")
    if len(longs) > 0:
        print(f"  Long Win Rate: {len(longs[longs['pnl_pct'] > 0])/len(longs)*100:.1f}%")
    if len(shorts) > 0:
        print(f"  Short Win Rate: {len(shorts[shorts['pnl_pct'] > 0])/len(shorts)*100:.1f}%")
    
    # Exit reason analysis
    print(f"\nExit Reasons:")
    exit_counts = trades_df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")
    
    # ICT Context Analysis
    print(f"\nICT Context at Entry:")
    print(f"  Near FVG: {trades_df['near_fvg'].sum()} ({trades_df['near_fvg'].sum()/total_trades*100:.1f}%)")
    print(f"  Near OB: {trades_df['near_ob'].sum()} ({trades_df['near_ob'].sum()/total_trades*100:.1f}%)")
    print(f"  Near Liquidity: {trades_df['near_liquidity'].sum()} ({trades_df['near_liquidity'].sum()/total_trades*100:.1f}%)")
    print(f"  Avg Confluence Score: {trades_df['confluence_score'].mean():.2f}")
    
    # Premium/Discount analysis
    print(f"\nPremium/Discount Zones:")
    pd_counts = trades_df['premium_discount'].value_counts()
    for zone, count in pd_counts.items():
        zone_trades = trades_df[trades_df['premium_discount'] == zone]
        win_rate = len(zone_trades[zone_trades['pnl_pct'] > 0]) / len(zone_trades) * 100
        print(f"  {zone}: {count} trades, {win_rate:.1f}% win rate")
    
    # Confidence analysis
    print(f"\nConfidence Analysis:")
    print(f"  Avg Confidence: {trades_df['confidence'].mean():.3f}")
    print(f"  Min Confidence: {trades_df['confidence'].min():.3f}")
    print(f"  Max Confidence: {trades_df['confidence'].max():.3f}")
    
    # High confidence trades
    high_conf = trades_df[trades_df['confidence'] > trades_df['confidence'].median()]
    if len(high_conf) > 0:
        high_conf_wr = len(high_conf[high_conf['pnl_pct'] > 0]) / len(high_conf) * 100
        print(f"  High Confidence (>{trades_df['confidence'].median():.3f}): {len(high_conf)} trades, {high_conf_wr:.1f}% win rate")
    
    return trades_df


def visualize_sample_trades(df: pd.DataFrame, trades_df: pd.DataFrame, n_samples: int = 6):
    """Visualize sample trades with entry/exit points."""
    # Select sample trades (mix of winners and losers)
    winners = trades_df[trades_df['pnl_pct'] > 0].head(n_samples // 2)
    losers = trades_df[trades_df['pnl_pct'] <= 0].head(n_samples // 2)
    samples = pd.concat([winners, losers]).sort_values('entry_idx')
    
    fig, axes = plt.subplots(n_samples, 1, figsize=(16, 4*n_samples))
    if n_samples == 1:
        axes = [axes]
    
    for idx, (_, trade) in enumerate(samples.iterrows()):
        ax = axes[idx]
        
        # Get window around trade
        entry_idx = trade['entry_idx']
        exit_idx = trade['exit_idx']
        window_start = max(0, entry_idx - 50)
        window_end = min(len(df), exit_idx + 50)
        
        window_df = df.iloc[window_start:window_end]
        
        # Plot candlesticks
        for i in range(len(window_df)):
            bar = window_df.iloc[i]
            color = 'green' if bar['close'] > bar['open'] else 'red'
            ax.plot([i, i], [bar['low'], bar['high']], color=color, linewidth=0.5)
            ax.plot([i, i], [bar['open'], bar['close']], color=color, linewidth=2)
        
        # Mark entry
        entry_bar = entry_idx - window_start
        ax.scatter(entry_bar, trade['entry_price'], color='blue', s=100, marker='^' if trade['direction'] == 'long' else 'v', zorder=5)
        
        # Mark exit
        exit_bar = exit_idx - window_start
        exit_color = 'green' if trade['pnl_pct'] > 0 else 'red'
        ax.scatter(exit_bar, trade['exit_price'], color=exit_color, s=100, marker='x', zorder=5)
        
        # Draw stop loss line
        ax.axhline(trade['stop_loss'], color='red', linestyle='--', alpha=0.5, linewidth=1)
        
        # Title with trade info
        title = f"{trade['direction'].upper()} | PnL: {trade['pnl_pct']:.2f}% | Bars: {trade['bars_in_trade']} | "
        title += f"Exit: {trade['exit_reason']} | Conf: {trade['confidence']:.3f} | "
        title += f"ICT: FVG={trade['near_fvg']}, OB={trade['near_ob']}, Liq={trade['near_liquidity']}, "
        title += f"Zone={trade['premium_discount']}, Score={trade['confluence_score']}"
        ax.set_title(title, fontsize=10)
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('data/trade_samples.png', dpi=150, bbox_inches='tight')
    print(f"\nSample trades visualization saved to: data/trade_samples.png")
    plt.close()


def main():
    """Main analysis function."""
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    
    # Prepare features
    print(f"\nPreparing ML features...")
    features_norm = prepare_ml_features(df)
    
    # Run strategy with analysis
    print(f"\nRunning ML strategy with detailed analysis...")
    signals, trades = ml_strategy_with_analysis(
        df, features_norm,
        k=15,
        lookback=2000,
        min_confidence=0.0
    )
    
    # Analyze trades
    trades_df = analyze_trade_patterns(trades, df)
    
    # Visualize sample trades
    if trades_df is not None and len(trades_df) > 0:
        visualize_sample_trades(df, trades_df, n_samples=6)
    
    print(f"\n{'='*60}")
    print(f"Analysis complete!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

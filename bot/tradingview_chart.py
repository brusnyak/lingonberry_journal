#!/usr/bin/env python3
"""
TradingView-Style Chart Generator
Creates professional trading charts with position overlays
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple


# TradingView Dark Theme Colors
TV_COLORS = {
    'bg': '#0a0e1a',
    'panel': '#141824',
    'grid': '#1e222d',
    'text': '#d1d4dc',
    'text_muted': '#787b86',
    'border': '#2a2e39',
    'candle_up': '#26a69a',
    'candle_down': '#ef5350',
    'wick': '#787b86',
    'entry_long': '#10b981',
    'entry_short': '#f97316',
    'sl': '#ef4444',
    'tp': '#22c55e',
    'exit': '#8b92a8',
    'risk_zone': '#ef4444',
    'reward_zone': '#22c55e',
}


def create_tradingview_chart(
    df: pd.DataFrame,
    title: str = "Trading Chart",
    show_volume: bool = False,
    figsize: Tuple[int, int] = (16, 9),
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    direction: str = "long",
) -> plt.Figure:
    """
    Create a TradingView-style chart with position overlay
    
    Args:
        df: DataFrame with columns: datetime, open, high, low, close, volume
        title: Chart title
        show_volume: Whether to show volume bars
        figsize: Figure size (width, height)
        entry_price: Entry price for position overlay
        exit_price: Exit price for position overlay
        sl_price: Stop loss price
        tp_price: Take profit price
        direction: 'long' or 'short'
    
    Returns:
        matplotlib Figure object
    """
    # Prepare data
    df = df.copy()
    if 'datetime' not in df.columns and 'ts' in df.columns:
        df = df.rename(columns={'ts': 'datetime'})
    
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    # Create figure
    if show_volume:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, 
                                       gridspec_kw={'height_ratios': [3, 1]},
                                       facecolor=TV_COLORS['bg'])
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=figsize, facecolor=TV_COLORS['bg'])
    
    # Style main axis
    ax1.set_facecolor(TV_COLORS['panel'])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_color(TV_COLORS['border'])
    ax1.spines['bottom'].set_color(TV_COLORS['border'])
    ax1.tick_params(colors=TV_COLORS['text_muted'], which='both')
    ax1.grid(True, color=TV_COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.3)
    
    # Calculate candle width
    if len(df) > 1:
        time_diff = (df['datetime'].iloc[1] - df['datetime'].iloc[0]).total_seconds() / 86400
        width = time_diff * 0.6
    else:
        width = 0.0008
    
    # Plot candlesticks
    for idx, row in df.iterrows():
        dt = mdates.date2num(row['datetime'])
        open_price = row['open']
        close_price = row['close']
        high_price = row['high']
        low_price = row['low']
        
        # Determine color
        color = TV_COLORS['candle_up'] if close_price >= open_price else TV_COLORS['candle_down']
        
        # Draw wick
        ax1.plot([dt, dt], [low_price, high_price], 
                color=TV_COLORS['wick'], linewidth=1, alpha=0.8)
        
        # Draw body
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        
        if height > 0:
            rect = Rectangle((dt - width/2, bottom), width, height,
                           facecolor=color, edgecolor=color, linewidth=0)
            ax1.add_patch(rect)
        else:
            # Doji - draw a line
            ax1.plot([dt - width/2, dt + width/2], [open_price, open_price],
                    color=color, linewidth=1.5)
    
    # Plot Indicators
    indicator_styles = {
        'ema_9': {'color': '#60a5fa', 'lw': 1, 'label': 'EMA 9'},
        'ema_21': {'color': '#f59e0b', 'lw': 1, 'label': 'EMA 21'},
        'ema_50': {'color': '#8b5cf6', 'lw': 1, 'label': 'EMA 50'},
        'ema_200': {'color': '#6b7280', 'lw': 1.5, 'label': 'EMA 200'},
        'vwap': {'color': '#ec4899', 'lw': 1.5, 'label': 'VWAP'},
    }
    
    for col, style in indicator_styles.items():
        if col in df.columns:
            ax1.plot(df['datetime'], df[col], color=style['color'], 
                    linewidth=style['lw'], alpha=0.8, label=style['label'])
    
    # Add position overlay if prices provided
    if entry_price is not None:
        is_long = direction.lower() == 'long'
        entry_color = TV_COLORS['entry_long'] if is_long else TV_COLORS['entry_short']
        
        # Entry line
        ax1.axhline(y=entry_price, color=entry_color, linestyle='-', 
                   linewidth=2, alpha=0.9, label=f'Entry: {entry_price:.5f}', zorder=10)
        
        # Get time range for position boxes
        if len(df) > 0:
            start_time = mdates.date2num(df['datetime'].iloc[0])
            end_time = mdates.date2num(df['datetime'].iloc[-1])
            box_width = end_time - start_time
            
            # Risk zone (entry to SL)
            if sl_price is not None:
                risk_bottom = min(entry_price, sl_price)
                risk_height = abs(entry_price - sl_price)
                risk_box = Rectangle((start_time, risk_bottom), box_width, risk_height,
                                    facecolor=TV_COLORS['risk_zone'], 
                                    edgecolor='none', alpha=0.12, zorder=1)
                ax1.add_patch(risk_box)
                
                # SL line
                ax1.axhline(y=sl_price, color=TV_COLORS['sl'], linestyle='--',
                           linewidth=1.5, alpha=0.8, label=f'SL: {sl_price:.5f}', zorder=10)
            
            # Reward zone (entry to TP)
            if tp_price is not None:
                reward_bottom = min(entry_price, tp_price)
                reward_height = abs(entry_price - tp_price)
                reward_box = Rectangle((start_time, reward_bottom), box_width, reward_height,
                                      facecolor=TV_COLORS['reward_zone'],
                                      edgecolor='none', alpha=0.12, zorder=1)
                ax1.add_patch(reward_box)
                
                # TP line
                ax1.axhline(y=tp_price, color=TV_COLORS['tp'], linestyle='--',
                           linewidth=1.5, alpha=0.8, label=f'TP: {tp_price:.5f}', zorder=10)
        
        # Exit line
        if exit_price is not None:
            # Determine if profitable
            is_profit = (exit_price >= entry_price) if is_long else (exit_price <= entry_price)
            exit_color = TV_COLORS['tp'] if is_profit else TV_COLORS['sl']
            
            ax1.axhline(y=exit_price, color=exit_color, linestyle=':',
                       linewidth=2, alpha=0.9, label=f'Exit: {exit_price:.5f}', zorder=10)
        
        # Entry marker at actual entry time
        if len(df) > 0:
            # Find the candle closest to entry time
            entry_time = df['datetime'].iloc[0]  # Default to first candle
            if 'ts_open' in trade:
                try:
                    trade_entry_time = pd.to_datetime(trade['ts_open'])
                    # Find closest candle to actual entry time
                    time_diffs = abs(df['datetime'] - trade_entry_time)
                    closest_idx = time_diffs.idxmin()
                    entry_time = df.loc[closest_idx, 'datetime']
                except:
                    pass  # Fall back to first candle
            
            marker = '^' if is_long else 'v'
            ax1.scatter([entry_time], [entry_price], marker=marker, s=150,
                       color=entry_color, edgecolor='white', linewidth=1.5, zorder=15)
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    # Title and labels
    ax1.set_title(title, color=TV_COLORS['text'], fontsize=14, 
                 fontweight='bold', pad=15, loc='left')
    ax1.set_ylabel('Price', color=TV_COLORS['text'], fontsize=11)
    
    # Legend
    legend = ax1.legend(loc='upper left', frameon=True, fancybox=False,
                      facecolor=TV_COLORS['panel'], edgecolor=TV_COLORS['border'],
                      fontsize=8, labelcolor=TV_COLORS['text'], ncol=2)
    legend.get_frame().set_alpha(0.8)
    
    # Volume subplot
    if show_volume and 'volume' in df.columns:
        ax2.set_facecolor(TV_COLORS['panel'])
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color(TV_COLORS['border'])
        ax2.spines['bottom'].set_color(TV_COLORS['border'])
        ax2.tick_params(colors=TV_COLORS['text_muted'], which='both')
        ax2.grid(True, color=TV_COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.3)
        
        # Plot volume bars
        colors = [TV_COLORS['candle_up'] if df.iloc[i]['close'] >= df.iloc[i]['open'] 
                 else TV_COLORS['candle_down'] for i in range(len(df))]
        ax2.bar(df['datetime'], df['volume'], width=width, color=colors, alpha=0.6)
        ax2.set_ylabel('Volume', color=TV_COLORS['text'], fontsize=11)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    plt.tight_layout()
    return fig


def save_chart(fig: plt.Figure, output_path: str, dpi: int = 150) -> None:
    """Save chart to file"""
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight', 
               facecolor=TV_COLORS['bg'], edgecolor='none')
    plt.close(fig)


if __name__ == "__main__":
    # Test with sample data
    import numpy as np
    
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
    np.random.seed(42)
    
    # Generate sample OHLC data
    close = 100 + np.cumsum(np.random.randn(100) * 0.5)
    open_price = close + np.random.randn(100) * 0.2
    high = np.maximum(open_price, close) + np.abs(np.random.randn(100) * 0.3)
    low = np.minimum(open_price, close) - np.abs(np.random.randn(100) * 0.3)
    volume = np.random.randint(1000, 10000, 100)
    
    df = pd.DataFrame({
        'datetime': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    # Create chart with position overlay
    fig = create_tradingview_chart(
        df=df,
        title="EURUSD - LONG - H1",
        show_volume=False,
        entry_price=100.5,
        sl_price=99.8,
        tp_price=101.5,
        exit_price=101.2,
        direction='long'
    )
    
    save_chart(fig, 'test_chart.png')
    print("Test chart saved to test_chart.png")

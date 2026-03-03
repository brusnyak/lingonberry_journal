#!/usr/bin/env python3
"""
TradingView-style chart generator with dark theme
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple


# TradingView Dark Theme Colors
TV_COLORS = {
    'background': '#131722',
    'grid': '#1e222d',
    'text': '#d1d4dc',
    'text_secondary': '#787b86',
    'border': '#2a2e39',
    'green': '#26a69a',
    'red': '#ef5350',
    'volume_green': '#26a69a40',
    'volume_red': '#ef535040',
}


def create_tradingview_chart(
    df: pd.DataFrame,
    title: str = "Chart",
    show_volume: bool = False,
    figsize: Tuple[int, int] = (16, 9),
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    direction: Optional[str] = None,
) -> plt.Figure:
    """
    Create a TradingView-style candlestick chart
    
    Args:
        df: DataFrame with columns: datetime, open, high, low, close, volume
        title: Chart title
        show_volume: Show volume subplot
        figsize: Figure size (width, height)
        entry_price: Entry price for trade marker
        exit_price: Exit price for trade marker
        sl_price: Stop loss price
        tp_price: Take profit price
        direction: 'long' or 'short'
    
    Returns:
        matplotlib Figure object
    """
    # Prepare data
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Create figure
    fig, ax1 = plt.subplots(figsize=figsize, facecolor=TV_COLORS['background'])
    
    # Style main axis
    ax1.set_facecolor(TV_COLORS['background'])
    ax1.spines['top'].set_color(TV_COLORS['border'])
    ax1.spines['bottom'].set_color(TV_COLORS['border'])
    ax1.spines['left'].set_visible(False)  # Hide left spine
    ax1.spines['right'].set_color(TV_COLORS['border'])
    ax1.tick_params(colors=TV_COLORS['text'], which='both')
    ax1.tick_params(axis='y', left=False, right=True, labelright=True, labelleft=False)  # Price on right
    ax1.grid(True, color=TV_COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.3)
    
    # Plot candlesticks
    width = 0.6
    for idx, row in df.iterrows():
        x = idx
        open_price = row['open']
        close_price = row['close']
        high_price = row['high']
        low_price = row['low']
        
        color = TV_COLORS['green'] if close_price >= open_price else TV_COLORS['red']
        
        # Wick (high-low line)
        ax1.plot([x, x], [low_price, high_price], color=color, linewidth=1, solid_capstyle='round')
        
        # Body (open-close rectangle)
        body_height = abs(close_price - open_price)
        body_bottom = min(open_price, close_price)
        
        if body_height < 0.00001:  # Doji
            body_height = 0.00001
        
        rect = Rectangle(
            (x - width/2, body_bottom),
            width,
            body_height,
            facecolor=color,
            edgecolor=color,
            linewidth=0
        )
        ax1.add_patch(rect)
    
    # Add trade markers if provided
    if entry_price is not None and direction is not None:
        # Calculate position box dimensions
        entry_idx = 0
        exit_idx = len(df) - 1
        
        # Draw position box (shaded area showing the trade)
        if direction.lower() == 'long':
            # Long: shade from entry to TP (green) and entry to SL (red)
            if tp_price is not None:
                # Profit zone (entry to TP)
                for i in range(len(df)):
                    rect = Rectangle(
                        (i - width/2, entry_price),
                        width,
                        tp_price - entry_price,
                        facecolor=TV_COLORS['green'],
                        edgecolor='none',
                        alpha=0.08,
                        zorder=1
                    )
                    ax1.add_patch(rect)
            
            if sl_price is not None:
                # Risk zone (SL to entry)
                for i in range(len(df)):
                    rect = Rectangle(
                        (i - width/2, sl_price),
                        width,
                        entry_price - sl_price,
                        facecolor=TV_COLORS['red'],
                        edgecolor='none',
                        alpha=0.08,
                        zorder=1
                    )
                    ax1.add_patch(rect)
        else:  # short
            # Short: shade from entry to TP (green) and entry to SL (red)
            if tp_price is not None:
                # Profit zone (TP to entry)
                for i in range(len(df)):
                    rect = Rectangle(
                        (i - width/2, tp_price),
                        width,
                        entry_price - tp_price,
                        facecolor=TV_COLORS['green'],
                        edgecolor='none',
                        alpha=0.08,
                        zorder=1
                    )
                    ax1.add_patch(rect)
            
            if sl_price is not None:
                # Risk zone (entry to SL)
                for i in range(len(df)):
                    rect = Rectangle(
                        (i - width/2, entry_price),
                        width,
                        sl_price - entry_price,
                        facecolor=TV_COLORS['red'],
                        edgecolor='none',
                        alpha=0.08,
                        zorder=1
                    )
                    ax1.add_patch(rect)
        
        # Draw horizontal lines
        ax1.axhline(entry_price, color='#2962ff', linestyle='--', linewidth=1.5, alpha=0.7, label='Entry')
        
        if sl_price is not None:
            ax1.axhline(sl_price, color=TV_COLORS['red'], linestyle=':', linewidth=1, alpha=0.6, label='SL')
        
        if tp_price is not None:
            ax1.axhline(tp_price, color=TV_COLORS['green'], linestyle=':', linewidth=1, alpha=0.6, label='TP')
        
        # Entry marker
        marker = '^' if direction.lower() == 'long' else 'v'
        marker_color = TV_COLORS['green'] if direction.lower() == 'long' else TV_COLORS['red']
        ax1.plot(entry_idx, entry_price, marker, color=marker_color, markersize=10, zorder=5, label=f'{direction.upper()} Entry')
    
    if exit_price is not None:
        exit_idx = len(df) - 1
        ax1.axhline(exit_price, color='#ff6d00', linestyle='--', linewidth=1.5, alpha=0.7, label='Exit')
        ax1.plot(exit_idx, exit_price, 'o', color='#ff6d00', markersize=8, zorder=5)
    
    # Title and labels
    ax1.set_title(title, color=TV_COLORS['text'], fontsize=14, fontweight='bold', pad=20)
    ax1.set_ylabel('Price', color=TV_COLORS['text'], fontsize=11)
    
    # Format x-axis
    if len(df) > 0:
        # Create time labels
        time_labels = []
        time_positions = []
        
        # Show labels at regular intervals
        step = max(1, len(df) // 12)  # Show ~12 labels
        for i in range(0, len(df), step):
            time_labels.append(df['datetime'].iloc[i].strftime('%H:%M'))
            time_positions.append(i)
        
        ax1.set_xticks(time_positions)
        ax1.set_xticklabels(time_labels, color=TV_COLORS['text_secondary'], fontsize=9)
    
    # Set x-axis limits with padding
    ax1.set_xlim(-1, len(df))
    
    # Add legend if trade markers exist
    if any([entry_price, exit_price, sl_price, tp_price]):
        legend = ax1.legend(
            loc='upper left',
            facecolor=TV_COLORS['grid'],
            edgecolor=TV_COLORS['border'],
            labelcolor=TV_COLORS['text'],
            fontsize=9
        )
        legend.get_frame().set_alpha(0.9)
    
    plt.tight_layout()
    
    return fig


def save_chart(fig: plt.Figure, output_path: str, dpi: int = 150):
    """Save chart to file"""
    fig.savefig(output_path, dpi=dpi, facecolor=TV_COLORS['background'], bbox_inches='tight')
    plt.close(fig)


# Example usage
if __name__ == '__main__':
    import sys
    import os
    from pathlib import Path
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Load sample data
    data_path = Path('data/market_data/forex/EURUSD/h1.csv')
    
    if not data_path.exists():
        print(f"❌ No data found at {data_path}")
        print("Run: python3 scripts/demo_eurusd_week.py first")
        sys.exit(1)
    
    df = pd.read_csv(data_path)
    
    # Get yesterday's data
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    
    yesterday = df['date'].unique()[-2] if len(df['date'].unique()) > 1 else df['date'].unique()[-1]
    day_data = df[df['date'] == yesterday].copy()
    
    print(f"Creating chart for {yesterday}...")
    
    # Create chart
    fig = create_tradingview_chart(
        df=day_data,
        title=f'EURUSD - {yesterday} (H1)',
        show_volume=True,
        figsize=(16, 9)
    )
    
    # Save
    output_path = Path('data/reports/eurusd_tradingview_style.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_chart(fig, str(output_path), dpi=150)
    
    print(f"✅ Chart saved to: {output_path}")

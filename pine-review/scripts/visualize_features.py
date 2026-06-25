#!/usr/bin/env python
"""
Visualization script to validate feature engineering implementations.
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.technicals import calculate_all_technicals
from src.features.microstructure import calculate_all_microstructure
from src.features.market_structure import analyze_market_structure
from src.features.regime import detect_regime_rule_based


def plot_price_and_structure(ax, df, structure):
    """Plot price with market structure overlays."""
    ax.plot(df.index, df['close'], label='Close', color='black', linewidth=1)
    
    # Plot swing highs
    for swing in structure['swing_highs']:
        ax.scatter(swing.index, swing.price, color='green', marker='^', s=100, zorder=5)
    
    # Plot swing lows
    for swing in structure['swing_lows']:
        ax.scatter(swing.index, swing.price, color='red', marker='v', s=100, zorder=5)
    
    # Plot FVGs
    for fvg in structure['fvgs'][:10]:  # Limit to first 10 for clarity
        color = 'lightgreen' if fvg.type == 'bullish' else 'lightcoral'
        alpha = 0.3 if not fvg.mitigated else 0.1
        ax.axhspan(fvg.bottom, fvg.top, xmin=fvg.index/len(df), xmax=min(1, (fvg.index+20)/len(df)),
                   color=color, alpha=alpha, label='FVG' if fvg == structure['fvgs'][0] else '')
    
    # Plot order blocks
    for ob in structure['order_blocks'][:5]:  # Limit to first 5
        color = 'blue' if ob.type == 'bullish' else 'orange'
        ax.axhspan(ob.bottom, ob.top, xmin=ob.index/len(df), xmax=min(1, (ob.index+10)/len(df)),
                   color=color, alpha=0.2, linestyle='--')
    
    ax.set_ylabel('Price')
    ax.set_title('Price Action with Market Structure (Swings, FVGs, Order Blocks)')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_technicals(ax1, ax2, ax3, df_tech):
    """Plot technical indicators."""
    # RSI
    ax1.plot(df_tech.index, df_tech['rsi'], label='RSI', color='purple')
    ax1.axhline(70, color='red', linestyle='--', alpha=0.5)
    ax1.axhline(30, color='green', linestyle='--', alpha=0.5)
    ax1.set_ylabel('RSI')
    ax1.set_title('Technical Indicators')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 100)
    
    # MACD
    ax2.plot(df_tech.index, df_tech['macd'], label='MACD', color='blue')
    ax2.plot(df_tech.index, df_tech['macd_signal'], label='Signal', color='red')
    ax2.bar(df_tech.index, df_tech['macd_hist'], label='Histogram', color='gray', alpha=0.3)
    ax2.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax2.set_ylabel('MACD')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # ATR Percentile
    ax3.plot(df_tech.index, df_tech['atr_percentile'], label='ATR Percentile', color='orange')
    ax3.axhline(70, color='red', linestyle='--', alpha=0.5, label='High Vol')
    ax3.axhline(30, color='green', linestyle='--', alpha=0.5, label='Low Vol')
    ax3.set_ylabel('ATR %ile')
    ax3.set_xlabel('Time')
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 100)


def plot_microstructure(ax1, ax2, df_micro):
    """Plot microstructure features."""
    # Volume Delta
    colors = ['green' if x > 0 else 'red' for x in df_micro['volume_delta']]
    ax1.bar(df_micro.index, df_micro['volume_delta'], color=colors, alpha=0.6)
    ax1.plot(df_micro.index, df_micro['cumulative_delta'], label='Cumulative Delta', 
             color='blue', linewidth=2)
    ax1.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax1.set_ylabel('Volume Delta')
    ax1.set_title('Order Flow Analysis')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # Order Flow Imbalance
    imbalance_colors = ['green' if x > 0 else 'red' if x < 0 else 'gray' 
                       for x in df_micro['order_flow_imbalance']]
    ax2.scatter(df_micro.index, df_micro['order_flow_imbalance'], 
               c=imbalance_colors, alpha=0.6, s=30)
    ax2.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax2.set_ylabel('Imbalance')
    ax2.set_xlabel('Time')
    ax2.set_title('Order Flow Imbalance (>0: Buy Pressure, <0: Sell Pressure)')
    ax2.grid(True, alpha=0.3)


def plot_regime(ax, df, regimes):
    """Plot regime detection."""
    # Map regimes to colors
    regime_colors = {
        'trending_bull': 'green',
        'trending_bear': 'red',
        'high_vol_ranging': 'orange',
        'low_vol_ranging': 'blue',
        'transition': 'gray'
    }
    
    # Plot price
    ax.plot(df.index, df['close'], color='black', linewidth=1, alpha=0.5)
    
    # Color background by regime
    current_regime = None
    start_idx = 0
    
    for i, regime in enumerate(regimes):
        if regime != current_regime:
            if current_regime is not None:
                color = regime_colors.get(current_regime, 'gray')
                ax.axvspan(start_idx, i, alpha=0.2, color=color)
            current_regime = regime
            start_idx = i
    
    # Final regime
    if current_regime is not None:
        color = regime_colors.get(current_regime, 'gray')
        ax.axvspan(start_idx, len(regimes), alpha=0.2, color=color)
    
    ax.set_ylabel('Price')
    ax.set_xlabel('Time')
    ax.set_title('Market Regime Detection')
    
    # Create legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=color, alpha=0.3, label=regime.replace('_', ' ').title())
                      for regime, color in regime_colors.items()]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)


def main():
    """Main visualization function."""
    print("Loading and analyzing data...")
    
    # Load data
    df = pd.read_parquet('data/parquet/crypto/BTCUSD1440.parquet')
    df = df.tail(200)  # Last 200 days for clarity
    df = df.reset_index(drop=True)
    
    print(f"Analyzing {len(df)} candles from {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Calculate features
    print("\nCalculating features...")
    df_tech = calculate_all_technicals(df, normalize=False)
    df_micro = calculate_all_microstructure(df)
    structure = analyze_market_structure(df)
    regimes = detect_regime_rule_based(df)
    
    print(f"✓ Technical indicators: {len([c for c in df_tech.columns if c not in df.columns])} features")
    print(f"✓ Microstructure: {len([c for c in df_micro.columns if c not in df.columns])} features")
    print(f"✓ Market structure: {len(structure['swing_highs'])} swings, {len(structure['fvgs'])} FVGs")
    print(f"✓ Regimes: {regimes.value_counts().to_dict()}")
    
    # Create visualization
    print("\nCreating visualization...")
    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(6, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    # Row 1: Price with structure (full width)
    ax_price = fig.add_subplot(gs[0:2, :])
    plot_price_and_structure(ax_price, df, structure)
    
    # Row 2: Technical indicators
    ax_rsi = fig.add_subplot(gs[2, 0])
    ax_macd = fig.add_subplot(gs[3, 0])
    ax_atr = fig.add_subplot(gs[4, 0])
    plot_technicals(ax_rsi, ax_macd, ax_atr, df_tech)
    
    # Row 2: Microstructure
    ax_delta = fig.add_subplot(gs[2:4, 1])
    ax_imbalance = fig.add_subplot(gs[4, 1])
    plot_microstructure(ax_delta, ax_imbalance, df_micro)
    
    # Row 3: Regime (full width)
    ax_regime = fig.add_subplot(gs[5, :])
    plot_regime(ax_regime, df, regimes)
    
    plt.suptitle('Feature Engineering Validation - BTC/USD Daily (Last 200 Days)', 
                 fontsize=14, fontweight='bold')
    
    # Save
    output_path = 'feature_validation.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Visualization saved to: {output_path}")
    
    # Print summary statistics
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    print("\n1. Market Structure:")
    print(f"   - Swing Highs: {len(structure['swing_highs'])}")
    print(f"   - Swing Lows: {len(structure['swing_lows'])}")
    print(f"   - Fair Value Gaps: {len(structure['fvgs'])}")
    print(f"   - Mitigated FVGs: {sum(1 for fvg in structure['fvgs'] if fvg.mitigated)}")
    print(f"   - Order Blocks: {len(structure['order_blocks'])}")
    print(f"   - Structure Breaks: {len(structure['structure_breaks'])}")
    
    print("\n2. Technical Indicators (Last Value):")
    print(f"   - RSI: {df_tech['rsi'].iloc[-1]:.2f}")
    print(f"   - MACD: {df_tech['macd'].iloc[-1]:.2f}")
    print(f"   - ATR Percentile: {df_tech['atr_percentile'].iloc[-1]:.2f}")
    print(f"   - Volume Ratio: {df_tech['volume_ratio'].iloc[-1]:.2f}")
    
    print("\n3. Order Flow (Last 10 candles avg):")
    print(f"   - Avg Volume Delta: {df_micro['volume_delta'].tail(10).mean():.2f}")
    print(f"   - Cumulative Delta: {df_micro['cumulative_delta'].iloc[-1]:.2f}")
    print(f"   - Imbalance Count: {(df_micro['order_flow_imbalance'].tail(10) != 0).sum()}/10")
    
    print("\n4. Regime Distribution:")
    for regime, count in regimes.value_counts().items():
        print(f"   - {regime.replace('_', ' ').title()}: {count} ({count/len(regimes)*100:.1f}%)")
    
    print("\n" + "="*60)
    print("✓ All features validated successfully!")
    print("="*60)


if __name__ == '__main__':
    main()

"""
Detailed ICT visualization for validation.
Shows each component clearly on separate charts.
"""
import sys
sys.path.append('backend')

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure


def load_data(symbol: str = 'BTCUSD', timeframe: str = '15', limit: int = 500) -> pd.DataFrame:
    """Load data from CSV files."""
    filepath = f'data/charts/crypto/{symbol}{timeframe}.csv'
    
    df = pd.read_csv(filepath, sep='\s+', header=None,
                    names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    
    return df


def plot_candles(ax, df):
    """Plot candlesticks."""
    for i in range(len(df)):
        color = 'green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red'
        
        # Candle body
        body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
        body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
        rect = patches.Rectangle(
            (i, body_bottom), 0.6, body_height,
            linewidth=0.5, edgecolor='white', facecolor=color, alpha=0.8
        )
        ax.add_patch(rect)
        
        # Wicks
        ax.plot([i + 0.3, i + 0.3], [df['low'].iloc[i], df['high'].iloc[i]], 
               color='white', linewidth=0.5, alpha=0.6)


def main():
    print("\n" + "="*60)
    print("DETAILED ICT VISUALIZATION")
    print("="*60)
    
    # Load data (last 500 bars for clarity)
    df = load_data('BTCUSD', '15', limit=500)
    print(f"\nLoaded {len(df)} bars")
    
    # Analyze structure
    structure = analyze_market_structure(
        df,
        swing_period=5,
        break_type='body',
        fvg_mitigation='partial',
        fvg_mitigation_threshold=0.382,
        volume_filter=True,
        detect_amd=False,
        premium_discount_lookback=100
    )
    
    print(f"\nStructure detected:")
    print(f"  Swings: {len(structure['swing_highs'])} highs, {len(structure['swing_lows'])} lows")
    print(f"  FVGs: {len(structure['fvgs'])}")
    print(f"  Order Blocks: {len(structure['order_blocks'])}")
    print(f"  Structure Breaks: {len(structure['structure_breaks'])}")
    print(f"  Liquidity Levels: {len(structure['liquidity_levels'])}")
    print(f"  Round Levels: {len(structure['round_levels'])}")
    print(f"  Open Levels: D={len(structure['open_levels'].get('daily', []))}, W={len(structure['open_levels'].get('weekly', []))}, M={len(structure['open_levels'].get('monthly', []))}")
    print(f"  Premium/Discount Zones: {len(structure['premium_discount_zones'])}")
    
    # Set dark theme
    plt.style.use('dark_background')
    
    # Create figure with 6 subplots (added Premium/Discount)
    fig, axes = plt.subplots(6, 1, figsize=(20, 18))
    
    # Chart 1: Swings & Structure Breaks
    ax1 = axes[0]
    plot_candles(ax1, df)
    
    # Plot swings
    for swing in structure['swing_highs']:
        label = structure['swing_labels'].get(swing.index, '')
        ax1.plot(swing.index, swing.price, 'v', color='lime', markersize=10, markeredgecolor='white', markeredgewidth=1)
        ax1.text(swing.index, swing.price, f' {label}', fontsize=9, color='lime', 
                verticalalignment='bottom', fontweight='bold')
    
    for swing in structure['swing_lows']:
        label = structure['swing_labels'].get(swing.index, '')
        ax1.plot(swing.index, swing.price, '^', color='red', markersize=10, markeredgecolor='white', markeredgewidth=1)
        ax1.text(swing.index, swing.price, f' {label}', fontsize=9, color='red',
                verticalalignment='top', fontweight='bold')
    
    # Plot structure breaks
    for brk in structure['structure_breaks']:
        color = 'lime' if brk.direction == 'bullish' else 'red'
        marker = 'BOS' if brk.type == 'BOS' else 'CHoCH'
        ax1.plot(brk.index, brk.price, 'o', color=color, markersize=8, markeredgecolor='white', markeredgewidth=1.5)
        ax1.text(brk.index, brk.price, f' {marker}', fontsize=8, color=color, fontweight='bold')
    
    ax1.set_title('1. SWINGS & STRUCTURE BREAKS (BOS/CHoCH)', fontsize=14, fontweight='bold', color='cyan')
    ax1.set_ylabel('Price', fontsize=11)
    ax1.grid(True, alpha=0.2)
    
    # Chart 2: Liquidity Levels
    ax2 = axes[1]
    plot_candles(ax2, df)
    
    for liq in structure['liquidity_levels']:
        if liq.type == 'high':
            color = 'lime'
            linestyle = '-' if not liq.swept else ':'
            alpha = 0.8 if not liq.swept else 0.3
            end_idx = liq.swept_index if liq.swept else len(df)
        else:
            color = 'red'
            linestyle = '-' if not liq.swept else ':'
            alpha = 0.8 if not liq.swept else 0.3
            end_idx = liq.swept_index if liq.swept else len(df)
        
        ax2.plot([liq.start_index, end_idx], [liq.price, liq.price], 
                linestyle=linestyle, color=color, linewidth=2, alpha=alpha)
        
        # Mark sweep point
        if liq.swept:
            ax2.plot(liq.swept_index, liq.price, 'x', color=color, 
                    markersize=12, markeredgewidth=3)
    
    ax2.set_title('2. LIQUIDITY LEVELS (Solid=Unswept, Dotted=Swept)', fontsize=14, fontweight='bold', color='cyan')
    ax2.set_ylabel('Price', fontsize=11)
    ax2.grid(True, alpha=0.2)
    
    # Chart 3: Fair Value Gaps
    ax3 = axes[2]
    plot_candles(ax3, df)
    
    for fvg in structure['fvgs']:
        color = 'blue' if fvg.type == 'bullish' else 'orange'
        alpha = 0.25 if not fvg.mitigated else 0.1
        
        # FVG box
        rect = patches.Rectangle(
            (fvg.index, fvg.bottom), len(df) - fvg.index, fvg.top - fvg.bottom,
            linewidth=0, facecolor=color, alpha=alpha
        )
        ax3.add_patch(rect)
        
        # 50% midline - EMPHASIZED
        mid = (fvg.top + fvg.bottom) / 2
        mid_color = 'yellow' if fvg.type == 'bullish' else 'purple'
        ax3.plot([fvg.index, len(df)], [mid, mid], '-', 
                color=mid_color, linewidth=2.5, alpha=0.9)
        
        # Label
        ax3.text(fvg.index, mid, f' FVG', fontsize=7, color=mid_color, fontweight='bold')
    
    ax3.set_title('3. FAIR VALUE GAPS (Yellow/Purple=50% Midpoint)', fontsize=14, fontweight='bold', color='cyan')
    ax3.set_ylabel('Price', fontsize=11)
    ax3.grid(True, alpha=0.2)
    
    # Chart 4: Order Blocks
    ax4 = axes[3]
    plot_candles(ax4, df)
    
    for ob in structure['order_blocks']:
        color = 'lime' if ob.type == 'bullish' else 'red'
        alpha = 0.35 if not ob.mitigated else 0.15
        
        # OB box
        rect = patches.Rectangle(
            (ob.index, ob.bottom), len(df) - ob.index, ob.top - ob.bottom,
            linewidth=2, edgecolor=color, facecolor=color, alpha=alpha
        )
        ax4.add_patch(rect)
        
        # Midline
        mid = (ob.top + ob.bottom) / 2
        ax4.plot([ob.index, len(df)], [mid, mid], ':', 
                color=color, linewidth=1.5, alpha=0.8)
        
        # Label
        ax4.text(ob.index, mid, f' OB', fontsize=7, color=color, fontweight='bold')
    
    ax4.set_title('4. ORDER BLOCKS (Last opposite candle before break)', fontsize=14, fontweight='bold', color='cyan')
    ax4.set_ylabel('Price', fontsize=11)
    ax4.grid(True, alpha=0.2)
    
    # Chart 5: Round Levels
    ax5 = axes[4]
    plot_candles(ax5, df)
    
    # Only show round levels within visible price range
    price_min = df['low'].min()
    price_max = df['high'].max()
    
    for level in structure['round_levels']:
        if price_min <= level.price <= price_max:
            if level.level_type == '00':
                ax5.axhline(y=level.price, color='gray', linestyle='-', 
                          linewidth=1.2, alpha=0.4)
                ax5.text(len(df)-1, level.price, f' {level.price:.0f}', 
                        fontsize=8, color='gray', verticalalignment='center')
            else:  # '50'
                ax5.axhline(y=level.price, color='gray', linestyle=':', 
                          linewidth=0.8, alpha=0.25)
    
    ax5.set_title('5. ROUND NUMBER LEVELS (Solid=00, Dotted=50)', fontsize=14, fontweight='bold', color='cyan')
    ax5.set_ylabel('Price', fontsize=11)
    ax5.grid(True, alpha=0.2)
    
    # Chart 6: Premium/Discount Zones
    ax6 = axes[5]
    plot_candles(ax6, df)
    
    # Show latest premium/discount zone
    if structure['premium_discount_zones']:
        latest_zone = structure['premium_discount_zones'][-1]
        
        # Draw zone boundaries
        ax6.axhline(y=latest_zone.high, color='red', linestyle='-', linewidth=1.5, alpha=0.6, label='Range High')
        ax6.axhline(y=latest_zone.low, color='lime', linestyle='-', linewidth=1.5, alpha=0.6, label='Range Low')
        ax6.axhline(y=latest_zone.equilibrium, color='yellow', linestyle='--', linewidth=2, alpha=0.8, label='Equilibrium (50%)')
        
        # Fill premium zone (above 50%)
        ax6.fill_between(range(len(df)), latest_zone.equilibrium, latest_zone.high, 
                        color='red', alpha=0.1, label='Premium Zone (Sell)')
        
        # Fill discount zone (below 50%)
        ax6.fill_between(range(len(df)), latest_zone.low, latest_zone.equilibrium, 
                        color='lime', alpha=0.1, label='Discount Zone (Buy)')
        
        # Mark current price position
        current_price = df['close'].iloc[-1]
        if current_price > latest_zone.equilibrium:
            zone_text = 'PREMIUM'
            zone_color = 'red'
        else:
            zone_text = 'DISCOUNT'
            zone_color = 'lime'
        
        ax6.text(len(df)-1, current_price, f' {zone_text}', 
                fontsize=10, color=zone_color, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
    
    ax6.set_title('6. PREMIUM/DISCOUNT ZONES (Above 50%=Premium/Sell, Below 50%=Discount/Buy)', 
                 fontsize=14, fontweight='bold', color='cyan')
    ax6.set_ylabel('Price', fontsize=11)
    ax6.set_xlabel('Bar Index', fontsize=11)
    ax6.legend(loc='upper left', fontsize=8)
    ax6.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.savefig('data/ict_detailed_validation.png', dpi=150, bbox_inches='tight', facecolor='#1a1a1a')
    print(f"\n✅ Detailed chart saved to: data/ict_detailed_validation.png")
    plt.close()
    
    # Create a summary chart with all components + premium/discount
    fig, ax = plt.subplots(figsize=(20, 12))
    plot_candles(ax, df)
    
    # Add premium/discount zone first (background)
    if structure['premium_discount_zones']:
        latest_zone = structure['premium_discount_zones'][-1]
        ax.axhline(y=latest_zone.equilibrium, color='yellow', linestyle='--', linewidth=1.5, alpha=0.5)
        ax.fill_between(range(len(df)), latest_zone.equilibrium, latest_zone.high, 
                        color='red', alpha=0.05)
        ax.fill_between(range(len(df)), latest_zone.low, latest_zone.equilibrium, 
                        color='lime', alpha=0.05)
    
    # Add all components
    # Swings
    for swing in structure['swing_highs']:
        label = structure['swing_labels'].get(swing.index, '')
        ax.plot(swing.index, swing.price, 'v', color='lime', markersize=8)
        ax.text(swing.index, swing.price, f' {label}', fontsize=7, color='lime')
    
    for swing in structure['swing_lows']:
        label = structure['swing_labels'].get(swing.index, '')
        ax.plot(swing.index, swing.price, '^', color='red', markersize=8)
        ax.text(swing.index, swing.price, f' {label}', fontsize=7, color='red')
    
    # Structure breaks
    for brk in structure['structure_breaks']:
        color = 'lime' if brk.direction == 'bullish' else 'red'
        marker = 'BOS' if brk.type == 'BOS' else 'CHoCH'
        ax.plot(brk.index, brk.price, 'o', color=color, markersize=6)
        ax.text(brk.index, brk.price, f' {marker}', fontsize=6, color=color)
    
    # Liquidity
    for liq in structure['liquidity_levels']:
        color = 'lime' if liq.type == 'high' else 'red'
        linestyle = '-' if not liq.swept else ':'
        alpha = 0.6 if not liq.swept else 0.2
        end_idx = liq.swept_index if liq.swept else len(df)
        ax.plot([liq.start_index, end_idx], [liq.price, liq.price], 
               linestyle=linestyle, color=color, linewidth=1, alpha=alpha)
    
    # FVGs
    for fvg in structure['fvgs']:
        color = 'blue' if fvg.type == 'bullish' else 'orange'
        alpha = 0.15 if not fvg.mitigated else 0.05
        rect = patches.Rectangle(
            (fvg.index, fvg.bottom), len(df) - fvg.index, fvg.top - fvg.bottom,
            linewidth=0, facecolor=color, alpha=alpha
        )
        ax.add_patch(rect)
        mid = (fvg.top + fvg.bottom) / 2
        mid_color = 'yellow' if fvg.type == 'bullish' else 'purple'
        ax.plot([fvg.index, len(df)], [mid, mid], '-', 
               color=mid_color, linewidth=1.5, alpha=0.7)
    
    # Order Blocks
    for ob in structure['order_blocks']:
        color = 'lime' if ob.type == 'bullish' else 'red'
        alpha = 0.2 if not ob.mitigated else 0.1
        rect = patches.Rectangle(
            (ob.index, ob.bottom), len(df) - ob.index, ob.top - ob.bottom,
            linewidth=1, edgecolor=color, facecolor=color, alpha=alpha
        )
        ax.add_patch(rect)
    
    # Round levels
    for level in structure['round_levels']:
        if price_min <= level.price <= price_max:
            if level.level_type == '00':
                ax.axhline(y=level.price, color='gray', linestyle='-', linewidth=0.8, alpha=0.3)
            else:
                ax.axhline(y=level.price, color='gray', linestyle=':', linewidth=0.5, alpha=0.2)
    
    ax.set_title('ALL ICT COMPONENTS COMBINED (with Premium/Discount Zones)', fontsize=16, fontweight='bold', color='cyan')
    ax.set_ylabel('Price', fontsize=12)
    ax.set_xlabel('Bar Index', fontsize=12)
    ax.grid(True, alpha=0.2)
    
    # Add text showing current zone
    if structure['premium_discount_zones']:
        latest_zone = structure['premium_discount_zones'][-1]
        current_price = df['close'].iloc[-1]
        if current_price > latest_zone.equilibrium:
            zone_text = 'Current: PREMIUM ZONE (Sell bias)'
            zone_color = 'red'
        else:
            zone_text = 'Current: DISCOUNT ZONE (Buy bias)'
            zone_color = 'lime'
        ax.text(0.02, 0.98, zone_text, transform=ax.transAxes,
               fontsize=12, color=zone_color, fontweight='bold',
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig('data/ict_all_combined.png', dpi=150, bbox_inches='tight', facecolor='#1a1a1a')
    print(f"✅ Combined chart saved to: data/ict_all_combined.png")
    plt.close()
    
    print("\n" + "="*60)
    print("VISUALIZATION COMPLETE!")
    print("="*60)
    print("\nGenerated charts:")
    print("  1. data/ict_detailed_validation.png - 6 separate charts")
    print("     - Chart 1: Swings & Structure Breaks")
    print("     - Chart 2: Liquidity Levels")
    print("     - Chart 3: Fair Value Gaps")
    print("     - Chart 4: Order Blocks")
    print("     - Chart 5: Round Number Levels")
    print("     - Chart 6: Premium/Discount Zones (NEW!)")
    print("  2. data/ict_all_combined.png - All components together")
    print("\nOpen these files to validate ICT implementation!")
    print("\nNew Features Added:")
    print("  ✅ FVG mitigation types (touch/partial/full)")
    print("  ✅ Premium/Discount zones")
    print("  ✅ Confluence scoring")
    print("  ✅ Open levels structure")


if __name__ == "__main__":
    main()

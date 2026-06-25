"""
Simple chart visualization using matplotlib.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.dates import DateFormatter
from typing import Dict, List, Optional
from ..features.market_structure import SwingPoint, FairValueGap, OrderBlock, StructureBreak


def plot_candlestick_with_structure(df: pd.DataFrame, structure: Dict,
                                    title: str = "Market Structure",
                                    figsize: tuple = (16, 10),
                                    show_swings: bool = True,
                                    show_fvgs: bool = True,
                                    show_obs: bool = True,
                                    show_liquidity: bool = True,
                                    show_round_levels: bool = True,
                                    show_intervals: bool = True):
    """
    Plot candlestick chart with ICT market structure overlay.

    Args:
        df: OHLC dataframe
        structure: Dict from analyze_market_structure()
        title: Chart title
        figsize: Figure size
        show_swings: Show swing highs/lows
        show_fvgs: Show Fair Value Gaps
        show_obs: Show Order Blocks
        show_liquidity: Show liquidity levels
        show_round_levels: Show round number levels (00, 50)
        show_intervals: Show weekly/monthly intervals
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Plot candlesticks
    for i in range(len(df)):
        color = 'green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red'

        # Candle body
        body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
        body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
        rect = patches.Rectangle(
            (i, body_bottom), 0.6, body_height,
            linewidth=0.5, edgecolor='black', facecolor=color, alpha=0.7
        )
        ax.add_patch(rect)

        # Wicks
        ax.plot([i + 0.3, i + 0.3], [df['low'].iloc[i], df['high'].iloc[i]],
               color='black', linewidth=0.5)

    # Plot round number levels (behind everything else)
    if show_round_levels and 'round_levels' in structure:
        for level in structure['round_levels']:
            if level.level_type == '00':
                ax.axhline(y=level.price, color='gray', linestyle='-',
                          linewidth=0.8, alpha=0.2, zorder=1)
            else:  # '50'
                ax.axhline(y=level.price, color='gray', linestyle=':',
                          linewidth=0.5, alpha=0.15, zorder=1)

    # Plot weekly/monthly intervals
    if show_intervals and hasattr(df.index, 'to_period'):
        # Weekly intervals
        week_changes = df.index.to_period('W').to_timestamp()
        unique_weeks = week_changes.unique()
        for week_start in unique_weeks[1:]:  # Skip first
            idx = df.index.get_loc(week_start, method='nearest')
            ax.axvline(x=idx, color='blue', linestyle=':', linewidth=1, alpha=0.3)

        # Monthly intervals
        month_changes = df.index.to_period('M').to_timestamp()
        unique_months = month_changes.unique()
        for month_start in unique_months[1:]:  # Skip first
            idx = df.index.get_loc(month_start, method='nearest')
            ax.axvline(x=idx, color='purple', linestyle='--', linewidth=1.5, alpha=0.5)

    # Plot swing highs and lows
    if show_swings and 'swing_highs' in structure:
        for swing in structure['swing_highs']:
            label = structure['swing_labels'].get(swing.index, '')
            ax.plot(swing.index, swing.price, 'v', color='darkgreen', markersize=8)
            ax.text(swing.index, swing.price, f' {label}', fontsize=8,
                   verticalalignment='bottom')

    if show_swings and 'swing_lows' in structure:
        for swing in structure['swing_lows']:
            label = structure['swing_labels'].get(swing.index, '')
            ax.plot(swing.index, swing.price, '^', color='darkred', markersize=8)
            ax.text(swing.index, swing.price, f' {label}', fontsize=8,
                   verticalalignment='top')

    # Plot liquidity levels (from swing highs/lows)
    if show_liquidity and 'liquidity_levels' in structure:
        for liq in structure['liquidity_levels']:
            if liq.type == 'high':
                color = 'green'
                linestyle = '--' if not liq.swept else ':'
                alpha = 0.6 if not liq.swept else 0.3
                end_idx = liq.swept_index if liq.swept else len(df)
            else:  # 'low'
                color = 'red'
                linestyle = '--' if not liq.swept else ':'
                alpha = 0.6 if not liq.swept else 0.3
                end_idx = liq.swept_index if liq.swept else len(df)

            ax.plot([liq.start_index, end_idx], [liq.price, liq.price],
                   linestyle=linestyle, color=color, linewidth=1.5, alpha=alpha, zorder=3)

            # Mark sweep point
            if liq.swept:
                ax.plot(liq.swept_index, liq.price, 'x', color=color,
                       markersize=8, markeredgewidth=2, zorder=4)

    # Plot FVGs with emphasized 50% midpoint
    if show_fvgs and 'fvgs' in structure:
        for fvg in structure['fvgs']:
            color = 'blue' if fvg.type == 'bullish' else 'orange'
            alpha = 0.2 if not fvg.mitigated else 0.1
            rect = patches.Rectangle(
                (fvg.index, fvg.bottom), len(df) - fvg.index, fvg.top - fvg.bottom,
                linewidth=0, facecolor=color, alpha=alpha
            )
            ax.add_patch(rect)

            # 50% Midline - EMPHASIZED
            mid = (fvg.top + fvg.bottom) / 2
            mid_color = 'yellow' if fvg.type == 'bullish' else 'purple'
            ax.plot([fvg.index, len(df)], [mid, mid], '-',
                   color=mid_color, linewidth=2, alpha=0.8, zorder=5)

    # Plot Order Blocks
    if show_obs and 'order_blocks' in structure:
        for ob in structure['order_blocks']:
            color = 'green' if ob.type == 'bullish' else 'red'
            alpha = 0.3 if not ob.mitigated else 0.15
            rect = patches.Rectangle(
                (ob.index, ob.bottom), len(df) - ob.index, ob.top - ob.bottom,
                linewidth=1, edgecolor=color, facecolor=color, alpha=alpha
            )
            ax.add_patch(rect)

            # Midline
            mid = (ob.top + ob.bottom) / 2
            ax.plot([ob.index, len(df)], [mid, mid], ':',
                   color=color, linewidth=1, alpha=0.7)

    # Plot old liquidity sweeps (for backward compatibility)
    if show_liquidity and 'swept_highs' in structure:
        for swing in structure['swept_highs']:
            ax.axhline(y=swing.price, color='green', linestyle='--',
                      linewidth=0.5, alpha=0.5)

    if show_liquidity and 'swept_lows' in structure:
        for swing in structure['swept_lows']:
            ax.axhline(y=swing.price, color='red', linestyle='--',
                      linewidth=0.5, alpha=0.5)

    # Plot structure breaks
    if 'structure_breaks' in structure:
        for brk in structure['structure_breaks']:
            color = 'green' if brk.direction == 'bullish' else 'red'
            marker = 'BOS' if brk.type == 'BOS' else 'CHoCH'
            ax.plot(brk.index, brk.price, 'o', color=color, markersize=6)
            ax.text(brk.index, brk.price, f' {marker}', fontsize=7, color=color)

    # Plot open levels
    if 'open_levels' in structure:
        if 'daily_open' in structure['open_levels']:
            ax.plot(range(len(df)), structure['open_levels']['daily_open'],
                   '--', color='yellow', linewidth=1, alpha=0.5, label='Daily Open')
        if 'weekly_open' in structure['open_levels']:
            ax.plot(range(len(df)), structure['open_levels']['weekly_open'],
                   '--', color='orange', linewidth=1, alpha=0.5, label='Weekly Open')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('Bar Index')
    ax.set_ylabel('Price')
    ax.grid(True, alpha=0.3)
    if 'open_levels' in structure:
        ax.legend(loc='upper left')

    plt.tight_layout()
    return fig, ax


def plot_equity_curve(result, title: str = "Equity Curve", figsize: tuple = (12, 6)):
    """
    Plot equity curve from backtest result.
    
    Args:
        result: BacktestResult object
        title: Chart title
        figsize: Figure size
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, height_ratios=[3, 1])
    
    # Equity curve
    ax1.plot(result.equity_curve.index, result.equity_curve.values, 
            linewidth=2, color='blue', label='Equity')
    ax1.axhline(y=result.initial_capital, color='gray', linestyle='--', 
               linewidth=1, alpha=0.5, label='Initial Capital')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.set_ylabel('Capital ($)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Drawdown
    cummax = result.equity_curve.cummax()
    drawdown = (result.equity_curve - cummax) / cummax * 100
    ax2.fill_between(drawdown.index, drawdown.values, 0, 
                     color='red', alpha=0.3, label='Drawdown')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    return fig, (ax1, ax2)


def plot_trade_distribution(result, figsize: tuple = (12, 8)):
    """
    Plot trade distribution and statistics.
    
    Args:
        result: BacktestResult object
        figsize: Figure size
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
    
    # P&L distribution
    pnls = [t.pnl for t in result.trades if t.pnl is not None]
    ax1.hist(pnls, bins=30, color='blue', alpha=0.7, edgecolor='black')
    ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
    ax1.set_title('P&L Distribution')
    ax1.set_xlabel('P&L ($)')
    ax1.set_ylabel('Frequency')
    ax1.grid(True, alpha=0.3)
    
    # Win/Loss pie chart
    wins = result.winning_trades
    losses = result.losing_trades
    ax2.pie([wins, losses], labels=['Wins', 'Losses'], autopct='%1.1f%%',
           colors=['green', 'red'], startangle=90)
    ax2.set_title(f'Win Rate: {result.win_rate:.1f}%')
    
    # MAE/MFE scatter
    maes = [t.mae for t in result.trades if t.pnl is not None]
    mfes = [t.mfe for t in result.trades if t.pnl is not None]
    colors = ['green' if t.is_winner else 'red' for t in result.trades if t.pnl is not None]
    ax3.scatter(maes, mfes, c=colors, alpha=0.6)
    ax3.set_title('MAE vs MFE')
    ax3.set_xlabel('MAE (Max Adverse Excursion)')
    ax3.set_ylabel('MFE (Max Favorable Excursion)')
    ax3.grid(True, alpha=0.3)
    
    # Trade duration
    durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 
                for t in result.trades if t.exit_time is not None]
    ax4.hist(durations, bins=20, color='purple', alpha=0.7, edgecolor='black')
    ax4.set_title('Trade Duration Distribution')
    ax4.set_xlabel('Duration (hours)')
    ax4.set_ylabel('Frequency')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig, ((ax1, ax2), (ax3, ax4))


def plot_component_analysis(df: pd.DataFrame, structure: Dict, figsize: tuple = (16, 12)):
    """
    Plot separate charts for each ICT component for better visibility.

    Args:
        df: OHLC dataframe
        structure: Dict from analyze_market_structure()
        figsize: Figure size
    """
    fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)

    # Helper function to plot candlesticks
    def plot_candles(ax, df):
        for i in range(len(df)):
            color = 'green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red'
            body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
            body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
            rect = patches.Rectangle(
                (i, body_bottom), 0.6, body_height,
                linewidth=0.5, edgecolor='black', facecolor=color, alpha=0.5
            )
            ax.add_patch(rect)
            ax.plot([i + 0.3, i + 0.3], [df['low'].iloc[i], df['high'].iloc[i]],
                   color='black', linewidth=0.5, alpha=0.5)

    # Chart 1: Swings & Structure Breaks
    ax1 = axes[0]
    plot_candles(ax1, df)

    if 'swing_highs' in structure:
        for swing in structure['swing_highs']:
            label = structure['swing_labels'].get(swing.index, '')
            ax1.plot(swing.index, swing.price, 'v', color='darkgreen', markersize=10)
            ax1.text(swing.index, swing.price, f' {label}', fontsize=9,
                    verticalalignment='bottom', fontweight='bold')

    if 'swing_lows' in structure:
        for swing in structure['swing_lows']:
            label = structure['swing_labels'].get(swing.index, '')
            ax1.plot(swing.index, swing.price, '^', color='darkred', markersize=10)
            ax1.text(swing.index, swing.price, f' {label}', fontsize=9,
                    verticalalignment='top', fontweight='bold')

    if 'structure_breaks' in structure:
        for brk in structure['structure_breaks']:
            color = 'green' if brk.direction == 'bullish' else 'red'
            marker = 'BOS' if brk.type == 'BOS' else 'CHoCH'
            ax1.plot(brk.index, brk.price, 'o', color=color, markersize=8)
            ax1.text(brk.index, brk.price, f' {marker}', fontsize=8, color=color, fontweight='bold')

    ax1.set_title('Swings & Structure Breaks (BOS/CHoCH)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Price')
    ax1.grid(True, alpha=0.3)

    # Chart 2: Fair Value Gaps
    ax2 = axes[1]
    plot_candles(ax2, df)

    if 'fvgs' in structure:
        for fvg in structure['fvgs']:
            color = 'blue' if fvg.type == 'bullish' else 'orange'
            alpha = 0.3 if not fvg.mitigated else 0.15
            rect = patches.Rectangle(
                (fvg.index, fvg.bottom), len(df) - fvg.index, fvg.top - fvg.bottom,
                linewidth=1, edgecolor=color, facecolor=color, alpha=alpha
            )
            ax2.add_patch(rect)

            mid = (fvg.top + fvg.bottom) / 2
            ax2.plot([fvg.index, len(df)], [mid, mid], '--',
                    color=color, linewidth=1, alpha=0.7)

    ax2.set_title('Fair Value Gaps (FVG)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Price')
    ax2.grid(True, alpha=0.3)

    # Chart 3: Order Blocks
    ax3 = axes[2]
    plot_candles(ax3, df)

    if 'order_blocks' in structure:
        for ob in structure['order_blocks']:
            color = 'green' if ob.type == 'bullish' else 'red'
            alpha = 0.4 if not ob.mitigated else 0.2
            rect = patches.Rectangle(
                (ob.index, ob.bottom), len(df) - ob.index, ob.top - ob.bottom,
                linewidth=2, edgecolor=color, facecolor=color, alpha=alpha
            )
            ax3.add_patch(rect)

            mid = (ob.top + ob.bottom) / 2
            ax3.plot([ob.index, len(df)], [mid, mid], ':',
                    color=color, linewidth=1.5, alpha=0.8)

    ax3.set_title('Order Blocks (OB)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Price')
    ax3.grid(True, alpha=0.3)

    # Chart 4: Liquidity & Open Levels
    ax4 = axes[3]
    plot_candles(ax4, df)

    if 'swept_highs' in structure:
        for swing in structure['swept_highs']:
            ax4.axhline(y=swing.price, color='green', linestyle='--',
                       linewidth=1, alpha=0.6, label='Swept High')

    if 'swept_lows' in structure:
        for swing in structure['swept_lows']:
            ax4.axhline(y=swing.price, color='red', linestyle='--',
                       linewidth=1, alpha=0.6, label='Swept Low')

    if 'open_levels' in structure:
        if 'daily_open' in structure['open_levels']:
            ax4.plot(range(len(df)), structure['open_levels']['daily_open'],
                    '--', color='yellow', linewidth=1.5, alpha=0.7, label='Daily Open')
        if 'weekly_open' in structure['open_levels']:
            ax4.plot(range(len(df)), structure['open_levels']['weekly_open'],
                    '--', color='orange', linewidth=1.5, alpha=0.7, label='Weekly Open')

    ax4.set_title('Liquidity & Open Levels', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Bar Index')
    ax4.set_ylabel('Price')
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc='upper left', fontsize=8)

    plt.tight_layout()
    return fig, axes


def plot_monte_carlo_results(mc_results: Dict, figsize: tuple = (12, 8)):
    """
    Plot Monte Carlo simulation results.

    Args:
        mc_results: Dict from BacktestResult.monte_carlo_simulation()
        figsize: Figure size
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)

    # Return distribution (would need individual sim results - simplified here)
    ax1.text(0.5, 0.5, f"Mean Return: {mc_results['mean_return']:.2f}%\n"
                       f"Median Return: {mc_results['median_return']:.2f}%\n"
                       f"Std Dev: {mc_results['std_return']:.2f}%",
            ha='center', va='center', fontsize=12, transform=ax1.transAxes)
    ax1.set_title('Return Statistics')
    ax1.axis('off')

    # Percentile ranges
    categories = ['5th %ile', 'Median', '95th %ile']
    values = [mc_results['percentile_5'], mc_results['median_return'], mc_results['percentile_95']]
    colors = ['red' if v < 0 else 'green' for v in values]
    ax2.bar(categories, values, color=colors, alpha=0.7)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_title('Return Percentiles')
    ax2.set_ylabel('Return (%)')
    ax2.grid(True, alpha=0.3, axis='y')

    # Drawdown stats
    ax3.text(0.5, 0.5, f"Mean Max DD: {mc_results['mean_max_dd']:.2f}%\n"
                       f"Worst DD: {mc_results['worst_dd']:.2f}%",
            ha='center', va='center', fontsize=12, transform=ax3.transAxes)
    ax3.set_title('Drawdown Statistics')
    ax3.axis('off')

    # Probability of profit
    prob_profit = mc_results['prob_profit']
    prob_loss = 100 - prob_profit
    ax4.pie([prob_profit, prob_loss], labels=['Profit', 'Loss'],
           autopct='%1.1f%%', colors=['green', 'red'], startangle=90)
    ax4.set_title(f"Probability of Profit: {prob_profit:.1f}%")

    plt.tight_layout()
    return fig, ((ax1, ax2), (ax3, ax4))



def save_chart(fig, filename: str, dpi: int = 150):
    """Save chart to file."""
    fig.savefig(filename, dpi=dpi, bbox_inches='tight')
    print(f"Chart saved to {filename}")

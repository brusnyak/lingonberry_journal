"""
Core backtesting engine for strategy evaluation.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    direction: str = 'long'  # 'long' or 'short'
    size: float = 1.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion
    
    def close(self, exit_time: pd.Timestamp, exit_price: float, reason: str = 'signal'):
        """Close the trade and calculate P&L."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        
        if self.direction == 'long':
            self.pnl = (exit_price - self.entry_price) * self.size
            self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            self.pnl = (self.entry_price - exit_price) * self.size
            self.pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * 100
    
    def update_excursions(self, current_price: float):
        """Update MAE and MFE during trade."""
        if self.direction == 'long':
            excursion = current_price - self.entry_price
        else:
            excursion = self.entry_price - current_price
        
        # Update MFE (best price)
        if excursion > self.mfe:
            self.mfe = excursion
        
        # Update MAE (worst price)
        if excursion < self.mae:
            self.mae = excursion
    
    @property
    def is_open(self) -> bool:
        """Check if trade is still open."""
        return self.exit_time is None
    
    @property
    def is_winner(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl is not None and self.pnl > 0


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 10000.0
    final_capital: float = 10000.0
    
    @property
    def total_trades(self) -> int:
        return len(self.trades)
    
    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.is_winner)
    
    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if not t.is_winner and t.pnl is not None)
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades if t.pnl is not None)
    
    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self.trades if t.is_winner]
        return np.mean(wins) if wins else 0.0
    
    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self.trades if not t.is_winner and t.pnl is not None]
        return np.mean(losses) if losses else 0.0
    
    @property
    def avg_rr(self) -> float:
        """Average Risk/Reward ratio."""
        rr_ratios = []
        for t in self.trades:
            if t.pnl is not None and t.stop_loss is not None:
                if t.direction == 'long':
                    risk = t.entry_price - t.stop_loss
                else:
                    risk = t.stop_loss - t.entry_price
                
                if risk > 0:
                    reward = abs(t.pnl / risk) if t.pnl != 0 else 0
                    rr_ratios.append(reward)
        
        return np.mean(rr_ratios) if rr_ratios else 0.0
    
    @property
    def expectancy(self) -> float:
        """Expected value per trade."""
        if self.total_trades == 0:
            return 0.0
        return (self.win_rate / 100 * self.avg_win) + ((100 - self.win_rate) / 100 * self.avg_loss)
    
    @property
    def profit_factor(self) -> float:
        """Ratio of gross profit to gross loss."""
        gross_profit = sum(t.pnl for t in self.trades if t.is_winner)
        gross_loss = abs(sum(t.pnl for t in self.trades if not t.is_winner and t.pnl is not None))
        return gross_profit / gross_loss if gross_loss > 0 else 0.0
    
    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown from peak."""
        if len(self.equity_curve) == 0:
            return 0.0
        
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax * 100
        return abs(drawdown.min())
    
    @property
    def sharpe_ratio(self) -> float:
        """Sharpe ratio (assuming 0% risk-free rate)."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = self.equity_curve.pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        
        return (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
    
    def summary(self) -> Dict:
        """Get summary statistics."""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'total_return_pct': ((self.final_capital - self.initial_capital) / self.initial_capital) * 100,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'avg_rr': self.avg_rr,
            'expectancy': self.expectancy,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio
        }
    
    def monte_carlo_simulation(self, n_simulations: int = 1000, n_trades: int = None) -> Dict:
        """
        Run Monte Carlo simulation by randomly resampling trades.
        
        Args:
            n_simulations: Number of simulations to run
            n_trades: Number of trades per simulation (default: same as actual)
        
        Returns:
            Dict with simulation results
        """
        if not self.trades:
            return {}
        
        if n_trades is None:
            n_trades = len(self.trades)
        
        trade_returns = [t.pnl for t in self.trades if t.pnl is not None]
        
        if not trade_returns:
            return {}
        
        simulation_results = []
        
        for _ in range(n_simulations):
            # Randomly sample trades with replacement
            sampled_returns = np.random.choice(trade_returns, size=n_trades, replace=True)
            
            # Calculate equity curve
            equity = self.initial_capital + np.cumsum(sampled_returns)
            
            # Calculate metrics
            final_capital = equity[-1]
            total_return = ((final_capital - self.initial_capital) / self.initial_capital) * 100
            
            # Max drawdown
            cummax = np.maximum.accumulate(equity)
            drawdown = (equity - cummax) / cummax * 100
            max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
            
            simulation_results.append({
                'final_capital': final_capital,
                'total_return': total_return,
                'max_drawdown': max_dd
            })
        
        # Aggregate results
        returns = [r['total_return'] for r in simulation_results]
        drawdowns = [r['max_drawdown'] for r in simulation_results]
        
        return {
            'n_simulations': n_simulations,
            'mean_return': np.mean(returns),
            'median_return': np.median(returns),
            'std_return': np.std(returns),
            'min_return': np.min(returns),
            'max_return': np.max(returns),
            'percentile_5': np.percentile(returns, 5),
            'percentile_95': np.percentile(returns, 95),
            'mean_max_dd': np.mean(drawdowns),
            'worst_dd': np.max(drawdowns),
            'prob_profit': (np.array(returns) > 0).sum() / len(returns) * 100
        }


class BacktestEngine:
    """
    Backtesting engine for strategy evaluation.
    
    Supports:
    - Long and short positions
    - Stop loss and take profit
    - Position sizing (fixed, percent risk, Kelly)
    - Walk-forward optimization
    """
    
    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.001,
                 risk_per_trade: float = 0.02, position_sizing: str = 'risk_pct',
                 slippage: float = 0.0):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital
            commission: Commission per trade (as decimal, e.g., 0.001 = 0.1%)
            risk_per_trade: Risk per trade as decimal (e.g., 0.02 = 2%)
            position_sizing: 'fixed', 'risk_pct', or 'kelly'
            slippage: Slippage per trade (as decimal, e.g., 0.0002 = 0.02%)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.risk_per_trade = risk_per_trade
        self.position_sizing = position_sizing
        self.slippage = slippage
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.current_trade: Optional[Trade] = None
        self.equity_curve = []
        self.peak_capital = initial_capital
        self.closed_trades = []  # Add this for compatibility
    
    def reset(self):
        """Reset engine state."""
        self.capital = self.initial_capital
        self.trades = []
        self.current_trade = None
        self.equity_curve = []
        self.peak_capital = self.initial_capital
    
    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk management.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Position size
        """
        if self.position_sizing == 'fixed':
            return 1.0
        
        elif self.position_sizing == 'risk_pct':
            # Risk-based position sizing
            risk_amount = self.capital * self.risk_per_trade
            price_risk = abs(entry_price - stop_loss)
            
            if price_risk == 0:
                return 1.0
            
            # Position size = Risk Amount / Price Risk
            position_size = risk_amount / price_risk
            
            # Cap at available capital
            max_size = self.capital / entry_price
            return min(position_size, max_size)
        
        elif self.position_sizing == 'kelly':
            # Kelly Criterion (simplified)
            if len(self.trades) < 10:
                return self.calculate_position_size(entry_price, stop_loss)  # Use risk_pct initially
            
            wins = [t for t in self.trades if t.is_winner]
            losses = [t for t in self.trades if not t.is_winner and t.pnl is not None]
            
            if not wins or not losses:
                return 1.0
            
            win_rate = len(wins) / len(self.trades)
            avg_win = sum(t.pnl for t in wins) / len(wins)
            avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
            
            if avg_loss == 0:
                return 1.0
            
            # Kelly % = W - (1-W) / (AvgWin/AvgLoss)
            kelly_pct = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
            kelly_pct = max(0, min(kelly_pct, 0.25))  # Cap at 25%
            
            return (self.capital * kelly_pct) / entry_price
        
        return 1.0
    
    def open_trade(self, time: pd.Timestamp, price: float, direction: str = 'long',
                   size: Optional[float] = None, stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None):
        """
        Open a new trade.
        
        Args:
            time: Entry timestamp
            price: Entry price
            direction: 'long' or 'short'
            size: Position size (if None, calculated automatically)
            stop_loss: Stop loss price
            take_profit: Take profit price
        """
        if self.current_trade is not None:
            return  # Already in a trade
        
        # Apply slippage to entry price
        if direction == 'long':
            price = price * (1 + self.slippage)  # Buy higher
        else:
            price = price * (1 - self.slippage)  # Sell lower
        
        # Calculate position size if not provided
        if size is None and stop_loss is not None:
            size = self.calculate_position_size(price, stop_loss)
        elif size is None:
            size = 1.0
        
        # Apply commission
        commission_cost = price * size * self.commission
        self.capital -= commission_cost
        
        self.current_trade = Trade(
            entry_time=time,
            entry_price=price,
            direction=direction,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def close_trade(self, time: pd.Timestamp, price: float, reason: str = 'signal'):
        """
        Close current trade.
        
        Args:
            time: Exit timestamp
            price: Exit price
            reason: Exit reason ('signal', 'stop_loss', 'take_profit', 'end_of_data')
        """
        if self.current_trade is None:
            return
        
        # Apply slippage to exit price
        if self.current_trade.direction == 'long':
            price = price * (1 - self.slippage)  # Sell lower
        else:
            price = price * (1 + self.slippage)  # Buy higher (to close short)
        
        # Apply commission
        commission_cost = price * self.current_trade.size * self.commission
        self.capital -= commission_cost
        
        # Close trade
        self.current_trade.close(time, price, reason)
        
        # Update capital
        self.capital += self.current_trade.pnl
        
        # Track peak capital for drawdown
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        # Store trade
        self.trades.append(self.current_trade)
        self.closed_trades.append(self.current_trade)  # Add to closed_trades list
        self.current_trade = None
    
    def update(self, time: pd.Timestamp, high: float, low: float, close: float):
        """
        Update engine state with new bar.
        
        Checks stop loss and take profit.
        
        Args:
            time: Current timestamp
            high: Bar high
            low: Bar low
            close: Bar close
        """
        if self.current_trade is None:
            self.equity_curve.append((time, self.capital))
            return
        
        # Update excursions
        self.current_trade.update_excursions(close)
        
        # Check stop loss
        if self.current_trade.stop_loss is not None:
            if self.current_trade.direction == 'long' and low <= self.current_trade.stop_loss:
                self.close_trade(time, self.current_trade.stop_loss, 'stop_loss')
                return
            elif self.current_trade.direction == 'short' and high >= self.current_trade.stop_loss:
                self.close_trade(time, self.current_trade.stop_loss, 'stop_loss')
                return
        
        # Check take profit
        if self.current_trade.take_profit is not None:
            if self.current_trade.direction == 'long' and high >= self.current_trade.take_profit:
                self.close_trade(time, self.current_trade.take_profit, 'take_profit')
                return
            elif self.current_trade.direction == 'short' and low <= self.current_trade.take_profit:
                self.close_trade(time, self.current_trade.take_profit, 'take_profit')
                return
        
        # Update equity curve with unrealized P&L
        if self.current_trade.direction == 'long':
            unrealized_pnl = (close - self.current_trade.entry_price) * self.current_trade.size
        else:
            unrealized_pnl = (self.current_trade.entry_price - close) * self.current_trade.size
        
        self.equity_curve.append((time, self.capital + unrealized_pnl))
    
    def run(self, df: pd.DataFrame, strategy: Callable) -> BacktestResult:
        """
        Run backtest on dataframe using strategy function.
        
        Args:
            df: OHLC dataframe
            strategy: Function that takes (engine, df, i) and generates signals
        
        Returns:
            BacktestResult object
        """
        self.reset()
        
        for i in range(len(df)):
            # Update engine state
            self.update(
                df.index[i],
                df['high'].iloc[i],
                df['low'].iloc[i],
                df['close'].iloc[i]
            )
            
            # Run strategy logic
            strategy(self, df, i)
        
        # Close any open trade at end
        if self.current_trade is not None:
            self.close_trade(df.index[-1], df['close'].iloc[-1], 'end_of_data')
        
        # Create result
        equity_series = pd.Series(
            [eq[1] for eq in self.equity_curve],
            index=[eq[0] for eq in self.equity_curve]
        )
        
        return BacktestResult(
            trades=self.trades,
            equity_curve=equity_series,
            initial_capital=self.initial_capital,
            final_capital=self.capital
        )

    def run_rolling_windows(self, df: pd.DataFrame, strategy: Callable,
                           window_days: int = 60) -> List[BacktestResult]:
        """
        Run backtest on rolling time windows.
        
        Args:
            df: OHLC dataframe
            strategy: Strategy function
            window_days: Window size in days
        
        Returns:
            List of BacktestResult objects (one per window)
        """
        results = []
        
        # Calculate window size in bars (approximate)
        if len(df) < 100:
            return [self.run(df, strategy)]
        
        # Determine timeframe from index
        time_diff = (df.index[1] - df.index[0]).total_seconds() / 60  # minutes
        bars_per_day = 1440 / time_diff if time_diff > 0 else 96  # Default to 15m
        window_bars = int(window_days * bars_per_day)
        
        # Run on each window
        start_idx = 0
        while start_idx < len(df):
            end_idx = min(start_idx + window_bars, len(df))
            window_df = df.iloc[start_idx:end_idx]
            
            if len(window_df) < 50:  # Skip if too small
                break
            
            # Reset and run
            self.reset()
            result = self.run(window_df, strategy)
            results.append(result)
            
            # Move window forward (50% overlap)
            start_idx += window_bars // 2
        
        return results

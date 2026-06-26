"""
Strategy abstract base class.

Usage:
    class MyStrategy(Strategy):
        def init(self, data):
            self.df_1m = data["1"]
            self.df_15m = data["15"]
            # pre-compute labels, FVGs etc. here

        def next(self, i, bar, state):
            # bar = (ts, open, high, low, close, volume) as named tuple
            # state = EngineState (equity, open_positions, etc.)
            # return Signal(...) to open a trade, or None to do nothing
            return None

        def on_close(self, trade, state):
            # optional hook called after each trade closes
            pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .orders import Signal


class BarData:
    """Single bar of OHLCV data passed to next()."""
    __slots__ = ("ts", "open", "high", "low", "close", "volume", "index")

    def __init__(self, ts, open_, high, low, close, volume, index: int):
        self.ts = ts
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.index = index


class EngineState:
    """Snapshot of engine state visible to strategy.next()."""
    __slots__ = ("equity", "initial_equity", "open_positions", "closed_trades", "bar_index")

    def __init__(self, equity: float, initial_equity: float, open_positions: list, closed_trades: list, bar_index: int):
        self.equity = equity
        self.initial_equity = initial_equity
        self.open_positions = open_positions
        self.closed_trades = closed_trades
        self.bar_index = bar_index

    @property
    def drawdown_pct(self) -> float:
        return (self.initial_equity - self.equity) / self.initial_equity

    @property
    def has_open_position(self) -> bool:
        return len(self.open_positions) > 0


class Strategy(ABC):
    """Base class for all backtested strategies."""

    def __init__(self) -> None:
        self._pending_sl_update: Optional[tuple[int, float]] = None

    def init(self, data: dict[str, object]) -> None:
        """
        Called once before the bar loop.

        data: dict keyed by timeframe string → pd.DataFrame
              e.g. {"1": df_1m, "15": df_15m, "240": df_4h}

        Pre-compute any indicators or labels here. Store them as instance
        attributes so next() can index into them by bar index.
        """

    @abstractmethod
    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        """
        Called on every bar of the entry timeframe.

        Return a Signal to open a trade, or None to wait.
        Never look ahead: only access data up to bar.index.
        """

    def post_bar(self, bar: BarData, state: EngineState) -> None:
        """
        Called on EVERY bar, even when next() is skipped due to max positions.

        Override to implement position monitoring, structure-based trailing,
        early exit on structure break, or pre-entry analysis.

        The runner calls post_bar() after exit checks but before next().
        Use update_sl() here to adjust stops — it will be applied on the
        next bar's exit check.

        Default: no-op.
        """

    def on_close(self, trade: object, state: EngineState) -> None:
        """Called after each trade is closed. Override for custom logging."""

    def on_partial(self, trade: object, state: EngineState) -> None:
        """Called after each partial close (TP1, TP2). Override if needed."""

    def update_sl(self, pos_id: int, new_sl: float) -> None:
        """
        Request the runner to move an open position's stop-loss.

        Called from within next(). The runner applies the update before
        exit checks on the following bar (one bar delay for safety).

        Parameters
        ----------
        pos_id : int
            ID of the open position to modify.
        new_sl : float
            New stop-loss price.
        """
        self._pending_sl_update = (pos_id, new_sl)

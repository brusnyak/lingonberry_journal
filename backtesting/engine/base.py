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
    """Base class for all backtested strategies.

    Declare _signal_source to document where trade decisions are made:
      "next" (default) — signals generated bar-by-bar in next(). Safe.
      "init_precomputed" — indicators/labels pre-computed in init() with
        shift(1) or similar causal windowing; trade decisions still in next().
        Safe when done correctly.
      "init_signals" — full trade signals (entry, sl, tp) pre-computed in
        init() on the complete dataset. HIGH RISK of look-ahead bias unless
        every future-referencing function is explicitly bounded (e.g. by
        truncating data to current bar index inside next()).

    The engine calls _check_lookahead_risk() after init() and warns if it
    detects pre-computed signal-like data without an explicit declaration.
    """

    _signal_source: str = "next"

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

    def on_close(self, trade: object, state: EngineState) -> None:
        """Called after each trade is closed. Override for custom logging."""

    def on_partial(self, trade: object, state: EngineState) -> None:
        """Called after each partial close (TP1, TP2). Override if needed."""

    def should_close(self, position: object, bar: BarData, state: EngineState) -> bool:
        """Return True to close a position at the current bar close."""
        return False

    def _check_lookahead_risk(self) -> None:
        """Post-init heuristic check for potential look-ahead bias.

        Scans for pre-computed signal-like objects stored in init().
        This is a best-effort warning — it can't prove absence of
        look-ahead, but it flags the pattern we found in TrIct.
        """
        import warnings

        # If the author has explicitly declared the signal source, trust that.
        if self._signal_source in ("next", "init_precomputed"):
            return

        for attr_name in dir(self):
            if attr_name.startswith("__"):
                continue
            attr = getattr(self, attr_name, None)
            if attr is None or not isinstance(attr, (list, tuple)):
                continue
            if len(attr) == 0:
                continue
            item = attr[0]
            # Duck-type: does it look like a trade signal?
            if hasattr(item, "signal_time") or hasattr(item, "entry_price"):
                warnings.warn(
                    f"{type(self).__name__}.{attr_name}: pre-computed trade "
                    f"signals in init() with _signal_source='{self._signal_source}'. "
                    f"Set _signal_source='init_signals' to acknowledge the risk, "
                    f"or better: move decision logic into next(). "
                    f"This pattern was the source of confirmed look-ahead bias "
                    f"in TrIct (see audit 2026-07-04).",
                    stacklevel=2,
                )
                return

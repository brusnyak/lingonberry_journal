"""
Backtesting runner.

Architecture:
  run() — Python loop per bar
    ├─ _check_exits_nb() — numba-compiled SL/TP/trail checks (hot path)
    └─ strategy.next()   — Python strategy callback

The numba function operates on a fixed-size position state array so it can
be JIT-compiled without Python objects. Position management (partials,
trailing, BE) happens in the Python layer after numba signals which positions
to close and at what price.

Usage:
    from backtesting.engine.runner import run
    from backtesting.engine.data import load_data
    from backtesting.engine.costs import ForexCosts
    from backtesting.strategies.smc_v1 import SmcV1

    data = {"1": load_data("EURUSD", "1", days=30),
            "15": load_data("EURUSD", "15", days=30),
            "240": load_data("EURUSD", "240", days=30)}

    result = run(SmcV1(), data, entry_tf="1", costs=ForexCosts(), initial_equity=10_000)
    print(result.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .base import BarData, EngineState, Strategy
from .costs import CostModel, ForexCosts
from .orders import ClosedTrade, Direction, ExitReason, Position, Signal
from . import metrics as metrics_mod


# ── Numba position-exit checker ───────────────────────────────────────────────

try:
    from numba import njit as _njit
    _NUMBA = True
except ImportError:
    _NUMBA = False

    def _njit(fn):
        return fn


# Position state columns (flat numpy array per position):
# [0] direction   (+1 long, -1 short)
# [1] entry_price
# [2] sl
# [3] tp1
# [4] tp2         (0 = none)
# [5] tp3         (0 = none)
# [6] trail_stop  (0 = inactive)
# [7] tp1_hit     (0/1)
# [8] tp2_hit     (0/1)
_POS_DIR   = 0
_POS_ENTRY = 1
_POS_SL    = 2
_POS_TP1   = 3
_POS_TP2   = 4
_POS_TP3   = 5
_POS_TRAIL = 6
_POS_TP1HIT = 7
_POS_TP2HIT = 8


@_njit
def _check_exits_nb(
    states: np.ndarray,   # shape (n_pos, 9)
    bar_o: float,
    bar_h: float,
    bar_l: float,
    bar_c: float,
) -> np.ndarray:
    """
    For each open position, determine if SL/TP was hit this bar.

    Returns result array shape (n_pos, 3):
      col 0: exit_code  (0=none, 1=sl, 2=tp1, 3=tp2, 4=tp3, 5=trail)
      col 1: fill_price (0 if no exit)
      col 2: is_sl      (1 if stop hit, 0 otherwise)
    """
    n = states.shape[0]
    result = np.zeros((n, 3), dtype=np.float64)

    for i in range(n):
        d = states[i, _POS_DIR]
        sl = states[i, _POS_SL]
        tp1 = states[i, _POS_TP1]
        tp2 = states[i, _POS_TP2]
        tp3 = states[i, _POS_TP3]
        trail = states[i, _POS_TRAIL]
        tp1_hit = states[i, _POS_TP1HIT]
        tp2_hit = states[i, _POS_TP2HIT]

        if d == 1:  # LONG
            # SL hit
            if bar_l <= sl:
                result[i, 0] = 1.0   # SL
                result[i, 1] = sl
                result[i, 2] = 1.0
                continue

            # Trail stop (active after TP1)
            if trail > 0.0 and bar_l <= trail:
                result[i, 0] = 5.0   # TRAIL
                result[i, 1] = trail
                result[i, 2] = 1.0
                continue

            # TP sequence
            if tp1_hit == 0.0 and tp1 > 0.0 and bar_h >= tp1:
                result[i, 0] = 2.0   # TP1
                result[i, 1] = tp1
                continue
            if tp1_hit == 1.0 and tp2_hit == 0.0 and tp2 > 0.0 and bar_h >= tp2:
                result[i, 0] = 3.0   # TP2
                result[i, 1] = tp2
                continue
            if tp2_hit == 1.0 and tp3 > 0.0 and bar_h >= tp3:
                result[i, 0] = 4.0   # TP3
                result[i, 1] = tp3
                continue

        else:  # SHORT
            # SL hit
            if bar_h >= sl:
                result[i, 0] = 1.0
                result[i, 1] = sl
                result[i, 2] = 1.0
                continue

            # Trail stop
            if trail > 0.0 and bar_h >= trail:
                result[i, 0] = 5.0
                result[i, 1] = trail
                result[i, 2] = 1.0
                continue

            # TP sequence
            if tp1_hit == 0.0 and tp1 > 0.0 and bar_l <= tp1:
                result[i, 0] = 2.0
                result[i, 1] = tp1
                continue
            if tp1_hit == 1.0 and tp2_hit == 0.0 and tp2 > 0.0 and bar_l <= tp2:
                result[i, 0] = 3.0
                result[i, 1] = tp2
                continue
            if tp2_hit == 1.0 and tp3 > 0.0 and bar_l <= tp3:
                result[i, 0] = 4.0
                result[i, 1] = tp3
                continue

    return result


# ── BacktestResult ────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    trades: list[ClosedTrade]
    report: dict
    elapsed_s: float
    n_bars: int

    def summary(self) -> str:
        lines = [
            f"Bars: {self.n_bars:,}  |  Time: {self.elapsed_s:.2f}s",
            metrics_mod.summary_str(self.report),
        ]
        return "\n".join(lines)

    def to_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        rows = []
        for t in self.trades:
            rows.append({
                "id": t.id,
                "direction": t.direction.value if hasattr(t.direction, "value") else t.direction,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "exit_reason": t.exit_reason.value if hasattr(t.exit_reason, "value") else t.exit_reason,
                "lots": t.lots,
                "pnl": t.pnl,
                "r_multiple": t.r_multiple,
                "label": t.label,
            })
        return pd.DataFrame(rows)


# ── Runner ────────────────────────────────────────────────────────────────────

def run(
    strategy: Strategy,
    data: dict[str, pd.DataFrame],
    entry_tf: str = "1",
    costs: Optional[CostModel] = None,
    initial_equity: float = 10_000.0,
    max_open_positions: int = 1,
    verbose: bool = False,
) -> BacktestResult:
    """
    Run a strategy backtest.

    Parameters
    ----------
    strategy      : Strategy subclass instance
    data          : dict of {tf_str: pd.DataFrame} — all timeframes the strategy needs
    entry_tf      : key in `data` used as the bar loop timeframe
    costs         : cost model (default: ForexCosts())
    initial_equity: starting account balance
    max_open_positions: maximum simultaneous trades
    verbose       : print progress every 10k bars
    """
    if costs is None:
        costs = ForexCosts()

    t0 = time.perf_counter()

    # Init strategy
    strategy.init(data)

    # Entry TF bars → numpy for fast indexing
    df = data[entry_tf].reset_index(drop=True)
    n_bars = len(df)

    ts_arr    = df["ts"].to_numpy()
    open_arr  = df["open"].to_numpy(dtype=float)
    high_arr  = df["high"].to_numpy(dtype=float)
    low_arr   = df["low"].to_numpy(dtype=float)
    close_arr = df["close"].to_numpy(dtype=float)
    vol_arr   = df["volume"].to_numpy(dtype=float) if "volume" in df.columns else np.zeros(n_bars)

    equity = initial_equity
    open_positions: list[Position] = []
    closed_trades: list[ClosedTrade] = []
    trade_id = 0
    pos_id = 0

    for i in range(n_bars):
        bar = BarData(
            ts=ts_arr[i],
            open_=open_arr[i],
            high=high_arr[i],
            low=low_arr[i],
            close=close_arr[i],
            volume=vol_arr[i],
            index=i,
        )

        # ── 1. Check exits on open positions ──────────────────────────────────
        if open_positions:
            states = _positions_to_array(open_positions)
            results = _check_exits_nb(states, bar.open, bar.high, bar.low, bar.close)

            remaining: list[Position] = []
            for j, pos in enumerate(open_positions):
                exit_code = int(results[j, 0])
                fill_raw = results[j, 1]
                is_sl_hit = bool(results[j, 2])

                if exit_code == 0:
                    # Update trailing stop if TP1 already hit
                    if pos.trail and pos.tp1_hit:
                        _update_trail(pos, bar)
                    remaining.append(pos)
                    continue

                exit_reason = _code_to_reason(exit_code)

                # Apply cost to fill
                fill = costs.exit_fill(fill_raw, pos.direction.value, is_sl=is_sl_hit)

                if exit_code == 2:  # TP1 — partial close
                    close_lots = pos.lots * pos.tp1_frac
                    comm_share = pos.entry_commission * pos.tp1_frac
                    pnl = _calc_pnl(costs, pos, fill, close_lots) - comm_share
                    equity += pnl
                    trade_id += 1
                    ct = ClosedTrade(
                        id=trade_id,
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        entry_time=pos.entry_time,
                        exit_price=fill,
                        exit_time=bar.ts,
                        exit_reason=ExitReason.TP1,
                        lots=close_lots,
                        pnl=pnl,
                        r_multiple=_r_mult(pos, fill, close_lots, costs),
                        label=pos.label if hasattr(pos, "label") else "",
                        sl=pos.original_sl,
                        tp1=pos.tp1 or 0.0,
                    )
                    closed_trades.append(ct)
                    strategy.on_partial(ct, _make_state(equity, initial_equity, remaining, closed_trades, i))

                    # Update position state
                    pos.lots_remaining -= close_lots
                    pos.tp1_hit = True
                    # Move SL to breakeven
                    pos.sl = pos.entry_price
                    pos.be_moved = True
                    # Activate trailing stop
                    if pos.trail:
                        pos.trail_stop = pos.entry_price
                    remaining.append(pos)

                elif exit_code == 3:  # TP2 — partial close
                    close_lots = pos.lots * pos.tp2_frac
                    comm_share = pos.entry_commission * pos.tp2_frac
                    pnl = _calc_pnl(costs, pos, fill, close_lots) - comm_share
                    equity += pnl
                    trade_id += 1
                    ct = ClosedTrade(
                        id=trade_id,
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        entry_time=pos.entry_time,
                        exit_price=fill,
                        exit_time=bar.ts,
                        exit_reason=ExitReason.TP2,
                        lots=close_lots,
                        pnl=pnl,
                        r_multiple=_r_mult(pos, fill, close_lots, costs),
                        label=pos.label if hasattr(pos, "label") else "",
                        sl=pos.original_sl,
                        tp1=pos.tp1 or 0.0,
                    )
                    closed_trades.append(ct)
                    strategy.on_partial(ct, _make_state(equity, initial_equity, remaining, closed_trades, i))
                    pos.lots_remaining -= close_lots
                    pos.tp2_hit = True
                    remaining.append(pos)

                else:  # SL / TP3 / TRAIL — full close of remainder
                    close_lots = pos.lots_remaining
                    runner_frac = close_lots / pos.lots if pos.lots > 0 else 1.0
                    comm_share = pos.entry_commission * runner_frac
                    pnl = _calc_pnl(costs, pos, fill, close_lots) - comm_share
                    # Funding cost for crypto
                    if hasattr(costs, "funding_cost"):
                        pnl -= costs.funding_cost(close_lots, pos.entry_price, pos.entry_time, bar.ts)
                    equity += pnl
                    trade_id += 1
                    ct = ClosedTrade(
                        id=trade_id,
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        entry_time=pos.entry_time,
                        exit_price=fill,
                        exit_time=bar.ts,
                        exit_reason=exit_reason,
                        lots=close_lots,
                        pnl=pnl,
                        r_multiple=_r_mult(pos, fill, close_lots, costs),
                        label=pos.label if hasattr(pos, "label") else "",
                        sl=pos.original_sl,
                        tp1=pos.tp1 or 0.0,
                    )
                    closed_trades.append(ct)
                    strategy.on_close(ct, _make_state(equity, initial_equity, remaining, closed_trades, i))

            open_positions = remaining

        # ── 2. Strategy signal ────────────────────────────────────────────────
        if len(open_positions) < max_open_positions:
            state = _make_state(equity, initial_equity, open_positions, closed_trades, i)
            signal = strategy.next(bar, state)

            if signal is not None:
                pos = _open_position(signal, bar, costs, equity, pos_id)
                if pos is not None:
                    pos_id += 1
                    # Store round-trip commission; netted into trade.pnl proportionally on close
                    pos.entry_commission = costs.commission(pos.lots, bar.close)
                    open_positions.append(pos)

        if verbose and i % 10_000 == 0 and i > 0:
            print(f"  {i:,}/{n_bars:,} bars  equity=${equity:.0f}  trades={len(closed_trades)}")

    # ── Flush open positions at end of data ───────────────────────────────────
    last_bar = BarData(
        ts=ts_arr[-1], open_=open_arr[-1], high=high_arr[-1],
        low=low_arr[-1], close=close_arr[-1], volume=vol_arr[-1], index=n_bars - 1,
    )
    for pos in open_positions:
        fill = costs.exit_fill(close_arr[-1], pos.direction.value, is_sl=False)
        runner_frac = pos.lots_remaining / pos.lots if pos.lots > 0 else 1.0
        comm_share = pos.entry_commission * runner_frac
        pnl = _calc_pnl(costs, pos, fill, pos.lots_remaining) - comm_share
        equity += pnl
        trade_id += 1
        closed_trades.append(ClosedTrade(
            id=trade_id,
            direction=pos.direction,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=fill,
            exit_time=last_bar.ts,
            exit_reason=ExitReason.EOD,
            lots=pos.lots_remaining,
            pnl=pnl,
            r_multiple=_r_mult(pos, fill, pos.lots_remaining, costs),
            label=pos.label if hasattr(pos, "label") else "",
            sl=pos.original_sl,
            tp1=pos.tp1 or 0.0,
        ))

    elapsed = time.perf_counter() - t0
    report = metrics_mod.compute(closed_trades, initial_equity)

    return BacktestResult(
        trades=closed_trades,
        report=report,
        elapsed_s=elapsed,
        n_bars=n_bars,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _positions_to_array(positions: list[Position]) -> np.ndarray:
    n = len(positions)
    arr = np.zeros((n, 9), dtype=np.float64)
    for i, p in enumerate(positions):
        arr[i, _POS_DIR]    = 1.0 if p.direction == Direction.LONG else -1.0
        arr[i, _POS_ENTRY]  = p.entry_price
        arr[i, _POS_SL]     = p.sl
        arr[i, _POS_TP1]    = p.tp1
        arr[i, _POS_TP2]    = p.tp2 or 0.0
        arr[i, _POS_TP3]    = p.tp3 or 0.0
        arr[i, _POS_TRAIL]  = p.trail_stop or 0.0
        arr[i, _POS_TP1HIT] = 1.0 if p.tp1_hit else 0.0
        arr[i, _POS_TP2HIT] = 1.0 if p.tp2_hit else 0.0
    return arr


def _code_to_reason(code: int) -> ExitReason:
    return {1: ExitReason.SL, 2: ExitReason.TP1, 3: ExitReason.TP2,
            4: ExitReason.TP3, 5: ExitReason.TRAIL}.get(code, ExitReason.SL)


def _calc_pnl(costs: CostModel, pos: Position, fill: float, lots: float) -> float:
    if hasattr(costs, "pnl"):
        return costs.pnl(pos.entry_price, fill, pos.direction.value, lots)
    # Fallback: pip-based
    price_move = fill - pos.entry_price if pos.direction == Direction.LONG else pos.entry_price - fill
    return price_move * costs.pip_value(lots)


def _r_mult(pos: Position, fill: float, lots: float, costs: CostModel) -> float:
    initial_risk = abs(pos.entry_price - pos.sl) * costs.pip_value(lots) / (
        costs.pip_size if hasattr(costs, "pip_size") else 0.0001
    )
    if initial_risk == 0:
        return 0.0
    pnl = _calc_pnl(costs, pos, fill, lots)
    return pnl / initial_risk


def _update_trail(pos: Position, bar: BarData) -> None:
    """Advance trailing stop on new structure (simple: bar close > last close)."""
    if pos.trail_stop is None:
        return
    if pos.direction == Direction.LONG:
        # Trail below bar low with a small buffer (use entry-level granularity)
        candidate = bar.low
        if candidate > pos.trail_stop:
            pos.trail_stop = candidate
    else:
        candidate = bar.high
        if candidate < pos.trail_stop:
            pos.trail_stop = candidate


def _open_position(
    signal: Signal,
    bar: BarData,
    costs: CostModel,
    equity: float,
    pos_id: int,
) -> Optional[Position]:
    """Create a Position from a Signal, computing lot size."""
    stop_dist = abs(signal.entry - signal.sl)
    if stop_dist <= 0:
        return None

    # Min stop check (forex)
    if hasattr(costs, "min_stop_pips") and hasattr(costs, "pip_size"):
        min_stop = costs.min_stop_pips() * costs.pip_size
        if stop_dist < min_stop:
            return None

    if hasattr(costs, "calc_lots"):
        import inspect
        sig = inspect.signature(costs.calc_lots)
        if "price" in sig.parameters:
            lots = costs.calc_lots(equity, signal.risk_pct, stop_dist, price=signal.entry)
        else:
            lots = costs.calc_lots(equity, signal.risk_pct, stop_dist)
    else:
        lots = 0.01

    if lots <= 0:
        return None

    fill = costs.entry_fill(signal.entry, signal.direction.value if hasattr(signal.direction, "value") else signal.direction)

    return Position(
        id=pos_id,
        direction=signal.direction,
        entry_price=fill,
        entry_time=bar.ts,
        sl=signal.sl,
        tp1=signal.tp1,
        tp2=signal.tp2,
        tp3=signal.tp3,
        lots=lots,
        risk_pct=signal.risk_pct,
        tp1_frac=signal.tp1_frac,
        tp2_frac=signal.tp2_frac,
        trail=signal.trail,
        label=getattr(signal, "label", ""),
    )


def _make_state(equity, initial_equity, open_positions, closed_trades, bar_index) -> EngineState:
    from .base import EngineState
    return EngineState(equity, initial_equity, open_positions, closed_trades, bar_index)

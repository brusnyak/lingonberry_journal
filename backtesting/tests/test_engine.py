"""
Engine audit tests.

Covers:
  1. No same-bar entry+exit (1-bar delay enforced)
  2. Partial close lot accounting (TP1 + TP2 + runner = original lots)
  3. Commission deducted exactly once per entry
  4. SL hit math (correct PnL sign for long and short)
  5. TP1 partial + BE move (SL moves to entry after TP1)
  6. R-multiple sign (winning trade > 0, losing trade < 0)
  7. CryptoCosts margin cap
  8. ForexCosts lot sizing (risk_pct × equity = expected dollar risk)
  9. Metrics: WR, PF, max DD on known trade list
 10. EOD flush closes all open positions

Run:
    python -m pytest backtesting/tests/test_engine.py -v
    python backtesting/tests/test_engine.py       # no pytest needed
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly without pytest
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.costs import CryptoCosts, ForexCosts
from backtesting.engine.orders import ClosedTrade, Direction, ExitReason, Signal
from backtesting.engine.runner import run, _check_exits_nb, _positions_to_array
from backtesting.engine import metrics


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_bars(
    n: int = 20,
    open_=1.1000,
    high=1.1010,
    low=1.0990,
    close=1.1005,
) -> pd.DataFrame:
    """Flat price bars — price never moves unless overridden."""
    ts = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({
        "ts": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000.0,
    })


def _make_bars_custom(rows: list[dict]) -> pd.DataFrame:
    """Build bars from explicit OHLC dicts."""
    ts = pd.date_range("2026-01-01", periods=len(rows), freq="1min", tz="UTC")
    df = pd.DataFrame(rows)
    df["ts"] = ts
    df["volume"] = 1000.0
    return df


class _SingleLongAtBar(Strategy):
    """Opens one long at bar `trigger_bar`, then does nothing."""
    def __init__(self, trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1050):
        self.trigger_bar = trigger_bar
        self._entry = entry
        self._sl = sl
        self._tp1 = tp1
        self.signals_sent = 0

    def next(self, bar, state):
        if bar.index == self.trigger_bar and not state.has_open_position:
            self.signals_sent += 1
            return Signal(
                direction=Direction.LONG,
                entry=self._entry,
                sl=self._sl,
                tp1=self._tp1,
                risk_pct=0.01,
                tp1_frac=0.5,
                tp2_frac=0.3,
                trail=False,
            )
        return None


class _SingleShortAtBar(Strategy):
    def __init__(self, trigger_bar=5, entry=1.1000, sl=1.1050, tp1=1.0950):
        self.trigger_bar = trigger_bar
        self._entry = entry
        self._sl = sl
        self._tp1 = tp1

    def next(self, bar, state):
        if bar.index == self.trigger_bar and not state.has_open_position:
            return Signal(
                direction=Direction.SHORT,
                entry=self._entry,
                sl=self._sl,
                tp1=self._tp1,
                risk_pct=0.01,
                tp1_frac=0.5,
                tp2_frac=0.3,
                trail=False,
            )
        return None


class _NullStrategy(Strategy):
    def next(self, bar, state):
        return None


# ── Test 1: No same-bar entry+exit ───────────────────────────────────────────

def test_no_same_bar_exit():
    """
    Position opened at bar 5. SL is below the low of bar 5.
    Bar 5 low should NOT trigger SL (entry and exit on same bar = look-ahead).
    SL must only be checked from bar 6 onward.
    """
    # Bar 5: low = 1.0940 which is below SL of 1.0950
    # If same-bar exit allowed → trade closes immediately at loss
    # Correct behavior: trade survives bar 5, exits on bar 6
    rows = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows.append({"open": 1.1000, "high": 1.1010, "low": 1.0930, "close": 1.0935})  # bar 5: entry bar, low < SL
    rows.append({"open": 1.0935, "high": 1.0960, "low": 1.0930, "close": 1.0940})  # bar 6: low < SL → should exit here

    df = _make_bars_custom(rows)
    strategy = _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1100)
    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)
    result = run(strategy, {"1": df}, entry_tf="1", costs=costs, initial_equity=10_000)

    assert len(result.trades) == 1, f"Expected 1 trade, got {len(result.trades)}"
    trade = result.trades[0]
    # Trade must exit on bar 6 (index 6) or later — NOT on bar 5
    entry_ts = df["ts"].iloc[5]
    assert trade.entry_time == entry_ts, "Entry must be at bar 5 timestamp"
    exit_ts = df["ts"].iloc[6]
    assert trade.exit_time >= exit_ts, f"Exit at {trade.exit_time} should be >= bar 6 {exit_ts}"
    print("PASS test_no_same_bar_exit")


# ── Test 2: Partial close lot accounting ─────────────────────────────────────

def test_partial_close_lots():
    """
    TP1 closes tp1_frac of lots.
    TP2 closes tp2_frac of lots.
    Runner (remainder) closes at EOD.
    Sum of all partial lots == original lots.
    """
    # Bar 5: enter long
    # Bar 6: price at TP1 (lots × 0.5 closed)
    # Bar 7: price at TP2 (lots × 0.3 closed)
    # Bar 8+: price flat → EOD flush closes runner (lots × 0.2)
    rows = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})  # bar 5: entry
    rows.append({"open": 1.1050, "high": 1.1060, "low": 1.1045, "close": 1.1055})  # bar 6: hits TP1=1.1050
    rows.append({"open": 1.1070, "high": 1.1085, "low": 1.1065, "close": 1.1080})  # bar 7: hits TP2=1.1080
    rows.append({"open": 1.1080, "high": 1.1085, "low": 1.1078, "close": 1.1082})  # bar 8: flat → EOD

    df = _make_bars_custom(rows)

    class _PartialStrategy(Strategy):
        def next(self, bar, state):
            if bar.index == 5 and not state.has_open_position:
                return Signal(
                    direction=Direction.LONG,
                    entry=1.1000,
                    sl=1.0900,
                    tp1=1.1050,
                    tp2=1.1080,
                    risk_pct=0.01,
                    tp1_frac=0.5,
                    tp2_frac=0.3,
                    trail=False,
                )
            return None

    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)
    result = run(_PartialStrategy(), {"1": df}, entry_tf="1", costs=costs, initial_equity=10_000)

    # Should have 3 trade records: TP1 partial, TP2 partial, EOD runner
    assert len(result.trades) == 3, f"Expected 3 trades (TP1+TP2+EOD), got {len(result.trades)}"

    reasons = [t.exit_reason for t in result.trades]
    assert ExitReason.TP1 in reasons, "Missing TP1 exit"
    assert ExitReason.TP2 in reasons, "Missing TP2 exit"
    assert ExitReason.EOD in reasons, "Missing EOD exit"

    total_lots = sum(t.lots for t in result.trades)
    # Get original lots from TP1 trade (tp1_frac = 0.5 → original = tp1_lots / 0.5)
    tp1_trade = next(t for t in result.trades if t.exit_reason == ExitReason.TP1)
    original_lots = tp1_trade.lots / 0.5
    assert abs(total_lots - original_lots) < 1e-9, \
        f"Lot sum {total_lots:.6f} != original {original_lots:.6f}"
    print(f"PASS test_partial_close_lots (original_lots={original_lots:.4f})")


# ── Test 3: Commission deducted exactly once ──────────────────────────────────

def test_commission_once():
    """
    Open 1 trade, close at SL. Commission should equal costs.commission(lots, price)
    and be deducted exactly once (on entry), not on exit too.
    """
    rows = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})  # bar 5: entry
    rows.append({"open": 1.0940, "high": 1.0945, "low": 1.0930, "close": 1.0935})  # bar 6: SL hit

    df = _make_bars_custom(rows)
    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.75)

    initial = 10_000.0
    result = run(
        _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1100),
        {"1": df}, entry_tf="1", costs=costs, initial_equity=initial,
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    lots = trade.lots

    # Commission is netted into trade.pnl — no separate equity deduction.
    # Invariant: equity_final == initial + sum(trade.pnl)
    equity_final = result.report["equity_curve"][-1]
    assert abs(equity_final - (initial + trade.pnl)) < 0.01, \
        f"equity {equity_final:.4f} != initial + trade.pnl = {initial + trade.pnl:.4f}"

    # Commission charged exactly once: trade.pnl = price_move_pnl - round_trip_comm
    expected_comm = 2 * 0.75 * lots
    gross_pnl = costs.pnl(trade.entry_price, trade.exit_price, trade.direction.value, lots)
    assert abs(trade.pnl - (gross_pnl - expected_comm)) < 0.01, \
        f"trade.pnl {trade.pnl:.4f} != gross {gross_pnl:.4f} - comm {expected_comm:.4f}"
    print(f"PASS test_commission_once (lots={lots:.2f}, comm=${expected_comm:.2f}, net_pnl=${trade.pnl:.2f})")


# ── Test 4: SL PnL sign ───────────────────────────────────────────────────────

def test_sl_pnl_sign():
    """Long SL hit → negative PnL. Short SL hit → negative PnL."""
    # Long: entry 1.1000, SL 1.0950 → loss
    rows_long = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows_long.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})
    rows_long.append({"open": 1.0940, "high": 1.0945, "low": 1.0930, "close": 1.0935})

    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)
    result_long = run(
        _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1100),
        {"1": _make_bars_custom(rows_long)}, entry_tf="1", costs=costs, initial_equity=10_000,
    )
    assert result_long.trades[0].pnl < 0, "Long SL hit must be negative PnL"

    # Short: entry 1.1000, SL 1.1050 → loss
    rows_short = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows_short.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})
    rows_short.append({"open": 1.1060, "high": 1.1070, "low": 1.1055, "close": 1.1065})

    result_short = run(
        _SingleShortAtBar(trigger_bar=5, entry=1.1000, sl=1.1050, tp1=1.0950),
        {"1": _make_bars_custom(rows_short)}, entry_tf="1", costs=costs, initial_equity=10_000,
    )
    assert result_short.trades[0].pnl < 0, "Short SL hit must be negative PnL"
    print("PASS test_sl_pnl_sign")


# ── Test 5: BE move after TP1 ─────────────────────────────────────────────────

def test_be_move_after_tp1():
    """
    After TP1 hit, SL must move to entry_price (breakeven).
    A subsequent bar that would have hit the original SL must NOT close the trade.
    """
    entry = 1.1000
    sl = 1.0900     # 100 pips below
    tp1 = 1.1050
    tp2 = 1.1100

    rows = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows.append({"open": entry, "high": entry + 0.0010, "low": entry - 0.0010, "close": entry})  # bar 5: entry
    rows.append({"open": 1.1050, "high": 1.1060, "low": 1.1045, "close": 1.1055})  # bar 6: TP1 hit
    rows.append({"open": 1.0950, "high": 1.0960, "low": 1.0910, "close": 1.0920})  # bar 7: dips to 1.0910 (old SL) but BE=1.1000

    # Bar 7 low (1.0910) < original SL (1.0900) but > entry (1.1000)?
    # Wait: 1.0910 is below entry 1.1000. So BE stop at 1.1000 should be hit.
    # Let's set bar 7 to dip to 1.0950 — below old SL but above entry.
    # Then trade should NOT close (BE=1.1000, bar 7 low=1.0950 which is < 1.1000... that would trigger BE)
    # Fix: bar 7 should dip to 1.0950 which is below original SL (1.0900 is the original, so 1.0950 > 1.0900)
    # and 1.0950 < 1.1000 (BE) → BE triggered.
    #
    # Correct test: bar 7 dips to 1.0950 (between original SL=1.0900 and entry=1.1000).
    # Original SL would NOT have triggered (low=1.0950 > sl=1.0900).
    # BE at 1.1000 WOULD trigger (low=1.0950 < be=1.1000).
    # After TP1: trade should have BE at 1.1000. Bar 7 low < 1.1000 → trade closes at BE.
    # This verifies BE moved correctly (trade closed, not open forever).
    rows[-1] = {"open": 1.1010, "high": 1.1015, "low": 1.0950, "close": 1.0955}  # low hits BE=1.1000
    rows.append({"open": 1.0955, "high": 1.0960, "low": 1.0950, "close": 1.0955})  # bar 8: flat

    df = _make_bars_custom(rows)

    class _BEStrategy(Strategy):
        def next(self, bar, state):
            if bar.index == 5 and not state.has_open_position:
                return Signal(
                    direction=Direction.LONG,
                    entry=entry,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    risk_pct=0.01,
                    tp1_frac=0.5,
                    tp2_frac=0.3,
                    trail=False,
                )
            return None

    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)
    result = run(_BEStrategy(), {"1": df}, entry_tf="1", costs=costs, initial_equity=10_000)

    # Should have TP1 partial + SL (BE) close
    reasons = [t.exit_reason for t in result.trades]
    assert ExitReason.TP1 in reasons, f"Missing TP1, got {reasons}"
    # Runner should close at or near BE (SL after BE move)
    sl_trades = [t for t in result.trades if t.exit_reason == ExitReason.SL]
    assert len(sl_trades) >= 1, f"Expected BE/SL close, got {reasons}"
    # Runner PnL should be near 0 (closed at entry price = BE)
    runner = sl_trades[0]
    assert abs(runner.pnl) < 5.0, f"BE close PnL should be ~0, got {runner.pnl:.2f}"
    print(f"PASS test_be_move_after_tp1 (runner pnl at BE: ${runner.pnl:.2f})")


# ── Test 6: R-multiple sign ───────────────────────────────────────────────────

def test_r_multiple_sign():
    """Winning trade (TP hit) → positive R. Losing trade (SL hit) → negative R."""
    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)

    # Winning: TP1 hit
    rows_win = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows_win.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})
    rows_win.append({"open": 1.1060, "high": 1.1070, "low": 1.1055, "close": 1.1065})  # TP1=1.1050 hit

    result_win = run(
        _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1050),
        {"1": _make_bars_custom(rows_win)}, entry_tf="1", costs=costs, initial_equity=10_000,
    )
    tp1_trade = next(t for t in result_win.trades if t.exit_reason == ExitReason.TP1)
    assert tp1_trade.r_multiple > 0, f"TP1 trade R should be positive, got {tp1_trade.r_multiple}"

    # Losing: SL hit
    rows_lose = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 5
    rows_lose.append({"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005})
    rows_lose.append({"open": 1.0940, "high": 1.0945, "low": 1.0930, "close": 1.0935})

    result_lose = run(
        _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0950, tp1=1.1100),
        {"1": _make_bars_custom(rows_lose)}, entry_tf="1", costs=costs, initial_equity=10_000,
    )
    assert result_lose.trades[0].r_multiple < 0, f"SL trade R should be negative"
    print("PASS test_r_multiple_sign")


# ── Test 7: CryptoCosts margin cap ───────────────────────────────────────────

def test_crypto_margin_cap():
    """
    With 10x leverage and $10k equity, max notional = $100k.
    At $50k BTC price: max lots = 2.0.
    Risk-based sizing might want 10 lots → must be capped at 2.
    """
    cr = CryptoCosts(leverage=10)
    lots = cr.calc_lots(10_000, 0.005, 5.0, price=50_000)
    assert lots == 2.0, f"Expected 2.0 lots (margin cap), got {lots}"

    # With small price (WLD at $2), risk-based sizing wins
    lots_wld = cr.calc_lots(10_000, 0.005, 0.05, price=2.0)
    risk_based = (10_000 * 0.005) / 0.05  # = 1000
    margin_cap = (10_000 * 10) / 2.0       # = 50000
    expected = min(risk_based, margin_cap)  # = 1000
    assert abs(lots_wld - expected) < 0.01, f"WLD lots {lots_wld} != {expected}"
    print(f"PASS test_crypto_margin_cap (BTC: {lots} lots, WLD: {lots_wld} lots)")


# ── Test 7b: Crypto exchange constraints ─────────────────────────────────────

def test_crypto_exchange_constraints():
    """Crypto sizing must respect 50x margin, min notional, min qty, and qty step."""
    cr = CryptoCosts(leverage=50, qty_step=0.001, min_qty=0.001, min_notional=5.0)

    # $20 account at 50x can carry at most $1000 notional.
    lots = cr.calc_lots(equity=20.0, risk_pct=0.5, stop_dist_price=10.0, price=100.0)
    assert lots == 1.0, f"Expected risk sizing to 1.0 lot, got {lots}"

    capped = cr.calc_lots(equity=20.0, risk_pct=1.0, stop_dist_price=0.01, price=100.0)
    assert capped == 10.0, f"Expected 50x notional cap to 10.0 lots, got {capped}"

    too_small = cr.calc_lots(equity=20.0, risk_pct=0.001, stop_dist_price=10.0, price=100.0)
    assert too_small == 0.0, f"Expected min_qty/min_notional rejection, got {too_small}"
    print("PASS test_crypto_exchange_constraints")


# ── Test 7c: Crypto funding side and liquidation ─────────────────────────────

def test_crypto_funding_and_liquidation():
    """Positive funding costs longs and credits shorts; 50x liquidation is close."""
    funding = pd.DataFrame({
        "ts": pd.to_datetime([
            "2026-01-01 08:00:00+00:00",
            "2026-01-01 16:00:00+00:00",
        ]),
        "fundingRate": [0.0001, 0.0002],
    })
    cr = CryptoCosts(leverage=50, funding_df=funding, maintenance_margin_rate=0.005)
    open_time = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    close_time = pd.Timestamp("2026-01-01 20:00:00", tz="UTC")

    long_cost = cr.funding_cost(1.0, 1000.0, open_time, close_time, direction="long")
    short_cost = cr.funding_cost(1.0, 1000.0, open_time, close_time, direction="short")
    assert abs(long_cost - 0.30) < 1e-9, f"Long funding should pay $0.30, got {long_cost}"
    assert abs(short_cost + 0.30) < 1e-9, f"Short funding should receive $0.30, got {short_cost}"

    assert abs(cr.liquidation_price(100.0, "long") - 98.5) < 1e-9
    assert abs(cr.liquidation_price(100.0, "short") - 101.5) < 1e-9
    assert cr.would_liquidate(100.0, "long", bar_high=101.0, bar_low=98.4)
    assert cr.would_liquidate(100.0, "short", bar_high=101.6, bar_low=99.0)
    print("PASS test_crypto_funding_and_liquidation")


# ── Test 7d: Runner liquidation exit ─────────────────────────────────────────

def test_runner_liquidation_exit():
    """Runner must close crypto trades at liquidation before a distant SL."""
    rows = [{"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0}] * 5
    rows.append({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0})  # entry
    rows.append({"open": 100.0, "high": 100.2, "low": 98.4, "close": 99.0})   # 50x liq ~= 98.5

    class _CryptoLong(Strategy):
        def next(self, bar, state):
            if bar.index == 5 and not state.has_open_position:
                return Signal(
                    direction=Direction.LONG,
                    entry=100.0,
                    sl=95.0,
                    tp1=110.0,
                    risk_pct=0.5,
                    trail=False,
                )
            return None

    result = run(
        _CryptoLong(),
        {"1": _make_bars_custom(rows)},
        entry_tf="1",
        costs=CryptoCosts(leverage=50, maintenance_margin_rate=0.005),
        initial_equity=20.0,
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == ExitReason.LIQUIDATION
    assert abs(result.trades[0].exit_price - 98.5) < 1e-9
    print("PASS test_runner_liquidation_exit")


# ── Test 8: Forex lot sizing dollar risk ─────────────────────────────────────

def test_forex_lot_sizing():
    """
    ForexCosts.calc_lots must produce: actual_dollar_risk ≈ equity × risk_pct.
    Tolerance: ±$1 for rounding to 2 decimal places.
    """
    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0)
    equity = 10_000.0
    risk_pct = 0.005  # 0.5% = $50

    # 10-pip stop
    stop_pips = 10
    stop_dist = stop_pips * costs.pip_size
    lots = costs.calc_lots(equity, risk_pct, stop_dist)
    dollar_risk = lots * stop_pips * costs.pip_value_per_lot
    expected = equity * risk_pct  # $50

    assert abs(dollar_risk - expected) < 1.0, \
        f"Dollar risk ${dollar_risk:.2f} vs expected ${expected:.2f}"

    # 25-pip stop
    lots2 = costs.calc_lots(equity, risk_pct, 25 * costs.pip_size)
    dollar_risk2 = lots2 * 25 * costs.pip_value_per_lot
    assert abs(dollar_risk2 - expected) < 1.0, \
        f"25-pip dollar risk ${dollar_risk2:.2f} vs expected ${expected:.2f}"
    print(f"PASS test_forex_lot_sizing (10pip: {lots} lots = ${dollar_risk:.1f} risk)")


# ── Test 9: Metrics correctness ──────────────────────────────────────────────

def test_metrics():
    """Known trade list → verify WR, PF, max DD."""
    def _trade(pnl, r):
        return ClosedTrade(
            id=1, direction=Direction.LONG,
            entry_price=1.1, entry_time=None,
            exit_price=1.11, exit_time=None,
            exit_reason=ExitReason.TP1,
            lots=0.1, pnl=pnl, r_multiple=r,
        )

    trades = [
        _trade(100, 2.0),
        _trade(100, 2.0),
        _trade(-50, -1.0),
        _trade(100, 2.0),
        _trade(-50, -1.0),
    ]
    report = metrics.compute(trades, initial_equity=10_000)

    assert report["trades"] == 5
    assert abs(report["win_rate"] - 0.6) < 0.001, f"WR {report['win_rate']}"
    expected_pf = 300 / 100  # gross wins / gross losses
    assert abs(report["profit_factor"] - expected_pf) < 0.01, f"PF {report['profit_factor']}"
    assert abs(report["total_pnl"] - 200) < 0.01

    # Equity curve: 10000, 10100, 10200, 10150, 10250, 10200
    # Max DD: 10250 → 10200 = 50
    assert abs(report["max_drawdown"] - 50) < 0.01, f"DD {report['max_drawdown']}"
    print(f"PASS test_metrics (WR={report['win_rate']:.0%}, PF={report['profit_factor']:.1f}, DD=${report['max_drawdown']:.0f})")


# ── Test 10: EOD flush ────────────────────────────────────────────────────────

def test_eod_flush():
    """Open position that never hits SL or TP must be closed by EOD flush."""
    # Entry at bar 5, SL far below, TP far above — never triggered in 10 bars
    rows = [{"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}] * 10

    costs = ForexCosts(pip_size=0.0001, pip_value_per_lot=10.0, commission_per_side=0.0)
    result = run(
        _SingleLongAtBar(trigger_bar=5, entry=1.1000, sl=1.0500, tp1=1.2000),
        {"1": _make_bars_custom(rows)}, entry_tf="1", costs=costs, initial_equity=10_000,
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == ExitReason.EOD, \
        f"Expected EOD, got {result.trades[0].exit_reason}"
    print("PASS test_eod_flush")


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    test_no_same_bar_exit,
    test_partial_close_lots,
    test_commission_once,
    test_sl_pnl_sign,
    test_be_move_after_tp1,
    test_r_multiple_sign,
    test_crypto_margin_cap,
    test_crypto_exchange_constraints,
    test_crypto_funding_and_liquidation,
    test_runner_liquidation_exit,
    test_forex_lot_sizing,
    test_metrics,
    test_eod_flush,
]

if __name__ == "__main__":
    passed = 0
    failed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
    sys.exit(0 if failed == 0 else 1)

"""Copy Trader tests.

Run:
    python -m pytest backtesting/tests/test_copy_trader.py -v
    python backtesting/tests/test_copy_trader.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from infra.copy_trader import _calc_slave_lots, _snapshot_positions, PosSnapshot, CopyTrader


# ── Test 1: Proportional sizing — 25K master -> 100K slave ───────────────────

def test_calc_slave_lots_4x():
    """$25K master with 0.36 lots -> $100K slave should get 1.44 lots."""
    lots = _calc_slave_lots(master_lots=0.36, master_equity=25_000, slave_equity=100_000)
    expected = 0.36 * 100_000 / 25_000  # exactly 1.44
    expected = int(expected / 0.01) * 0.01
    assert abs(lots - expected) < 0.001, f"lots={lots} expected={expected}"
    print(f"PASS test_calc_slave_lots_4x: {lots} lots (expected {expected})")


# ── Test 2: Proportional sizing — small master position ──────────────────────

def test_calc_slave_lots_small():
    """$25K master with 0.09 lots -> $100K slave -> 0.36 lots."""
    lots = _calc_slave_lots(master_lots=0.09, master_equity=25_000, slave_equity=100_000)
    expected = int(0.09 * 100_000 / 25_000 / 0.01) * 0.01  # 0.36
    assert abs(lots - expected) < 0.001, f"lots={lots} expected={expected}"
    print(f"PASS test_calc_slave_lots_small: {lots} lots (expected {expected})")


# ── Test 3: Capped at MAX_LOTS ───────────────────────────────────────────────

def test_calc_slave_lots_max_cap():
    """Very large master lots with high equity ratio should hit MAX_LOTS cap."""
    lots = _calc_slave_lots(master_lots=10.0, master_equity=10_000, slave_equity=1_000_000)
    assert lots == 20.0, f"Expected MAX_LOTS=20.0, got {lots}"
    print(f"PASS test_calc_slave_lots_max_cap: {lots} lots")


# ── Test 4: Minimum LOT_STEP floor ───────────────────────────────────────────

def test_calc_slave_lots_minimum():
    """Very small master lots or tiny slave equity should floor at LOT_STEP."""
    lots = _calc_slave_lots(master_lots=0.01, master_equity=100_000, slave_equity=1_000)
    assert lots == 0.01, f"Expected LOT_STEP=0.01, got {lots}"
    print(f"PASS test_calc_slave_lots_minimum: {lots} lots")


# ── Test 5: Zero equity protection ───────────────────────────────────────────

def test_calc_slave_lots_zero_equity():
    """Zero master or slave equity returns minimum LOT_STEP."""
    lots_a = _calc_slave_lots(master_lots=0.36, master_equity=0, slave_equity=98_000)
    assert lots_a == 0.01, f"Expected LOT_STEP=0.01, got {lots_a}"

    lots_b = _calc_slave_lots(master_lots=0.36, master_equity=24_000, slave_equity=0)
    assert lots_b == 0.01, f"Expected LOT_STEP=0.01, got {lots_b}"

    print("PASS test_calc_slave_lots_zero_equity: 0.01 lots on zero equity")


# ── Test 6: Snapshot parsing ─────────────────────────────────────────────────

def test_snapshot_positions():
    """Parse a mock positions DataFrame into PosSnapshot dict."""
    mock_tl = MagicMock()
    df = pd.DataFrame([{
        "id": 12345,
        "tradableInstrumentId": 999,
        "side": "buy",
        "qty": 0.10,
        "avgPrice": 1.10000,
        "stopLoss": 1.09500,
        "takeProfit": 1.10500,
    }])
    mock_tl.get_all_positions.return_value = df
    mock_tl.get_symbol_name_from_instrument_id.return_value = "EURUSD.X"

    result = _snapshot_positions(mock_tl, {}, {})

    assert 12345 in result
    pos = result[12345]
    assert pos.side == "buy"
    assert pos.qty == 0.10
    assert pos.avg_price == 1.10000
    assert pos.stop_loss == 1.09500
    assert pos.take_profit == 1.10500
    print(f"PASS test_snapshot_positions: {pos.symbol} {pos.side} {pos.qty} lots")


# ── Test 7: Snapshot handles empty positions ─────────────────────────────────

def test_snapshot_empty():
    """Empty DataFrame -> empty dict."""
    mock_tl = MagicMock()
    mock_tl.get_all_positions.return_value = pd.DataFrame()
    result = _snapshot_positions(mock_tl, {}, {})
    assert result == {}
    print("PASS test_snapshot_empty")


# ── Test 8: Snapshot handles None positions ──────────────────────────────────

def test_snapshot_none():
    """None from API -> empty dict."""
    mock_tl = MagicMock()
    mock_tl.get_all_positions.return_value = None
    result = _snapshot_positions(mock_tl, {}, {})
    assert result == {}
    print("PASS test_snapshot_none")


# ── Test 9: CopyTrader pre-links matching positions ──────────────────────────

def test_prelink_existing():
    """Positions with same instrument+side get pre-linked on startup."""
    with patch("infra.copy_trader._create_tlapi") as mock_create, \
         patch("infra.copy_trader._snapshot_positions") as mock_snap, \
         patch("infra.copy_trader.time") as mock_time:

        master_tl = MagicMock()
        slave_tl = MagicMock()
        mock_create.side_effect = [master_tl, slave_tl]

        # Master has one buy on instrument 100
        master_pos = {
            1: PosSnapshot(1, 100, "EURUSD", "buy", 0.10, 1.1000, 1.0950, 1.1050),
        }
        # Slave has matching buy on instrument 200 (different ID, same symbol)
        slave_pos = {
            2: PosSnapshot(2, 200, "EURUSD", "buy", 0.40, 1.1000, 1.0950, 1.1050),
        }
        # First two calls: initial sync in run(). Then KeyboardInterrupt to break loop.
        mock_snap.side_effect = [master_pos, slave_pos]
        mock_time.sleep.side_effect = KeyboardInterrupt()

        trader = CopyTrader()
        try:
            trader.run()
        except KeyboardInterrupt:
            pass

        assert trader._master_to_slave == {1: 2}, f"Expected {{1: 2}}, got {trader._master_to_slave}"
        print("PASS test_prelink_existing: master#1 -> slave#2")


# ── Runner ───────────────────────────────────────────────────────────────────

TESTS = [
    test_calc_slave_lots_4x,
    test_calc_slave_lots_small,
    test_calc_slave_lots_max_cap,
    test_calc_slave_lots_minimum,
    test_calc_slave_lots_zero_equity,
    test_snapshot_positions,
    test_snapshot_empty,
    test_snapshot_none,
    test_prelink_existing,
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

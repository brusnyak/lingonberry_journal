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

from infra.copy_trader import _calc_lots, _snapshot_positions, PosSnapshot, CopyTrader


# ── Test 1: Lot sizing — standard pair ───────────────────────────────────────

def test_calc_lots_standard():
    """0.5% risk on $25k equity, 15-pip stop on EURUSD → correct lot size."""
    equity = 25_000.0
    stop_pips = 15
    stop_distance = stop_pips * 0.0001  # 0.0015

    lots = _calc_lots(equity, stop_distance, is_jpy=False)

    # Risk amount = 25000 * 0.005 = $125
    # pip_value_per_lot for standard = $10/pip
    # lots = 125 / (15 * 10) = 0.833...
    # floored to LOT_STEP=0.01 → 0.83
    risk_amt = equity * 0.005
    expected = risk_amt / (stop_pips * 10)
    expected_floored = int(expected / 0.01) * 0.01
    assert abs(lots - expected_floored) < 0.001, f"lots={lots} expected={expected_floored}"
    print(f"PASS test_calc_lots_standard: {lots} lots (risk=${risk_amt:.0f}, {stop_pips}pip stop)")


# ── Test 2: Lot sizing — JPY pair ────────────────────────────────────────────

def test_calc_lots_jpy():
    """JPY pair uses 1_000 multiplier, not 100_000."""
    equity = 25_000.0
    stop_distance = 0.15  # 15 pips for JPY (0.01 per pip)

    lots = _calc_lots(equity, stop_distance, is_jpy=True)

    # JPY: mult=1000, risk=$125, lots = 125 / (0.15 * 1000) = 0.833
    risk_amt = equity * 0.005
    expected = risk_amt / (stop_distance * 1000)
    expected_floored = int(expected / 0.01) * 0.01
    assert abs(lots - expected_floored) < 0.001, f"lots={lots} expected={expected_floored}"
    print(f"PASS test_calc_lots_jpy: {lots} lots")


# ── Test 3: Lot sizing — capped at MAX_LOTS ──────────────────────────────────

def test_calc_lots_max_cap():
    """Very tight stop with high equity should hit MAX_LOTS cap."""
    lots = _calc_lots(equity=100_000, stop_distance=0.0001, is_jpy=False)
    assert lots == 20.0, f"Expected MAX_LOTS=20.0, got {lots}"
    print(f"PASS test_calc_lots_max_cap: {lots} lots")


# ── Test 4: Lot sizing — minimum LOT_STEP ────────────────────────────────────

def test_calc_lots_minimum():
    """Wide stop with low equity should return minimum LOT_STEP."""
    lots = _calc_lots(equity=1_000, stop_distance=0.05, is_jpy=False)
    assert lots == 0.01, f"Expected LOT_STEP=0.01, got {lots}"
    print(f"PASS test_calc_lots_minimum: {lots} lots")


# ── Test 5: Lot sizing — slave (100K) produces ~4x master (25K) ──────────────

def test_calc_lots_proportional():
    """Same risk%, same stop → 100K account should produce ~4x the lots of 25K."""
    stop_distance = 0.0015  # 15 pips

    lots_25k = _calc_lots(25_000, stop_distance, is_jpy=False)
    lots_100k = _calc_lots(100_000, stop_distance, is_jpy=False)

    ratio = lots_100k / lots_25k if lots_25k > 0 else 0
    assert 3.8 <= ratio <= 4.2, f"Expected ~4x ratio, got {ratio:.2f}x ({lots_25k} → {lots_100k})"
    print(f"PASS test_calc_lots_proportional: 25K={lots_25k} → 100K={lots_100k} ({ratio:.1f}x)")


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
    """Empty DataFrame → empty dict."""
    mock_tl = MagicMock()
    mock_tl.get_all_positions.return_value = pd.DataFrame()
    result = _snapshot_positions(mock_tl, {}, {})
    assert result == {}
    print("PASS test_snapshot_empty")


# ── Test 8: Snapshot handles None positions ──────────────────────────────────

def test_snapshot_none():
    """None from API → empty dict."""
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
        print("PASS test_prelink_existing: master#1 → slave#2")


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    test_calc_lots_standard,
    test_calc_lots_jpy,
    test_calc_lots_max_cap,
    test_calc_lots_minimum,
    test_calc_lots_proportional,
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

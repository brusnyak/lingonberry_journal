"""
Tests for webapp/crypto_execute.py against a fake ccxt client -- no real
API calls, no real money. Verifies the logic (confirm gating, correct
TP ladder, breakeven-move detection, EOD close) is actually correct, since
the real account has been at $0 balance all session and this code has
never been proven against a real fill.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from webapp.crypto_execute import (
    execute_trade, manage_open_positions, size_trade, account_state, ExecutionError,
    TP1_R, TP1_FRAC, TP2_R, TP2_FRAC, TP3_R, TP3_FRAC,
)


class FakeClient:
    """Minimal fake standing in for ccxt.bingx. Records every call so tests
    can assert on exact order parameters, not just "it didn't crash"."""

    def __init__(self, equity=20.0, positions=None, open_orders=None, entry_price=0.0016):
        self._equity = equity
        self._positions = positions or []
        self._open_orders = open_orders or []
        self._next_id = 1
        self.calls = []

    def _id(self):
        i = self._next_id
        self._next_id += 1
        return str(i)

    def fetch_balance(self):
        return {"USDT": {"free": self._equity, "total": self._equity}}

    def load_markets(self):
        return {"AKE/USDT:USDT": {
            "limits": {"cost": {"min": 2.0}, "amount": {"min": 28.0}},
            "precision": {"amount": 1.0, "price": 1e-5},
        }}

    def fetch_positions(self):
        return self._positions

    def fetch_open_orders(self, symbol):
        return [o for o in self._open_orders if o.get("symbol", symbol) == symbol]

    def set_leverage(self, leverage, symbol):
        self.calls.append(("set_leverage", leverage, symbol))

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self.calls.append(("create_order", symbol, type, side, amount, price, params))
        return {"id": self._id()}

    def create_stop_loss_order(self, symbol, type, side, amount, stopLossPrice=None, params=None):
        self.calls.append(("create_stop_loss_order", symbol, type, side, amount, stopLossPrice, params))
        return {"id": self._id()}

    def cancel_order(self, order_id, symbol):
        self.calls.append(("cancel_order", order_id, symbol))


# ── size_trade ──────────────────────────────────────────────────────────────

def test_size_trade_rejects_when_equity_zero():
    client = FakeClient(equity=0.0)
    result = size_trade("AKE/USDT:USDT", "long", entry=0.0016, sl=0.0014, client=client)
    assert result["tradeable"] is False
    assert "too small" in result["reject_reason"]


def test_size_trade_sizes_against_real_balance_and_specs():
    client = FakeClient(equity=1000.0)  # generous balance so min_notional isn't the binding constraint
    result = size_trade("AKE/USDT:USDT", "long", entry=0.0016, sl=0.0014, risk_pct=0.005, client=client)
    assert result["equity"] == 1000.0
    # risk_amount = 1000 * 0.005 = 5; stop_dist = 0.0002; lots = 5/0.0002 = 25000
    assert result["lots"] == pytest.approx(25000, rel=0.05)


# ── execute_trade ───────────────────────────────────────────────────────────

def test_execute_trade_refuses_without_confirm():
    with pytest.raises(ExecutionError, match="confirm"):
        execute_trade("AKE/USDT:USDT", "long", entry=0.0016, sl=0.0014, confirm=False)


def test_execute_trade_places_full_ladder_at_correct_prices_and_fractions(monkeypatch):
    client = FakeClient(equity=1000.0)
    monkeypatch.setattr("webapp.crypto_execute.get_client", lambda: client)
    result = execute_trade("AKE/USDT:USDT", "long", entry=0.0016, sl=0.0014, confirm=True)

    assert len(result["tp_orders"]) == 3
    risk = 0.0016 - 0.0014
    expected = [
        (TP1_R, TP1_FRAC, 0.0016 + TP1_R * risk),
        (TP2_R, TP2_FRAC, 0.0016 + TP2_R * risk),
        (TP3_R, TP3_FRAC, 0.0016 + TP3_R * risk),
    ]
    for tp, (r_mult, frac, price) in zip(result["tp_orders"], expected):
        assert tp["r_mult"] == r_mult
        assert tp["price"] == pytest.approx(price)
        assert tp["lots"] == pytest.approx(result["sizing"]["lots"] * frac)

    tp_calls = [c for c in client.calls if c[0] == "create_order" and c[6] and c[6].get("reduceOnly")]
    assert len(tp_calls) == 3
    sl_calls = [c for c in client.calls if c[0] == "create_stop_loss_order"]
    assert len(sl_calls) == 1
    assert sl_calls[0][5] == 0.0014  # SL is the strategy's own stop, unchanged from input


def test_execute_trade_short_direction_flips_sides_correctly(monkeypatch):
    client = FakeClient(equity=1000.0)
    monkeypatch.setattr("webapp.crypto_execute.get_client", lambda: client)
    result = execute_trade("AKE/USDT:USDT", "short", entry=0.0016, sl=0.0018, confirm=True)
    # short: TP prices go DOWN from entry
    assert result["tp_orders"][0]["price"] < 0.0016
    entry_calls = [c for c in client.calls if c[0] == "create_order" and c[3] == "sell" and c[6] is None]
    assert len(entry_calls) == 1  # market sell to open the short


# ── manage_open_positions ────────────────────────────────────────────────────

_POS = [{"symbol": "AKE/USDT:USDT", "side": "long", "entryPrice": 0.0016, "contracts": 12500.0}]


def test_manage_moves_sl_to_breakeven_when_tp1_filled(monkeypatch):
    open_orders = [
        {"symbol": "AKE/USDT:USDT", "id": "sl1", "clientOrderId": "tag-sl",
         "stopPrice": 0.0014},
        # tp1 NOT present -> filled
        {"symbol": "AKE/USDT:USDT", "id": "tp2", "clientOrderId": "tag-tp2"},
        {"symbol": "AKE/USDT:USDT", "id": "tp3", "clientOrderId": "tag-tp3"},
    ]
    client = FakeClient(positions=_POS, open_orders=open_orders)
    # fixed "now" well before EOD cutoff (19:55 UTC)
    actions = manage_open_positions(client=client, eod_hour_utc=25, eod_minute_utc=0)  # unreachable EOD for this test
    assert len(actions) == 1
    assert actions[0]["action"] == "moved_sl_to_breakeven"
    assert actions[0]["price"] == 0.0016
    assert ("cancel_order", "sl1", "AKE/USDT:USDT") in client.calls


def test_manage_does_nothing_when_tp1_still_open(monkeypatch):
    open_orders = [
        {"symbol": "AKE/USDT:USDT", "id": "sl1", "clientOrderId": "tag-sl", "stopPrice": 0.0014},
        {"symbol": "AKE/USDT:USDT", "id": "tp1", "clientOrderId": "tag-tp1"},
        {"symbol": "AKE/USDT:USDT", "id": "tp2", "clientOrderId": "tag-tp2"},
    ]
    client = FakeClient(positions=_POS, open_orders=open_orders)
    actions = manage_open_positions(client=client, eod_hour_utc=25, eod_minute_utc=0)
    assert actions == []


def test_manage_is_idempotent_when_sl_already_at_breakeven(monkeypatch):
    open_orders = [
        {"symbol": "AKE/USDT:USDT", "id": "sl1", "clientOrderId": "tag-sl", "stopPrice": 0.0016},
        {"symbol": "AKE/USDT:USDT", "id": "tp2", "clientOrderId": "tag-tp2"},
    ]
    client = FakeClient(positions=_POS, open_orders=open_orders)
    actions = manage_open_positions(client=client, eod_hour_utc=25, eod_minute_utc=0)
    assert actions == []  # already at breakeven -- must not fire again


def test_manage_closes_and_cancels_past_eod():
    open_orders = [
        {"symbol": "AKE/USDT:USDT", "id": "sl1", "clientOrderId": "tag-sl", "stopPrice": 0.0014},
        {"symbol": "AKE/USDT:USDT", "id": "tp2", "clientOrderId": "tag-tp2"},
    ]
    client = FakeClient(positions=_POS, open_orders=open_orders)
    now = dt.datetime.now(dt.timezone.utc)
    actions = manage_open_positions(client=client, eod_hour_utc=now.hour, eod_minute_utc=0)
    assert len(actions) == 1
    assert actions[0]["action"] == "eod_close"
    close_calls = [c for c in client.calls if c[0] == "create_order" and c[6] and c[6].get("reduceOnly")]
    assert len(close_calls) == 1
    assert close_calls[0][3] == "sell"  # closing a long -> sell
    cancel_calls = [c for c in client.calls if c[0] == "cancel_order"]
    assert len(cancel_calls) == 2  # both open orders cancelled

"""
Crypto execution layer — 2026-07-18.

Hard rule this module enforces in its own structure, not just by convention:
NEW trade entries require an explicit human-triggered API call (a button
click hitting POST /api/crypto/execute). Nothing in this module runs on a
timer or background loop to open a position on its own initiative.

Managing an ALREADY-OPEN position (breakeven, trailing behind new structure)
is different and safe to automate -- see manage_open_positions(), meant to
be called from a polling loop -- because it only ever reduces risk on a
decision a human already made, never takes on new risk.

Position sizing reuses CryptoCosts.calc_lots (same math validated all
session) against the account's REAL fetched balance and BingX's real
market specs (min notional, qty precision) -- not a hardcoded number.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ccxt

from backtesting.engine.costs import CryptoCosts

BINGX_TAKER_FEE = 0.0005
BINGX_MAKER_FEE = 0.0002
BINGX_MIN_NOTIONAL = 2.0
DEFAULT_RISK_PCT = 0.005
DEFAULT_LEVERAGE = 50.0


class ExecutionError(Exception):
    pass


def get_client() -> ccxt.bingx:
    key = os.environ.get("BINGX_API_KEY")
    secret = os.environ.get("BINGX_API_SECRET")
    if not key or not secret:
        raise ExecutionError("BINGX_API_KEY / BINGX_API_SECRET not set in environment")
    return ccxt.bingx({"apiKey": key, "secret": secret, "options": {"defaultType": "swap"}})


def _market_specs(client: ccxt.bingx, symbol: str) -> dict:
    markets = client.load_markets()
    m = markets.get(symbol, {})
    limits = m.get("limits", {})
    precision = m.get("precision", {})
    return {
        "min_notional": (limits.get("cost") or {}).get("min", 0.0) or BINGX_MIN_NOTIONAL,
        "min_qty": (limits.get("amount") or {}).get("min", 0.0) or 0.0,
        "qty_step": precision.get("amount", 0.0) or 0.0,
        "tick_size": precision.get("price", 0.0) or 0.0,
    }


def account_state(client: Optional[ccxt.bingx] = None) -> dict:
    """Read-only: current USDT balance + open positions. Safe to call anytime."""
    client = client or get_client()
    bal = client.fetch_balance()
    positions = client.fetch_positions()
    open_positions = [p for p in positions if float(p.get("contracts") or 0) != 0]
    return {
        "usdt_free": (bal.get("USDT") or {}).get("free", 0.0),
        "usdt_total": (bal.get("USDT") or {}).get("total", 0.0),
        "open_positions": len(open_positions),
        "positions": [
            {"symbol": p["symbol"], "side": p.get("side"), "contracts": p.get("contracts"),
             "entryPrice": p.get("entryPrice"), "unrealizedPnl": p.get("unrealizedPnl")}
            for p in open_positions
        ],
    }


def size_trade(symbol: str, direction: str, entry: float, sl: float,
                risk_pct: float = DEFAULT_RISK_PCT, leverage: float = DEFAULT_LEVERAGE,
                client: Optional[ccxt.bingx] = None) -> dict:
    """Compute position size against REAL account balance and REAL market
    specs. Read-only (no order placed) -- safe to call to preview a trade
    before deciding whether to execute it."""
    client = client or get_client()
    specs = _market_specs(client, symbol)
    state = account_state(client)
    equity = state["usdt_total"]

    costs = CryptoCosts(
        maker_fee=BINGX_MAKER_FEE, taker_fee=BINGX_TAKER_FEE, leverage=leverage,
        min_notional=specs["min_notional"], min_qty=specs["min_qty"],
        qty_step=specs["qty_step"], tick_size=specs["tick_size"],
    )
    stop_dist = abs(entry - sl)
    lots = costs.calc_lots(equity, risk_pct, stop_dist, price=entry)
    notional = lots * entry

    return {
        "symbol": symbol, "direction": direction, "equity": equity,
        "risk_pct": risk_pct, "entry": entry, "sl": sl, "stop_dist": stop_dist,
        "lots": lots, "notional": notional,
        "min_notional": specs["min_notional"],
        "tradeable": lots > 0 and notional >= specs["min_notional"],
        "reject_reason": None if lots > 0 else (
            f"equity {equity} too small for min_notional {specs['min_notional']} "
            f"at risk_pct {risk_pct} with stop_dist {stop_dist}"
        ),
    }


def execute_trade(symbol: str, direction: str, entry: float, sl: float, tp: float,
                   risk_pct: float = DEFAULT_RISK_PCT, leverage: float = DEFAULT_LEVERAGE,
                   confirm: bool = False) -> dict:
    """Places a REAL order on the connected BingX account. Only ever called
    from the explicit POST /api/crypto/execute route -- a human clicking a
    button -- never from a loop. `confirm=True` is required or this refuses
    to do anything; that flag must come from the actual button click, not
    a default, so no code path can fire an order by accident."""
    if not confirm:
        raise ExecutionError("execute_trade requires confirm=True from an explicit user action")

    client = get_client()
    sizing = size_trade(symbol, direction, entry, sl, risk_pct, leverage, client=client)
    if not sizing["tradeable"]:
        raise ExecutionError(sizing["reject_reason"] or "position not tradeable")

    side = "buy" if direction == "long" else "sell"
    client.set_leverage(leverage, symbol)

    order = client.create_order(symbol, "market", side, sizing["lots"])
    sl_side = "sell" if direction == "long" else "buy"
    sl_order = client.create_stop_loss_order(symbol, "market", sl_side, sizing["lots"], stopLossPrice=sl)
    tp_order = client.create_take_profit_order(symbol, "market", sl_side, sizing["lots"], takeProfitPrice=tp)

    return {
        "entry_order": order.get("id"), "sl_order": sl_order.get("id"), "tp_order": tp_order.get("id"),
        "sizing": sizing,
    }


def manage_open_positions(client: Optional[ccxt.bingx] = None) -> list[dict]:
    """Safe to automate: only tightens stops on positions a human already
    opened, per the breakeven/structural-trail rules from position_manager.py.
    NOT YET IMPLEMENTED -- placeholder so this gap is visible, not silently
    assumed done. Needs: a loop that calls this on an interval, structure
    computed on each open position's symbol, and moves SL via
    client.edit_order / cancel+recreate the SL order once the trade has
    moved far enough in profit or new structure confirms it."""
    raise NotImplementedError(
        "Live position management (breakeven/trailing on open trades) is not "
        "built yet -- backtest-time logic exists in crypto/position_manager.py "
        "but nothing runs it against real open positions on an interval."
    )

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

_JOURNAL_ACCOUNT_NAME = "BingX Crypto (live)"


def _journal_account_id() -> int:
    """Get-or-create the journal account row every crypto trade logs
    against. Reuses the existing, already-tested relational journal
    (bot/journal/) instead of a new store -- this IS "a journal you can
    analyze", not a placeholder for one."""
    from bot.journal.crud import get_accounts, create_account
    for acc in get_accounts():
        if acc.get("name") == _JOURNAL_ACCOUNT_NAME:
            return acc["id"]
    return create_account(
        name=_JOURNAL_ACCOUNT_NAME, currency="USDT", initial_balance=20.0,
        broker="BingX", platform="ccxt", risk_per_trade_pct=DEFAULT_RISK_PCT * 100,
    )


def _structural_snapshot(symbol: str) -> dict:
    """Best-effort: attach the structural read (trend/FVG/OI) at the
    moment of execution as indicator_data, so a closed trade can later be
    analyzed against what the setup actually looked like -- not just
    entry/exit prices. Never blocks execution if it fails."""
    try:
        from webapp.crypto_watch import snapshot
        bare_symbol = symbol.replace("/USDT:USDT", "USDT").replace("/", "")
        return snapshot(bare_symbol)
    except Exception as e:
        return {"snapshot_error": f"{type(e).__name__}: {e}"}


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


# ORB's validated ladder (backtesting/lvl2_orb/orb_wide_stop.py _make_signal,
# multi_target=True): 50% at 2R, 30% at 5R, remaining 20% rides to 10R.
# Kept as named constants here so the execution layer can't silently drift
# from what was actually backtested.
TP1_R, TP1_FRAC = 2.0, 0.5
TP2_R, TP2_FRAC = 5.0, 0.3
TP3_R, TP3_FRAC = 10.0, 0.2

TP1_CLIENT_ID_SUFFIX = "-tp1"
TP2_CLIENT_ID_SUFFIX = "-tp2"
TP3_CLIENT_ID_SUFFIX = "-tp3"
SL_CLIENT_ID_SUFFIX = "-sl"


def execute_trade(symbol: str, direction: str, entry: float, sl: float,
                   risk_pct: float = DEFAULT_RISK_PCT, leverage: float = DEFAULT_LEVERAGE,
                   confirm: bool = False) -> dict:
    """Places a REAL order on the connected BingX account. Only ever called
    from the explicit POST /api/crypto/execute route -- a human clicking a
    button -- never from a loop. `confirm=True` is required or this refuses
    to do anything; that flag must come from the actual button click, not
    a default, so no code path can fire an order by accident.

    Mirrors ORB's actual backtested mechanics, not a simplified version:
    SL at the full stop distance (the strategy's own SL, e.g. the opposite
    side of the opening range), and a 3-tier TP ladder (2R/5R/10R at
    50/30/20%) instead of one all-or-nothing target. `tp` isn't a
    parameter here anymore -- it's derived from `sl`'s risk distance so the
    ladder can never drift from what was backtested."""
    if not confirm:
        raise ExecutionError("execute_trade requires confirm=True from an explicit user action")

    client = get_client()
    sizing = size_trade(symbol, direction, entry, sl, risk_pct, leverage, client=client)
    if not sizing["tradeable"]:
        raise ExecutionError(sizing["reject_reason"] or "position not tradeable")

    lots = sizing["lots"]
    risk = abs(entry - sl)
    sign = 1 if direction == "long" else -1
    side = "buy" if direction == "long" else "sell"
    exit_side = "sell" if direction == "long" else "buy"
    tag = f"{symbol.replace('/', '').replace(':', '')}-{int(entry * 1e8)}"

    client.set_leverage(leverage, symbol)
    order = client.create_order(symbol, "market", side, lots)
    sl_order = client.create_stop_loss_order(symbol, "market", exit_side, lots, stopLossPrice=sl,
                                              params={"clientOrderId": tag + SL_CLIENT_ID_SUFFIX})

    tp_orders = []
    for r_mult, frac, suffix in [(TP1_R, TP1_FRAC, TP1_CLIENT_ID_SUFFIX),
                                   (TP2_R, TP2_FRAC, TP2_CLIENT_ID_SUFFIX),
                                   (TP3_R, TP3_FRAC, TP3_CLIENT_ID_SUFFIX)]:
        tp_price = entry + sign * r_mult * risk
        tp_lots = lots * frac
        tp_order = client.create_order(symbol, "limit", exit_side, tp_lots, tp_price,
                                        params={"reduceOnly": True, "clientOrderId": tag + suffix})
        tp_orders.append({"id": tp_order.get("id"), "r_mult": r_mult, "price": tp_price, "lots": tp_lots})

    trade_id = None
    try:
        import datetime as _dt
        from bot.journal.crud import create_trade
        # "strategy" column doesn't exist on the live trades table (more
        # schema drift, found alongside the entry/sl/tp NOT NULL bug) --
        # create_trade() silently drops unknown columns, so fold it into
        # indicator_data too rather than lose it.
        snapshot = _structural_snapshot(symbol)
        snapshot["_strategy"] = "orb_wide_stop"
        trade_id = create_trade(
            account_id=_journal_account_id(), symbol=symbol, direction=direction.upper(),
            entry_price=entry, position_size=lots, ts_open=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            asset_type="crypto", sl_price=sl, tp_price=entry + sign * TP3_R * risk,
            timeframe="5m", strategy="orb_wide_stop", external_id=order.get("id"),
            provider="bingx", indicator_data=snapshot,
        )
    except Exception as e:
        # Journal logging must never block or roll back a real order that
        # already filled -- the trade is live either way. Surface the
        # failure in the response instead of silently losing the record.
        journal_error = f"{type(e).__name__}: {e}"
    else:
        journal_error = None

    return {
        "entry_order": order.get("id"), "sl_order": sl_order.get("id"),
        "tp_orders": tp_orders, "tag": tag, "sizing": sizing,
        "journal_trade_id": trade_id, "journal_error": journal_error,
    }


def _find_open_journal_trade(symbol: str) -> Optional[dict]:
    """Best-effort match: the journal doesn't persist a live order-id-to-
    trade-id map across process restarts, so this matches on symbol +
    OPEN status within the crypto account. Fine for a single-position-per-
    symbol assumption (which execute_trade already enforces via the
    exchange itself); would need a real mapping if that assumption changes."""
    try:
        from bot.journal.crud import get_open_trades
        bare_symbol = symbol.replace("/USDT:USDT", "USDT").replace("/", "")
        for t in get_open_trades(account_id=_journal_account_id()):
            if t.get("symbol") in (symbol, bare_symbol):
                return t
    except Exception:
        pass
    return None


def _log_journal_sl_move(symbol: str, new_sl: float) -> None:
    trade = _find_open_journal_trade(symbol)
    if trade:
        from bot.journal.crud import update_trade_sl_tp
        update_trade_sl_tp(trade["id"], sl_price=new_sl, tp_price=trade.get("tp_price"))


def _log_journal_close(symbol: str, close_order: dict) -> None:
    trade = _find_open_journal_trade(symbol)
    if not trade:
        return
    exit_price = close_order.get("average") or close_order.get("price")
    if not exit_price:
        return  # don't guess a fill price -- leave the trade OPEN in the journal rather than log a wrong exit
    from bot.journal.crud import close_trade
    # "MANUAL" matches the existing outcome vocabulary (TP/SL/MANUAL/OPEN,
    # see bot/journal/stats.py) rather than inventing a new value other
    # code doesn't recognize -- the actual EOD reason is in the payload.
    close_trade(trade["id"], exit_price=float(exit_price), outcome="MANUAL",
                event_type="eod_close", provider="bingx", payload={"reason": "eod_cutoff"})


def manage_open_positions(client: Optional[ccxt.bingx] = None, eod_hour_utc: int = 19,
                           eod_minute_utc: int = 55) -> list[dict]:
    """Safe to automate (only reduces risk on positions a human already
    opened, never opens anything new). Meant to be called from a polling
    loop on a short interval (e.g. every 30-60s).

    Two things, matching ORB's actual live-trade lifecycle:
      1. TP1 filled -> move SL to breakeven for the remaining size. Detected
         by the TP1 order (tagged '-tp1') no longer being open while the SL
         order still sits at the original (non-breakeven) price -- avoids
         needing a separate persistent trade database for this check.
      2. Past EOD cutoff (15:55 America/New_York, expressed here in UTC
         since exchange timestamps are UTC) -> cancel remaining orders and
         market-close whatever's left. ORB never holds overnight; this is
         the live-side enforcement of that, mirroring eod_min in
         orb_wide_stop.py.

    NOT YET LIVE-TESTED against a real open position -- the account has
    been at $0 balance all session, so there has never been a position for
    this to actually manage. Logic is covered by
    backtesting/tests/test_crypto_execute.py against a mock client; that is
    NOT the same as proving it against a real BingX fill. Treat the first
    live run as a supervised test, not a proven-safe automation.
    """
    import datetime as _dt

    client = client or get_client()
    positions = client.fetch_positions()
    open_positions = [p for p in positions if float(p.get("contracts") or 0) != 0]
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    past_eod = (now_utc.hour, now_utc.minute) >= (eod_hour_utc, eod_minute_utc)

    actions = []
    for pos in open_positions:
        symbol = pos["symbol"]
        direction = "long" if pos.get("side") == "long" else "short"
        entry_price = float(pos.get("entryPrice") or 0)
        contracts = float(pos.get("contracts") or 0)
        open_orders = client.fetch_open_orders(symbol)
        tp1_open = any(o.get("clientOrderId", "").endswith(TP1_CLIENT_ID_SUFFIX) for o in open_orders)
        sl_orders = [o for o in open_orders if o.get("clientOrderId", "").endswith(SL_CLIENT_ID_SUFFIX)]

        if past_eod:
            for o in open_orders:
                client.cancel_order(o["id"], symbol)
            close_side = "sell" if direction == "long" else "buy"
            close_order = client.create_order(symbol, "market", close_side, contracts, params={"reduceOnly": True})
            _log_journal_close(symbol, close_order)
            actions.append({"symbol": symbol, "action": "eod_close", "contracts": contracts})
            continue

        if not tp1_open and sl_orders:
            sl_order = sl_orders[0]
            sl_price = float(sl_order.get("stopPrice") or sl_order.get("price") or 0)
            already_be = abs(sl_price - entry_price) < entry_price * 1e-6
            if not already_be:
                client.cancel_order(sl_order["id"], symbol)
                exit_side = "sell" if direction == "long" else "buy"
                new_sl = client.create_stop_loss_order(
                    symbol, "market", exit_side, contracts, stopLossPrice=entry_price,
                    params={"clientOrderId": sl_order.get("clientOrderId", "") or (symbol + SL_CLIENT_ID_SUFFIX)})
                _log_journal_sl_move(symbol, entry_price)
                actions.append({"symbol": symbol, "action": "moved_sl_to_breakeven",
                                 "new_sl_order": new_sl.get("id"), "price": entry_price})

    return actions

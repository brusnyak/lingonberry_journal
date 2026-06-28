#!/usr/bin/env python3
"""
TradeLocker Position Manager — standalone entry point.

Reads TL_ACC_NUM_MASTER (or TL_MASTER_ACCOUNT) for the account to manage.
Uses TradelockerClient as the broker adapter.  Delegates all trailing/breakeven
logic to infra.position_manager.PositionManager.

Environment:
    TL_ACTIVE_ENV          demo|live (default demo)
    TL_ENVIRONMENT_LIVE    TradeLocker server URL
    TL_USERNAME_LIVE       Email
    TL_PASSWORD_LIVE       Password
    TL_SERVER_LIVE         Server (GFTTL)

    TL_MASTER_ACCOUNT      Account number to manage (default: first from TL_ACC_NUM_MASTER)
    PM_DRY_RUN             true → log actions, no SL modifications (default true)
    PM_POLL_INTERVAL       Seconds between polls (default 5)
    All other PM_* vars    see infra/position_manager.py

Usage:
    # Export env vars, then:
    python3 infra/tl_position_manager.py

    # With args:
    python3 infra/tl_position_manager.py --dry-run --poll 3 --account 2165806
"""
from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tl-pm")


def main():
    import argparse

    ap = argparse.ArgumentParser(description="TradeLocker Position Manager")
    ap.add_argument("--dry-run", action="store_true", help="Log only, no SL modifications")
    ap.add_argument("--poll", type=int, default=None, help="Poll interval seconds")
    ap.add_argument("--account", type=int, default=None, help="Account ID to manage")
    ap.add_argument("--test", action="store_true", help="Run one eval cycle and exit")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["PM_DRY_RUN"] = "true"
    if args.poll is not None:
        os.environ["PM_POLL_INTERVAL"] = str(args.poll)

    # Resolve account ID
    account_id = args.account
    if account_id is None:
        account_id = int(os.getenv("TL_MASTER_ACCOUNT", os.getenv("TL_ACC_NUM_MASTER", "0")))
    if account_id == 0:
        log.error("No account specified. Set TL_MASTER_ACCOUNT or pass --account")
        sys.exit(1)

    log.info("Connecting TradeLocker account %s...", account_id)

    from infra.tradelocker_client import TradelockerClient

    client = TradelockerClient(account_ids=[account_id])
    client.connect()

    log.info("Connected. Balance=%.2f  Equity=%.2f",
             client.get_balance(), client.get_equity())

    from infra.position_manager import PositionManager

    pm = PositionManager(client=client, account_ids=[account_id])

    if args.test:
        pm.eval_once()
        pm._log_managed_state()
        return

    pm.run()


if __name__ == "__main__":
    main()

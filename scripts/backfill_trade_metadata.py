#!/usr/bin/env python3
"""Backfill normalized session labels and RR ratios for historical trades."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import journal_db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", type=int, help="Only backfill trades for one account")
    args = parser.parse_args()

    journal_db.init_db()
    result = journal_db.backfill_trade_metadata(account_id=args.account_id)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Trade Logger — JSONL event log for the strategy bundle.

Writes structured trade events to data/trades/YYYY-MM-DD.jsonl.
One JSON object per line.  Queryable with jq or pandas later.

Events:
  signal    — strategy detected a signal (may or may not trade)
  open      — position opened
  close     — position closed
  modify_sl — stop loss changed
  modify_tp — take profit changed
  error     — something went wrong
  heartbeat — periodic status
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("trade-logger")

_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "trades",
)


class TradeLogger:
    """Thread-safe JSONL trade event logger."""

    def __init__(self, log_dir: str | None = None):
        self._log_dir = log_dir or _LOG_DIR
        os.makedirs(self._log_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._file = None  # current day's file handle
        self._date = ""    # current date string

    # ── Public ────────────────────────────────────────────────────────────

    def log(self, event: str, symbol: str, **kwargs):
        """Write a trade event line.

        Args:
            event: Event type (signal, open, close, modify_sl, error, heartbeat).
            symbol: Trading symbol (e.g. BTCUSD).
            kwargs: Any additional fields to include in the JSON line.
        """
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event,
            "symbol": symbol.upper(),
        }
        record.update(kwargs)

        with self._lock:
            self._write(record)

    def close(self):
        """Close current file handle."""
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _daily_path(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self._log_dir, f"{today}.jsonl")

    def _write(self, record: dict[str, Any]):
        path = self._daily_path()
        date_part = path.split("/")[-1].replace(".jsonl", "")

        # Rotate file at day boundary
        if date_part != self._date:
            if self._file:
                self._file.close()
            self._file = open(path, "a")
            self._date = date_part

        line = json.dumps(record, default=str) + "\n"
        self._file.write(line)
        self._file.flush()

    def __del__(self):
        self.close()


# ── Module-level singleton ────────────────────────────────────────────────────

_LOGGER: TradeLogger | None = None
_LOCK = threading.Lock()


def get_logger(log_dir: str | None = None) -> TradeLogger:
    global _LOGGER
    with _LOCK:
        if _LOGGER is None:
            _LOGGER = TradeLogger(log_dir=log_dir)
    return _LOGGER

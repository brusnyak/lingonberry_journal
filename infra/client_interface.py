"""
Client Interface — abstract contract for Position Manager.

Position Manager is the only component that needs to swap between
CtraderClient (live) and a future TradelockerClient. The strategy
stays cTrader-native.

Define only the methods Position Manager actually calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ClientInterface(ABC):
    """Minimal client interface that PositionManager depends on."""

    @property
    @abstractmethod
    def account_ids(self) -> list[int]:
        """Account IDs this client can operate on."""

    @abstractmethod
    def connect(self) -> None:
        """Connect and auth all accounts."""

    @abstractmethod
    def get_positions(self, account_id: int | None = None) -> list[Any]:
        """Return open positions for account_id (or primary)."""

    @abstractmethod
    def get_ohlc(
        self,
        symbol: str,
        period: int = 2,
        count: int = 50,
        account_id: int | None = None,
    ) -> Any:
        """Return OHLC DataFrame for symbol."""

    @abstractmethod
    def modify_sltp(
        self,
        position_id: int,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        account_id: int | None = None,
    ) -> Any:
        """Modify SL/TP on an open position. Returns result object."""

    @abstractmethod
    def close_position(
        self,
        position_id: int,
        volume: int = 0,
        account_id: int | None = None,
    ) -> Any:
        """Close a position (full or partial). Returns result object."""

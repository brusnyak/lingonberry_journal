"""Helpers for exchange-aware crypto futures cost models."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from backtesting.engine.costs import CryptoCosts
from backtesting.crypto.data import load_funding_rate

ROOT = Path(__file__).resolve().parent.parent.parent
CRYPTO_DATA_DIR = ROOT / "data" / "market_data" / "crypto"


def load_market_spec(symbol: str, exchange: str) -> dict:
    """Return the latest stored market-spec row for a symbol/exchange."""
    path = CRYPTO_DATA_DIR / exchange.lower() / "market_specs.parquet"
    if not path.exists():
        return {}

    try:
        specs = pd.read_parquet(path)
    except Exception:
        return {}

    if specs.empty:
        return {}

    wanted = symbol.upper()
    ids = specs.get("id", pd.Series(dtype=str)).astype(str).str.upper()
    symbols = specs.get("symbol", pd.Series(dtype=str)).astype(str).str.upper()
    mask = (ids == wanted) | symbols.str.replace("/", "", regex=False).str.replace(":USDT", "", regex=False).eq(wanted)
    rows = specs.loc[mask].copy()
    if rows.empty:
        return {}

    if "ts" in rows.columns:
        rows["ts"] = pd.to_datetime(rows["ts"], utc=True, errors="coerce")
        rows = rows.sort_values("ts")
    return rows.iloc[-1].to_dict()


def _float_or_zero(value) -> float:
    if value is None or pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_crypto_costs(
    symbol: str,
    *,
    exchange: str = "binance",
    leverage: float = 10.0,
    pip_size: float = 1.0,
    funding_df: Optional[pd.DataFrame] = None,
) -> CryptoCosts:
    """Build a realistic crypto cost model from stored funding/spec data."""
    spec = load_market_spec(symbol, exchange)
    if funding_df is None:
        funding_df = load_funding_rate(symbol, exchange=exchange)

    return CryptoCosts(
        leverage=leverage,
        pip_size=pip_size,
        funding_df=funding_df,
        qty_step=_float_or_zero(spec.get("amount_precision")),
        min_qty=_float_or_zero(spec.get("min_qty")),
        min_notional=_float_or_zero(spec.get("min_notional")),
        tick_size=_float_or_zero(spec.get("price_precision")),
    )

"""TradeLocker data source.

This project expects a DataSource to:
- return OHLCV as a pandas.DataFrame with a DatetimeIndex
- columns: open, high, low, close, volume

Implementation note
--------------------
TradeLocker does not provide a simple public OHLCV REST API. Most access flows
are via authenticated endpoints used by the web UI.

This adapter is implemented as a lightweight, UI-driven HTTP client using the
provided credentials from backend/.env.

If the underlying endpoints differ (they can change without notice), adjust
`_session_request()` + `_instrument_to_url()` accordingly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from src.data.base import DataSource
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


@dataclass(frozen=True)
class TradeLockerInstrument:
    instrument_id: int
    symbol: str


class TradeLockerSource(DataSource):
    """TradeLocker data source using authenticated web endpoints."""

    # These environment variables are expected in backend/.env
    TL_ENVIRONMENT = "TL_ENVIRONMENT"
    TL_USERNAME = "TL_USERNAME"
    TL_PASSWORD = "TL_PASSWORD"
    TL_SERVER = "TL_SERVER"

    # Default minimal mapping based on your examples.
    DEFAULT_SYMBOL_TO_INSTRUMENT: Dict[str, int] = {
        "GBPUSD": 6933,
        "EURUSD": 6920,
    }

    def __init__(
        self,
        symbol_to_instrument: Optional[Dict[str, int]] = None,
        timeout_s: int = 30,
    ):
        self.base_env_url = os.getenv(self.TL_ENVIRONMENT, "").rstrip("/")
        self.username = os.getenv(self.TL_USERNAME, "")
        self.password = os.getenv(self.TL_PASSWORD, "")
        self.server = os.getenv(self.TL_SERVER, "")
        self.timeout_s = timeout_s

        if not self.base_env_url:
            logger.warning("TradeLockerSource: TL_ENVIRONMENT is empty; calls will fail")

        self.symbol_to_instrument = symbol_to_instrument or dict(self.DEFAULT_SYMBOL_TO_INSTRUMENT)

        self._http = requests.Session()
        self._authenticated = False

    def is_available(self) -> bool:
        # Best-effort auth check.
        try:
            self._authenticate()
            return True
        except Exception as exc:
            logger.warning("TradeLockerSource not available: %s", exc)
            return False

    def get_available_symbols(self) -> List[str]:
        return sorted(self.symbol_to_instrument.keys())

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV.

        timeframe mapping
        ------------------
        TradeLocker uses human timeframes like M1/H1/D1 in its UI. We map the
        timeframe strings used in this repo (1,5,15,30,60,240,1440) or
        Binance-style (1m,5m,1h,4h,1d).

        Since TradeLocker endpoint specifics can vary, this method currently
        targets a best-effort candle endpoint.
        """
        try:
            self._authenticate()
        except Exception as exc:
            # Keep going: some endpoints may work without a separate login call,
            # or auth can be established lazily.
            logger.warning("TradeLocker auth failed; attempting fetch anyway: %s", exc)

        if symbol not in self.symbol_to_instrument:
            raise ValueError(f"Unknown TradeLocker symbol: {symbol}")
        instrument_id = self.symbol_to_instrument[symbol]

        tl_tf = self._normalize_timeframe(timeframe)

        # Compute a date window. We request more than needed and then slice.
        if since is None:
            # request last ~limit bars
            end = datetime.now(tz=timezone.utc)
            since = end - self._tf_delta(tl_tf) * max(1, limit)
        else:
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)

        params = {
            "instrument": instrument_id,
            "timeframe": tl_tf,
            "from": int(since.timestamp()),
            "to": int(datetime.now(tz=timezone.utc).timestamp()),
        }

        raw = self._fetch_candles_raw(params)
        df = self._coerce_ohlcv(raw)

        if df.empty:
            return df

        if limit and len(df) > limit:
            df = df.iloc[-limit:]

        return df

    # -------------------- internal helpers --------------------

    def _normalize_timeframe(self, timeframe: str) -> str:
        tf = str(timeframe).strip()

        # repo commonly uses: "1","5","15","30","60","240","1440".
        if tf.isdigit():
            minutes = int(tf)
            if minutes == 1:
                return "M1"
            if minutes == 5:
                return "M5"
            if minutes == 15:
                return "M15"
            if minutes == 30:
                return "M30"
            if minutes == 60:
                return "H1"
            if minutes == 240:
                return "H4"
            if minutes == 1440:
                return "D1"

        # Binance-style: 1m/5m/1h/4h/1d
        mapping = {
            "1m": "M1",
            "5m": "M5",
            "15m": "M15",
            "30m": "M30",
            "1h": "H1",
            "4h": "H4",
            "1d": "D1",
        }
        return mapping.get(tf, "M5")

    def _tf_delta(self, tl_tf: str) -> timedelta:
        if tl_tf == "M1":
            return timedelta(minutes=1)
        if tl_tf == "M5":
            return timedelta(minutes=5)
        if tl_tf == "M15":
            return timedelta(minutes=15)
        if tl_tf == "M30":
            return timedelta(minutes=30)
        if tl_tf == "H1":
            return timedelta(hours=1)
        if tl_tf == "H4":
            return timedelta(hours=4)
        if tl_tf == "D1":
            return timedelta(days=1)
        return timedelta(minutes=5)

    def _authenticate(self) -> None:
        if self._authenticated:
            return
        if not (self.base_env_url and self.username and self.password and self.server):
            raise RuntimeError("TradeLocker credentials are missing from environment")

        # The web UI uses a login endpoint. We'll do a best-effort POST.
        # If your account requires a different flow, adjust this.
        # TradeLocker auth endpoints can vary by environment (demo/live) and can
        # be implemented either via JSON endpoints or form posts.
        # We attempt a couple of common endpoints; the first that returns 2xx wins.
        candidates = [
            f"{self.base_env_url}/api/trade/login",
            f"{self.base_env_url}/api/login",
            f"{self.base_env_url}/en/api/trade/login",
        ]

        payload = {
            "username": self.username,
            "password": self.password,
            "server": self.server,
        }

        last_resp: Optional[requests.Response] = None
        for login_url in candidates:
            try:
                resp = self._http.post(login_url, json=payload, timeout=self.timeout_s)
                last_resp = resp
                if resp.status_code < 400:
                    self._authenticated = True
                    logger.info("TradeLockerSource authenticated via %s", login_url)
                    return
            except Exception:
                continue

        if last_resp is not None and last_resp.status_code:
            raise ConnectionError(
                f"TradeLocker login failed: {last_resp.status_code} {last_resp.text[:200]}"
            )
        raise ConnectionError("TradeLocker login failed")


    def _instrument_to_url(self, instrument_id: int) -> str:
        return f"{self.base_env_url}/en/trade?instrument={instrument_id}"

    def _session_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        return self._http.request(method=method, url=url, timeout=self.timeout_s, **kwargs)

    def _fetch_candles_raw(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Best-effort candle endpoint. This may need adjustment.
        # We'll first attempt a JSON endpoint often used by such UIs.
        candidates = [
            f"{self.base_env_url}/api/trade/candles",
            f"{self.base_env_url}/api/candles",
            f"{self.base_env_url}/api/trading/candles",
        ]
        last_exc: Optional[Exception] = None
        for url in candidates:
            try:
                resp = self._session_request("GET", url, params=params)
                if resp.status_code >= 400:
                    continue
                data = resp.json()
                # Common shapes: {candles:[...]} or [...]
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for key in ("candles", "data", "results"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
                raise ValueError(f"Unexpected TradeLocker candle payload from {url}")
            except Exception as exc:  # pragma: no cover
                last_exc = exc
                continue

        raise ConnectionError(f"Unable to fetch candles from TradeLocker: {last_exc}")

    def _coerce_ohlcv(self, raw: Any) -> pd.DataFrame:
        if raw is None:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        if isinstance(raw, dict):
            raw = raw.get("candles") or raw.get("data") or []
        if not isinstance(raw, list):
            raise ValueError("TradeLocker candle payload is not a list")

        # Expect each row to carry a timestamp and OHLC(+volume).
        rows = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            ts = r.get("time") or r.get("timestamp") or r.get("t")
            o = r.get("open")
            h = r.get("high")
            l = r.get("low")
            c = r.get("close")
            v = r.get("volume") or r.get("vol") or 0.0
            if ts is None or o is None or h is None or l is None or c is None:
                continue
            # ts can be ms or seconds
            ts_num = float(ts)
            if ts_num > 1e12:
                ts_num = ts_num / 1000.0
            dt = datetime.fromtimestamp(ts_num, tz=timezone.utc)
            rows.append({
                "datetime": dt,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            })

        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_localize(None)
        df = df.sort_values("datetime")
        df.set_index("datetime", inplace=True)
        return df


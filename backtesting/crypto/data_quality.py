"""Data-quality guards for crypto research runs."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FundingCoverage:
    ok: bool
    reason: str | None
    ohlcv_start: pd.Timestamp | None
    ohlcv_end: pd.Timestamp | None
    funding_start: pd.Timestamp | None
    funding_end: pd.Timestamp | None
    start_lag_hours: float
    end_lag_hours: float


def check_funding_coverage(
    ohlcv: pd.DataFrame | dict[str, pd.DataFrame],
    funding_df: pd.DataFrame | None,
    *,
    max_lag_hours: float = 9.0,
) -> FundingCoverage:
    """Check that funding timestamps cover the OHLCV research window.

    Perp funding is typically every 8 hours. `max_lag_hours=9` allows a small
    timestamp offset while still catching stale or missing funding files.
    """
    ohlcv_start, ohlcv_end = _ohlcv_range(ohlcv)
    if ohlcv_start is None or ohlcv_end is None:
        return FundingCoverage(
            ok=False,
            reason="empty_ohlcv",
            ohlcv_start=ohlcv_start,
            ohlcv_end=ohlcv_end,
            funding_start=None,
            funding_end=None,
            start_lag_hours=0.0,
            end_lag_hours=0.0,
        )

    if funding_df is None or funding_df.empty or "ts" not in funding_df.columns:
        return FundingCoverage(
            ok=False,
            reason="missing_funding",
            ohlcv_start=ohlcv_start,
            ohlcv_end=ohlcv_end,
            funding_start=None,
            funding_end=None,
            start_lag_hours=0.0,
            end_lag_hours=0.0,
        )

    funding_ts = pd.to_datetime(funding_df["ts"], utc=True, errors="coerce").dropna()
    if funding_ts.empty:
        return FundingCoverage(
            ok=False,
            reason="missing_funding_timestamps",
            ohlcv_start=ohlcv_start,
            ohlcv_end=ohlcv_end,
            funding_start=None,
            funding_end=None,
            start_lag_hours=0.0,
            end_lag_hours=0.0,
        )

    funding_start = funding_ts.min()
    funding_end = funding_ts.max()
    start_lag_hours = max(0.0, (funding_start - ohlcv_start).total_seconds() / 3600)
    end_lag_hours = max(0.0, (ohlcv_end - funding_end).total_seconds() / 3600)

    if start_lag_hours > max_lag_hours:
        reason = f"funding_starts_after_ohlcv_by_{start_lag_hours:.1f}h"
        ok = False
    elif end_lag_hours > max_lag_hours:
        reason = f"funding_ends_before_ohlcv_by_{end_lag_hours:.1f}h"
        ok = False
    else:
        reason = None
        ok = True

    return FundingCoverage(
        ok=ok,
        reason=reason,
        ohlcv_start=ohlcv_start,
        ohlcv_end=ohlcv_end,
        funding_start=funding_start,
        funding_end=funding_end,
        start_lag_hours=round(start_lag_hours, 3),
        end_lag_hours=round(end_lag_hours, 3),
    )


def require_funding_coverage(
    ohlcv: pd.DataFrame | dict[str, pd.DataFrame],
    funding_df: pd.DataFrame | None,
    *,
    max_lag_hours: float = 9.0,
) -> FundingCoverage:
    coverage = check_funding_coverage(ohlcv, funding_df, max_lag_hours=max_lag_hours)
    if not coverage.ok:
        raise ValueError(format_funding_coverage_error(coverage))
    return coverage


def format_funding_coverage_error(coverage: FundingCoverage) -> str:
    return (
        f"funding coverage failed: {coverage.reason}; "
        f"ohlcv={coverage.ohlcv_start}..{coverage.ohlcv_end}; "
        f"funding={coverage.funding_start}..{coverage.funding_end}; "
        f"start_lag_h={coverage.start_lag_hours}; "
        f"end_lag_h={coverage.end_lag_hours}"
    )


def _ohlcv_range(ohlcv: pd.DataFrame | dict[str, pd.DataFrame]) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    frames = ohlcv.values() if isinstance(ohlcv, dict) else [ohlcv]
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for df in frames:
        if df is None or df.empty or "ts" not in df.columns:
            continue
        ts = pd.to_datetime(df["ts"], utc=True, errors="coerce").dropna()
        if ts.empty:
            continue
        starts.append(ts.min())
        ends.append(ts.max())
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)

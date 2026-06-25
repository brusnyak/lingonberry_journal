import json
import sys
import base64
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure


ROOT = Path(__file__).resolve().parents[3]
APP_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
STATIC_DIR = Path(__file__).parent / "static"
SESSIONS_DIR = ROOT / "data" / "review_sessions"
BACKTESTS_DIR = ROOT / "data" / "backtests"
ARTIFACTS_DIR = ROOT / "data" / "review_artifacts"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
BACKTESTS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

_LOCKS_GUARD = threading.Lock()
_SESSION_LOCKS: Dict[str, threading.Lock] = {}


def _get_session_lock(session_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _SESSION_LOCKS[session_id] = lock
        return lock


class ReviewTrade(BaseModel):
    id: str
    direction: str
    entry_time: int
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    notes: str = ""
    tags: List[str] = Field(default_factory=list)
    status: str = "pending"  # pending | done
    source: str = "manual"  # manual | backtest
    outcome: Optional[str] = None  # win | loss | breakeven | skip
    reason_tags: List[str] = Field(default_factory=list)
    manual_entry_price: Optional[float] = None
    manual_direction: Optional[str] = None
    manual_stop_loss: Optional[float] = None
    manual_take_profit: Optional[float] = None
    manual_exit_time: Optional[int] = None
    manual_exit_price: Optional[float] = None
    manual_hit_reason: Optional[str] = None  # take_profit | stop_loss | timeout | unknown
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewDrawing(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    type: str
    points: List[Dict[str, float]]
    style: Dict[str, Any] = Field(default_factory=dict)
    timeframe_created: Optional[str] = None
    note: str = ""
    # Preserve client-side metadata used for risk/reward reconstruction.
    side: Optional[str] = None
    trade_id: Optional[str] = None
    rr: Optional[Dict[str, Any]] = None


class ReviewSession(BaseModel):
    id: str
    name: str = "Review Session"
    symbol: str
    asset_type: Optional[str] = None
    timeframe: str = "1"
    trades: List[ReviewTrade] = Field(default_factory=list)
    drawings: List[ReviewDrawing] = Field(default_factory=list)
    starred_tools: List[str] = Field(default_factory=list)
    current_trade_index: int = 0
    finished: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateSessionRequest(BaseModel):
    symbol: str
    timeframe: str = "1"
    asset_type: Optional[str] = None
    name: str = "Review Session"
    backtest_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScreenshotArtifactRequest(BaseModel):
    screenshot_base64: str
    note: str = ""
    trade_id: Optional[str] = None
    tag: str = "manual_review"
    capture_mode: str = "chart_composite"
    chart_state: Optional[Dict[str, Any]] = None
    drawing_snapshot: Optional[List[Dict[str, Any]]] = None
    trade_snapshot: Optional[Dict[str, Any]] = None
    indicator_state: Optional[Dict[str, Any]] = None


app = FastAPI(title="Pine Review App", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/data", StaticFiles(directory=ROOT / "data"), name="data")


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_json_retry(path: Path, retries: int = 4, delay_s: float = 0.03) -> Dict[str, Any]:
    """
    Retry transient decode errors that can happen if a concurrent writer just rotated a file.
    """
    last_exc: Optional[Exception] = None
    for _ in range(max(1, retries)):
        try:
            return _read_json(path)
        except json.JSONDecodeError as exc:
            last_exc = exc
            time.sleep(delay_s)
    if last_exc is not None:
        raise last_exc
    return _read_json(path)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.stem}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.flush()
        temp_name = tmp.name
    Path(temp_name).replace(path)


def _asset_types() -> List[str]:
    roots = [ROOT / "data" / "parquet", APP_DATA_ROOT / "parquet"]
    asset_types = set()
    for parquet_root in roots:
        if not parquet_root.exists():
            continue
        for p in parquet_root.iterdir():
            if p.is_dir():
                asset_types.add(p.name)
    return sorted(asset_types)


def _discover_symbols(asset_type: Optional[str] = None) -> List[Dict[str, Any]]:
    parquet_roots = [ROOT / "data" / "parquet", APP_DATA_ROOT / "parquet"]
    markets = [asset_type] if asset_type else _asset_types()
    out: Dict[str, Dict[str, Any]] = {}

    for market in markets:
        for parquet_root in parquet_roots:
            market_dir = parquet_root / market
            if not market_dir.exists():
                continue
            for fp in market_dir.glob("*.parquet"):
                stem = fp.stem
                split_idx = len(stem)
                for i in range(len(stem) - 1, -1, -1):
                    if not stem[i].isdigit():
                        split_idx = i + 1
                        break
                symbol = stem[:split_idx]
                timeframe = stem[split_idx:]
                key = f"{market}:{symbol}"
                if key not in out:
                    out[key] = {"symbol": symbol, "asset_type": market, "timeframes": []}
                if timeframe and timeframe not in out[key]["timeframes"]:
                    out[key]["timeframes"].append(timeframe)

    for item in out.values():
        item["timeframes"].sort(key=lambda x: int(x) if x.isdigit() else x)
    return sorted(out.values(), key=lambda x: (x["asset_type"], x["symbol"]))


def _convert_backtest_trade(raw: Dict[str, Any], idx: int) -> ReviewTrade:
    # Supports common fields from strategy outputs.
    entry_time = raw.get("entry_time")
    exit_time = raw.get("exit_time")
    if isinstance(entry_time, str):
        ts = pd.Timestamp(entry_time)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        entry_time = int(ts.timestamp())
    if isinstance(exit_time, str):
        ts = pd.Timestamp(exit_time)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        exit_time = int(ts.timestamp())
    if entry_time is None:
        entry_time = 0

    return ReviewTrade(
        id=str(raw.get("id") or f"bt-{idx}-{uuid4().hex[:8]}"),
        direction=str(raw.get("direction", "long")).lower(),
        entry_time=int(entry_time),
        entry_price=float(raw.get("entry_price", 0.0)),
        stop_loss=float(raw["stop_loss"]) if raw.get("stop_loss") is not None else None,
        take_profit=float(raw["take_profit"]) if raw.get("take_profit") is not None else None,
        exit_time=int(exit_time) if exit_time is not None else None,
        exit_price=float(raw["exit_price"]) if raw.get("exit_price") is not None else None,
        notes=str(raw.get("notes", "")),
        tags=list(raw.get("tags", [])),
        status=str(raw.get("status", "pending")),
        source="backtest",
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/analytics")
def analytics_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "sessions.html")


@app.get("/signals")
def signals_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "signals.html")


@app.get("/api/sessions")
def list_sessions() -> Dict[str, Any]:
    sessions = []
    for fp in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = _read_json_retry(fp)
        except Exception:
            # Skip malformed/transient files rather than failing whole listing.
            continue
        trades = data.get("trades", [])
        done = sum(1 for t in trades if t.get("status") == "done")
        sessions.append(
            {
                "id": data.get("id", fp.stem),
                "name": data.get("name", fp.stem),
                "symbol": data.get("symbol"),
                "asset_type": data.get("asset_type"),
                "timeframe": data.get("timeframe"),
                "finished": bool(data.get("finished", False)),
                "trade_count": len(trades),
                "done_count": done,
                "updated_at": datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return {"sessions": sessions}


@app.get("/api/symbols")
def get_symbols(asset_type: Optional[str] = None) -> Dict[str, Any]:
    return {"symbols": _discover_symbols(asset_type)}


@app.get("/api/backtests")
def list_backtests() -> Dict[str, Any]:
    items = []
    for fp in sorted(BACKTESTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _read_json(fp)
        items.append(
            {
                "id": fp.stem,
                "name": payload.get("name", fp.stem),
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "trades": len(payload.get("trades", [])),
                "asset_type": payload.get("asset_type"),
            }
        )
    return {"backtests": items}


@app.get("/api/backtests/{backtest_id}")
def get_backtest(backtest_id: str) -> Dict[str, Any]:
    path = BACKTESTS_DIR / f"{backtest_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backtest file not found")
    return _read_json(path)


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest) -> Dict[str, Any]:
    sid = uuid4().hex[:12]
    trades: List[ReviewTrade] = []

    if req.backtest_id:
        bt_path = BACKTESTS_DIR / f"{req.backtest_id}.json"
        if not bt_path.exists():
            raise HTTPException(status_code=404, detail="Backtest file not found")
        bt = _read_json(bt_path)
        for i, trade in enumerate(bt.get("trades", [])):
            trades.append(_convert_backtest_trade(trade, i))
        # Align session chart context to backtest context to keep trades on-chart.
        if bt.get("symbol"):
            req.symbol = bt["symbol"]
        if bt.get("timeframe"):
            req.timeframe = str(bt["timeframe"])
        if bt.get("asset_type"):
            req.asset_type = bt["asset_type"]

    session = ReviewSession(
        id=sid,
        name=req.name,
        symbol=req.symbol,
        asset_type=req.asset_type,
        timeframe=req.timeframe,
        trades=trades,
        metadata=req.metadata,
    )
    _write_json(_session_path(sid), session.model_dump())
    return {"session_id": sid, "session": session.model_dump()}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    lock = _get_session_lock(session_id)
    with lock:
        try:
            return _read_json_retry(path)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=409, detail=f"Session file is corrupted: {exc}") from exc


@app.put("/api/sessions/{session_id}")
def put_session(session_id: str, payload: ReviewSession) -> Dict[str, Any]:
    if payload.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")
    lock = _get_session_lock(session_id)
    with lock:
        path = _session_path(session_id)
        incoming = payload.model_dump()
        # Preserve server-managed artifacts if client payload is stale.
        existing: Dict[str, Any] = {}
        if path.exists():
            try:
                existing = _read_json_retry(path)
            except Exception:
                existing = {}

        existing_artifacts = (
            existing.get("metadata", {}).get("artifacts", [])
            if isinstance(existing.get("metadata", {}), dict)
            else []
        )
        incoming.setdefault("metadata", {})
        incoming["metadata"].setdefault("artifacts", [])

        # Merge by file path first, then by id.
        seen_files = {str(a.get("file")) for a in incoming["metadata"]["artifacts"] if a.get("file")}
        seen_ids = {str(a.get("id")) for a in incoming["metadata"]["artifacts"] if a.get("id")}
        for a in existing_artifacts:
            f = str(a.get("file")) if a.get("file") else ""
            i = str(a.get("id")) if a.get("id") else ""
            if (f and f in seen_files) or (i and i in seen_ids):
                continue
            incoming["metadata"]["artifacts"].append(a)
            if f:
                seen_files.add(f)
            if i:
                seen_ids.add(i)

        _write_json(path, incoming)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/artifacts/screenshot")
def save_screenshot_artifact(session_id: str, req: ScreenshotArtifactRequest) -> Dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    art_dir = ARTIFACTS_DIR / session_id
    art_dir.mkdir(parents=True, exist_ok=True)

    if "," in req.screenshot_base64:
        _, encoded = req.screenshot_base64.split(",", 1)
    else:
        encoded = req.screenshot_base64

    try:
        img_bytes = base64.b64decode(encoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid screenshot payload: {exc}") from exc

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{ts}_{req.tag}_{req.trade_id or 'session'}.png"
    img_path = art_dir / file_name
    with img_path.open("wb") as f:
        f.write(img_bytes)

    meta = {
        "id": uuid4().hex[:12],
        "kind": "screenshot",
        "file": str(img_path.relative_to(ROOT)),
        "note": req.note,
        "trade_id": req.trade_id,
        "tag": req.tag,
        "capture_mode": req.capture_mode,
        "chart_state": req.chart_state or {},
        "drawing_snapshot": req.drawing_snapshot or [],
        "trade_snapshot": req.trade_snapshot or {},
        "indicator_state": req.indicator_state or {},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    lock = _get_session_lock(session_id)
    with lock:
        sess = _read_json_retry(path)
        sess.setdefault("metadata", {})
        sess["metadata"].setdefault("artifacts", [])
        sess["metadata"]["artifacts"].append(meta)
        _write_json(path, sess)

    return {"ok": True, "artifact": meta}


@app.get("/api/candles")
def get_candles(
    symbol: str,
    timeframe: str,
    asset_type: Optional[str] = None,
    limit: int = 3000,
) -> Dict[str, Any]:
    loader = DataLoader()
    parquet_root = ROOT / "data" / "parquet"

    try:
        df = loader.load(symbol, timeframe, limit=limit, prefer_parquet=True)
    except FileNotFoundError as exc:
        # Fallback: retry with explicit asset_type (if provided) and then auto-detect again.
        # This makes the endpoint resilient to UI/session asset_type mismatches.
        tried = []
        if asset_type:
            tried.append(f"explicit_asset_type={asset_type}")
            try:
                df = loader._load_parquet(symbol, timeframe, asset_type)  # noqa: SLF001
                if df is not None:
                    df = loader._filter_data(df, None, None, limit)  # noqa: SLF001
                    df = df.copy()
                    df.index = pd.to_datetime(df.index)
                    # If needed, ensure OHLC columns exist.
                    return {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "asset_type": asset_type,
                        "candles": [
                            {
                                "time": int(pd.Timestamp(ts).timestamp()),
                                "open": float(row["open"]),
                                "high": float(row["high"]),
                                "low": float(row["low"]),
                                "close": float(row["close"]),
                                "volume": float(row.get("volume", 0.0)),
                            }
                            for ts, row in df.iterrows()
                        ],
                    }
            except Exception:
                pass

        tried.append("auto_detect_asset_type")
        try:
            df = loader.load(symbol, timeframe, limit=limit, prefer_parquet=True)
        except Exception:
            df = None

        # Last resort: search for a matching parquet file under any asset_type folder.
        if df is None:
            target = f"{symbol}{timeframe}.parquet"
            matches = list(parquet_root.glob(f"*/{target}"))
            if matches:
                fp = matches[0]
                # asset_type is the parent folder name.
                mt = fp.parent.name
                # Load the exact parquet file instead of relying on loader path logic.
                try:
                    df = pd.read_parquet(fp)
                    if "datetime" in df.columns:
                        df["datetime"] = pd.to_datetime(df["datetime"])
                        df = df.set_index("datetime")
                    else:
                        df.index = pd.to_datetime(df.index)
                except Exception:
                    df = None

                if df is not None:
                    df = loader._filter_data(df, None, None, limit)  # noqa: SLF001
                    df = df.copy()
                    df.index = pd.to_datetime(df.index)
                    return {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "asset_type": mt,
                        "candles": [
                            {
                                "time": int(pd.Timestamp(ts).timestamp()),
                                "open": float(row["open"]),
                                "high": float(row["high"]),
                                "low": float(row["low"]),
                                "close": float(row["close"]),
                                "volume": float(row.get("volume", 0.0)),
                            }
                            for ts, row in df.iterrows()
                        ],
                    }

        # Give up with the original message.

        raise HTTPException(
            status_code=404,
            detail=f"No data found for {symbol} {timeframe}. Tried: {', '.join(tried)}. Original error: {exc}",
        ) from exc


    rows = []
    for ts, row in df.iterrows():
        rows.append(
            {
                "time": int(pd.Timestamp(ts).timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            }
        )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "asset_type": asset_type,
        "candles": rows,
    }


@app.get("/api/sessions/{session_id}/stats")
def get_session_stats(session_id: str) -> Dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    lock = _get_session_lock(session_id)
    with lock:
        try:
            sess = ReviewSession(**_read_json_retry(path))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=409, detail=f"Session file is corrupted: {exc}") from exc

    def calc_stats(trades: List[ReviewTrade], use_manual: bool):
        total = 0
        wins = 0
        pnl = 0.0
        for t in trades:
            if t.status != "done" and not use_manual:
                continue

            entry = t.manual_entry_price if use_manual and t.manual_entry_price else t.entry_price
            direction = t.manual_direction if use_manual and t.manual_direction else t.direction
            exit_p = t.manual_exit_price if use_manual and t.manual_exit_price is not None else t.exit_price
            if exit_p is None:
                exit_p = entry  # fallback

            if entry and exit_p:
                total += 1
                trade_pnl = 0
                if direction == "long":
                    trade_pnl = exit_p - entry
                else:
                    trade_pnl = entry - exit_p

                pnl += trade_pnl
                if trade_pnl > 0:
                    wins += 1

        return {
            "count": total,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "pnl": pnl,
        }

    return {
        "system": calc_stats(sess.trades, False),
        "manual": calc_stats(sess.trades, True),
    }


@app.get("/api/sessions/{session_id}/artifacts")
def get_session_artifacts(session_id: str) -> Dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    lock = _get_session_lock(session_id)
    with lock:
        try:
            sess = _read_json_retry(path)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=409, detail=f"Session file is corrupted: {exc}") from exc
        items = list(sess.get("metadata", {}).get("artifacts", []))
        seen_files = {str(i.get("file")) for i in items if i.get("file")}

        # Recover screenshots that exist on disk but were not indexed due previous write errors.
        art_dir = ARTIFACTS_DIR / session_id
        if art_dir.exists():
            for fp in sorted(art_dir.glob("*.png")):
                rel = str(fp.relative_to(ROOT))
                if rel in seen_files:
                    continue
                recovered = {
                    "id": uuid4().hex[:12],
                    "kind": "screenshot",
                    "file": rel,
                    "note": "recovered_artifact",
                    "trade_id": None,
                    "tag": "recovered",
                    "created_at": datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat(),
                }
                items.append(recovered)

        sess.setdefault("metadata", {})
        sess["metadata"]["artifacts"] = items
        _write_json(path, sess)

    return {"artifacts": items}


@app.get("/api/ict-overlay")
def get_ict_overlay(
    symbol: str,
    timeframe: str,
    asset_type: Optional[str] = None,
    limit: int = 1200,
) -> Dict[str, Any]:
    """
    Optional overlay feed for chart review: FVG, OB, and unswept liquidity.
    """
    loader = DataLoader()
    parquet_root = ROOT / "data" / "parquet"

    def _load_df() -> Any:
        # Simpler/consistent fallback: always load exact parquet file first.
        # This avoids relying on DataLoader's prefer_parquet + path heuristics.
        target = f"{symbol}{timeframe}.parquet"
        matches = list(parquet_root.glob(f"*/{target}"))
        if not matches and asset_type:
            # Best-effort explicit folder check.
            explicit = parquet_root / asset_type / target
            if explicit.exists():
                matches = [explicit]

        if matches:
            fp = matches[0]
            df_local = pd.read_parquet(fp)
            if "datetime" in df_local.columns:
                df_local["datetime"] = pd.to_datetime(df_local["datetime"])
                df_local = df_local.set_index("datetime")
            else:
                df_local.index = pd.to_datetime(df_local.index)
            if limit is not None and len(df_local) > limit:
                df_local = df_local.iloc[-limit:]
            return df_local

        # If parquet isn't present, keep the original loader behavior as last resort.
        return loader.load(symbol, timeframe, limit=limit, prefer_parquet=True)



    df = _load_df()
    # Debug header to understand why overlay may fail.


    if df is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol} {timeframe}")
    if len(df) == 0:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol} {timeframe}")



    ms = analyze_market_structure(df, volume_filter=False)

    # Keep overlays focused and readable for manual review.
    fvgs = [
        {
            "type": f.type,
            "top": float(f.top),
            "bottom": float(f.bottom),
            "time": int(pd.Timestamp(f.time).timestamp()),
            "index": int(f.index),
            "mitigated": bool(f.mitigated),
        }
        for f in ms.get("fvgs", [])
        if not f.mitigated
    ]
    obs = [
        {
            "type": o.type,
            "top": float(o.top),
            "bottom": float(o.bottom),
            "time": int(pd.Timestamp(o.time).timestamp()),
            "index": int(o.index),
            "mitigated": bool(o.mitigated),
        }
        for o in ms.get("order_blocks", [])
        if not o.mitigated
    ]
    liq = [
        {
            "type": l.type,
            "price": float(l.price),
            "start_time": int(pd.Timestamp(l.start_time).timestamp()),
            "swept": bool(l.swept),
        }
        for l in ms.get("liquidity_levels", [])
    ]
    breaks = [
        {
            "type": b.type,
            "direction": b.direction,
            "price": float(b.price),
            "time": int(pd.Timestamp(b.time).timestamp()),
            "index": int(b.index),
        }
        for b in ms.get("structure_breaks", [])
    ]

    swing_labels = ms.get("swing_labels", {}) or {}

    swing_label_items = []
    # ms["swing_labels"] maps swing index -> label string (HH/HL/LL/LH)
    # We need time+price for each swing point.
    for swing_index, label in swing_labels.items():
        try:
            idx_int = int(swing_index)
        except Exception:
            continue
        label_str = str(label)
        # Swing highs: indices reference original df index (ms detector uses i as df index)
        # Determine time/price from the closest swing point arrays.
        found = False
        for sp in ms.get("swing_highs", []) or []:
            if int(getattr(sp, "index", -1)) == idx_int and label_str in ("HH", "LH"):
                swing_label_items.append(
                    {
                        "time": int(pd.Timestamp(sp.time).timestamp()),
                        "price": float(sp.price),
                        "label": label_str,
                    }
                )
                found = True
                break
        if found:
            continue
        for sp in ms.get("swing_lows", []) or []:
            if int(getattr(sp, "index", -1)) == idx_int and label_str in ("HL", "LL"):
                swing_label_items.append(
                    {
                        "time": int(pd.Timestamp(sp.time).timestamp()),
                        "price": float(sp.price),
                        "label": label_str,
                    }
                )
                found = True
                break
        # If not found (label mismatch), skip.

    # Last N only to avoid clutter for structure labels too.
    swing_label_items = swing_label_items[-120:]

    # Keep overlays focused and readable for manual review.
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "fvgs": fvgs[-40:],
        "order_blocks": obs[-40:],
        "liquidity": liq[-24:],
        "structure_breaks": breaks[-36:],
        "swing_labels": swing_label_items,
    }

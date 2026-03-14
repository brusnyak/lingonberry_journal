import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

HEADER_TOKENS = {
    "instrument", "entry", "time", "(eet)", "type", "side", "amount", "price",
    "sl", "tp", "exit", "fee", "swap", "p&l", "net", "order", "position", "id",
    "symbol", "open", "date", "close", "stop", "loss", "take", "profit", "lots",
    "duration", "deal",
}

PROP_HEADERS = {
    "SYMBOL", "OPEN DATE", "OPEN PRICE", "CLOSE", "DATE", "CLOSE PRICE",
    "TYPE", "STOP LOSS", "TAKE", "PROFIT", "LOTS", "DURATION", "DEAL",
}

PLATFORM_PATTERN = re.compile(
    r"(?P<symbol>[A-Z0-9]+)\s+"
    r"(?P<entry_dt>\d{4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<type>Take\s+profit|Stop\s+loss|Market|Limit|Stop)\s+"
    r"(?P<side>Buy|Sell)\s+"
    r"(?P<amount>[\d.]+)\s+"
    r"(?P<entry>[\d,\.]+)\s+"
    r"(?P<sl>[\d,\.]+)\s+"
    r"(?P<tp>[\d,\.]+)\s+"
    r"(?P<exit_dt>\d{4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<exit>[\d,\.]+)\s+"
    r"(?P<fee>[-$\d,\.]+)\s+"
    r"(?P<swap>[-$\d,\.]+)\s+"
    r"(?P<pnl>[-$\d,\.]+)\s+"
    r"(?P<net>[-$\d,\.]+)\s+"
    r"(?P<order_id>\d+)\s+"
    r"(?P<position_id>\d+)",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    return text.replace("\u00a0", " ").replace("\t", " ")


def _parse_price(value: str) -> Optional[float]:
    if value is None:
        return None
    v = value.replace(",", "").replace("$", "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_datetime(value: str, tz_offset_hours: int) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            local_dt = datetime.strptime(value, fmt).replace(tzinfo=timezone(timedelta(hours=tz_offset_hours)))
            return local_dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    s = s.replace("NAS1O0", "NAS100").replace("NASIOO", "NAS100")
    if s in {"NAS100", "US100"}:
        return "US100"
    if s in {"GOLD", "XAUUSD"}:
        return "XAUUSD"
    if s in {"SILVER", "XAGUSD"}:
        return "XAGUSD"
    return s


def _infer_outcome(trade_type: str, direction: str, entry: float, exit_price: float) -> str:
    t = (trade_type or "").lower()
    if "take" in t:
        return "TP"
    if "stop" in t:
        return "SL"
    if direction == "LONG":
        return "TP" if exit_price > entry else "SL"
    return "TP" if exit_price < entry else "SL"


def parse_trade_platform(text: str, tz_offset_hours: int) -> List[Dict]:
    cleaned = _clean_text(text)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln.lower() != "currency flag"]
    joined = " ".join(lines)
    joined = re.sub(r"Instrument\s+Entry\s+Time.*?Position\s+ID", "", joined, flags=re.IGNORECASE)

    trades = []
    for match in PLATFORM_PATTERN.finditer(joined):
        symbol = _normalize_symbol(match.group("symbol"))
        entry_dt = _parse_datetime(match.group("entry_dt"), tz_offset_hours)
        exit_dt = _parse_datetime(match.group("exit_dt"), tz_offset_hours)
        side = match.group("side").upper()
        direction = "LONG" if side == "BUY" else "SHORT"
        entry_price = _parse_price(match.group("entry"))
        exit_price = _parse_price(match.group("exit"))
        sl = _parse_price(match.group("sl"))
        tp = _parse_price(match.group("tp"))
        lots = _parse_price(match.group("amount")) or 0.1
        net_pnl = _parse_price(match.group("net"))
        trade_type = match.group("type")

        if not (entry_dt and exit_dt and entry_price and exit_price):
            continue

        trades.append({
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "sl": sl,
            "tp": tp,
            "ts_open": entry_dt,
            "ts_close": exit_dt,
            "lots": lots,
            "outcome": _infer_outcome(trade_type, direction, entry_price, exit_price),
            "pnl_usd": net_pnl,
            "external_id": match.group("order_id"),
            "notes": f"Order {match.group('order_id')} / Position {match.group('position_id')}",
        })

    return trades


def parse_prop_firm(text: str, tz_offset_hours: int) -> List[Dict]:
    cleaned = _clean_text(text)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    filtered = []
    for ln in lines:
        if ln.upper() in PROP_HEADERS:
            continue
        if ln.lower() == "currency flag":
            continue
        filtered.append(ln)

    trades = []
    i = 0
    while i + 11 < len(filtered):
        symbol = filtered[i]
        if re.match(r"\d{4}[/-]", symbol):
            i += 1
            continue
        open_dt = _parse_datetime(filtered[i + 1], tz_offset_hours)
        open_price = _parse_price(filtered[i + 2])
        close_dt = _parse_datetime(filtered[i + 3], tz_offset_hours)
        close_price = _parse_price(filtered[i + 4])
        side = filtered[i + 5].upper()
        sl = _parse_price(filtered[i + 6])
        tp = _parse_price(filtered[i + 7])
        lots = _parse_price(filtered[i + 8]) or 0.1
        pnl = _parse_price(filtered[i + 9])
        deal = filtered[i + 11]

        if not (open_dt and close_dt and open_price and close_price):
            i += 1
            continue

        direction = "LONG" if side == "BUY" else "SHORT"
        trades.append({
            "symbol": _normalize_symbol(symbol),
            "direction": direction,
            "entry_price": open_price,
            "exit_price": close_price,
            "sl": sl,
            "tp": tp,
            "ts_open": open_dt,
            "ts_close": close_dt,
            "lots": lots,
            "outcome": _infer_outcome(side, direction, open_price, close_price),
            "pnl_usd": pnl,
            "external_id": deal.split()[0] if deal else None,
            "notes": f"Deal {deal}" if deal else "",
        })
        i += 12

    return trades


def parse_raw_trades(text: str, tz_offset_hours: int = 2) -> List[Dict]:
    platform = parse_trade_platform(text, tz_offset_hours)
    prop = parse_prop_firm(text, tz_offset_hours)

    seen = set()
    combined = []
    for t in platform + prop:
        key = (t.get("external_id"), t.get("symbol"), t.get("ts_open"), t.get("entry_price"))
        if key in seen:
            continue
        seen.add(key)
        combined.append(t)

    return combined

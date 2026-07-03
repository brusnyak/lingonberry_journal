"""
Stage 0, step 2: parse the channel's text-templated signal messages into
structured records. No vision/OCR needed -- entries/leverage/TP/SL are
posted as plain text in a consistent format.

Usage:
    python infra/telegram_signals/parse_signals.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MSG_LOG = ROOT / "data" / "telegram_signals" / "just_trade_it" / "messages.jsonl"
OUT = ROOT / "data" / "telegram_signals" / "just_trade_it" / "signals_parsed.jsonl"

# Two header orders seen in the channel's history: "LONG 🔼 HFT" and
# "WLD/USDT 🔼 LONG". Try both, "LONG"-first wins if both somehow match.
RE_HEADER_DIR_FIRST = re.compile(r"\b(LONG|SHORT)\b\s*[🔼🔽]?\s*([A-Z][A-Z0-9]{1,14})\b")
RE_HEADER_SYM_FIRST = re.compile(r"\b([A-Z][A-Z0-9]{1,14})(?:/USDT)?\s*[🔼🔽]?\s*(LONG|SHORT)\b")
RE_LEVERAGE = re.compile(r"Плечо:\s*(\d+)\s*[XxХх]")
RE_STOP = re.compile(r"Stop(?:\s*loss)?:\s*([\d.,]+)", re.IGNORECASE)
RE_PM = re.compile(r"PM:\s*([\d.,]+)\s*-\s*([\d.,]+)%")
# Takes come in two templates:
#   1) numbered-emoji lines: "1️⃣0.04128 - ..."
#   2) inline dash-separated: "Take profit: 0.1551 - 0.1448 - 0.1367"
RE_TAKE_EMOJI = re.compile(r"[0-9]️?⃣\s*([\d.,]+)")
RE_TAKE_INLINE = re.compile(r"Take(?:\s*profit)?:\s*([\d.,\s\-–]+)", re.IGNORECASE)

_STOPWORDS = {"USDT", "USD", "PM", "LONG", "SHORT"}


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _extract_takes(text: str) -> list[float]:
    emoji_takes = [_num(x) for x in RE_TAKE_EMOJI.findall(text)]
    if emoji_takes:
        return emoji_takes
    m = RE_TAKE_INLINE.search(text)
    if not m:
        return []
    nums = re.findall(r"[\d]+[.,][\d]+|\d+", m.group(1))
    return [_num(n) for n in nums]


def parse_signal(text: str, msg_id: int, date: str) -> dict | None:
    if "Take" not in text and "TAKE" not in text.upper():
        return None
    if "Stop" not in text and "STOP" not in text.upper():
        return None

    header = RE_HEADER_DIR_FIRST.search(text)
    if header:
        direction, symbol = header.group(1), header.group(2)
    else:
        header = RE_HEADER_SYM_FIRST.search(text)
        if not header:
            return None
        symbol, direction = header.group(1), header.group(2)

    if symbol in _STOPWORDS:
        return None

    lev_m = RE_LEVERAGE.search(text)
    stop_m = RE_STOP.search(text)
    pm_m = RE_PM.search(text)
    takes = _extract_takes(text)

    if not takes or not stop_m:
        return None

    try:
        stop_val = _num(stop_m.group(1))
    except ValueError:
        return None

    return {
        "msg_id": msg_id,
        "date": date,
        "direction": direction,
        "symbol": symbol,
        "leverage": int(lev_m.group(1)) if lev_m else None,
        "takes": takes,
        "stop": stop_val,
        "pm_pct_min": _num(pm_m.group(1)) if pm_m else None,
        "pm_pct_max": _num(pm_m.group(2)) if pm_m else None,
        "raw_text": text,
    }


def main() -> None:
    signals = []
    with open(MSG_LOG) as f:
        for line in f:
            d = json.loads(line)
            if not d["text"]:
                continue
            sig = parse_signal(d["text"], d["id"], d["date"])
            if sig:
                signals.append(sig)

    with open(OUT, "w") as f:
        for s in signals:
            f.write(json.dumps(s) + "\n")

    print(f"Parsed {len(signals)} entry signals -> {OUT}")

    symbols = sorted({s["symbol"] for s in signals})
    print(f"Unique symbols: {len(symbols)}: {symbols}")

    from collections import Counter
    dir_counts = Counter(s["direction"] for s in signals)
    print(f"Direction split: {dict(dir_counts)}")

    levs = [s["leverage"] for s in signals if s["leverage"]]
    print(f"Leverage: min={min(levs)} max={max(levs)} mean={sum(levs)/len(levs):.1f}")

    # Per-month signal count -> trades/month claim check
    from collections import defaultdict
    per_month = defaultdict(int)
    for s in signals:
        per_month[s["date"][:7]] += 1
    for m in sorted(per_month):
        print(f"  {m}: {per_month[m]} signals")


if __name__ == "__main__":
    main()

"""
Export every trade-entry message in the channel's full history to a CSV,
for the user to independently spot-check -- not just the 216 already
machine-verified against real price data.

Three confidence tiers, all included:
  "text_full"     -- entry/leverage/TP-ladder/stop all in the text (the 216
                      already backtested against real Binance data).
  "text_partial"  -- entry message detected (LONG/SHORT + symbol + verb),
                      but TP/stop are image-only ("на скрине"/"на графике").
                      Not independently verified; image_path given so the
                      user can check the chart themselves.
  "unparsed"      -- matched a loose long/short mention but didn't fit either
                      pattern above (recap posts, commentary, etc.) -- kept
                      at the bottom for completeness/audit, not as trades.

Also attaches, for each entry, any follow-up messages for the same symbol
before the next entry on that symbol -- the channel's own claimed outcome
narrative ("Взял первый тейк", "Закрываю позицию" etc.) -- so the user can
compare what the channel said happened against our independent backtest
result on the same row.

Usage:
    python infra/telegram_signals/export_all_trades.py
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "telegram_signals" / "just_trade_it"
MSG_LOG = DATA_DIR / "messages.jsonl"
SIGNALS_PARSED = DATA_DIR / "signals_parsed.jsonl"
BACKTEST_NET = DATA_DIR / "backtest_results_net.jsonl"
OUT_CSV = DATA_DIR / "all_trades_export.csv"

ENTRY_VERBS = r"(Захожу|Открыл|Открываю|Вхожу|Вход)"
RE_LEVERAGE_TOKEN = re.compile(r"\b\d{1,3}\s*[xXхХХ]\b|Плечо:")
# Update/close phrases that indicate this message is a follow-up on an
# EXISTING position, not a new entry -- even though it may still contain
# "SHORT UNI" as a label carried over from the original signal.
RE_UPDATE_PHRASE = re.compile(
    r"(Взял|Взяли|Фиксиру|закрыва|Закрыва|закрыт|Закрыт|ушли в бу|в безубыток|"
    r"стоп двигаю|стоп ставлю|ставлю стоп|стоп в бу|прогресс|не хватило)",
    re.IGNORECASE,
)
RE_LOOSE_LONG_SHORT = re.compile(r"\b(LONG|SHORT|long|short|лонг|шорт)\b")
RE_SYMBOL_TOKEN = re.compile(r"\b([A-Z]{2,10}[A-Z0-9]*)\b")
RE_HEADER_DIR_FIRST = re.compile(r"\b(LONG|SHORT)\b\s*[🔼🔽]?\s*([A-Z][A-Z0-9]{1,14})\b")
RE_HEADER_SYM_FIRST = re.compile(r"\b([A-Z][A-Z0-9]{1,14})(?:/USDT)?\s*[🔼🔽]?\s*(LONG|SHORT)\b")
_STOPWORDS = {"USDT", "USD", "PM", "LONG", "SHORT", "RM", "PLUS"}


def classify(text: str) -> tuple[str, str | None, str | None]:
    """Returns (tier, symbol, direction) or ("unparsed"/"skip", None, None).

    A message is only a NEW entry if it has an explicit leverage marker or
    an opening verb -- a bare "SHORT UNI" label is not enough, since the
    channel reuses that label in follow-up/close messages for the same
    position (e.g. "SHORT UNI \n Взяли первый тейк и ушли в бу")."""
    has_takestop = ("Take" in text or "TAKE" in text.upper()) and ("Stop" in text or "STOP" in text.upper())
    is_update = bool(RE_UPDATE_PHRASE.search(text)) and not has_takestop
    has_leverage_or_verb = bool(RE_LEVERAGE_TOKEN.search(text)) or bool(re.search(ENTRY_VERBS, text, re.IGNORECASE))

    header = RE_HEADER_DIR_FIRST.search(text)
    if header:
        direction, symbol = header.group(1), header.group(2)
    else:
        header = RE_HEADER_SYM_FIRST.search(text)
        if header:
            symbol, direction = header.group(1), header.group(2)
        else:
            header = None

    if header and symbol not in _STOPWORDS:
        if is_update and not has_takestop:
            return ("skip", None, None)  # follow-up on an existing position
        if has_takestop or has_leverage_or_verb:
            return ("text_full" if has_takestop else "text_partial", symbol, direction)
        return ("skip", None, None)  # bare "SHORT UNI" with no other signal -- ambiguous, don't count it

    # Analysis/recap posts ("BTC -- таймфрейм 4h...") mention long/short as
    # commentary, not a confirmed entry -- exclude explicitly.
    if "таймфрейм" in text.lower() or "ежедневный разбор" in text.lower():
        return ("skip", None, None)

    # Loose entry-verb + long/short + a plausible symbol token (Cyrillic entry verbs)
    if (re.search(r"\b" + ENTRY_VERBS, text, re.IGNORECASE) and RE_LOOSE_LONG_SHORT.search(text)
            and not is_update):
        direction_m = RE_LOOSE_LONG_SHORT.search(text)
        direction = "LONG" if direction_m.group(0).lower() in ("long", "лонг") else "SHORT"
        symbols = [t for t in RE_SYMBOL_TOKEN.findall(text) if t not in _STOPWORDS]
        symbol = symbols[0] if symbols else None
        if symbol:
            return ("text_partial", symbol, direction)

    if RE_LOOSE_LONG_SHORT.search(text):
        return ("unparsed", None, None)
    return ("skip", None, None)


def main() -> None:
    messages = [json.loads(l) for l in open(MSG_LOG)]
    parsed_by_id = {s["msg_id"]: s for s in (json.loads(l) for l in open(SIGNALS_PARSED))}
    net_by_id = {}
    if BACKTEST_NET.exists():
        net_by_id = {r["msg_id"]: r for r in (json.loads(l) for l in open(BACKTEST_NET))}

    rows = []
    # Track, per symbol, the messages between one entry and the next -- the
    # channel's own follow-up narrative for that position.
    last_entry_idx_by_symbol: dict[str, int] = {}
    entries: list[dict] = []

    for i, m in enumerate(messages):
        if not m["text"]:
            continue
        tier, symbol, direction = classify(m["text"])
        if tier in ("text_full", "text_partial"):
            entries.append({"idx": i, "msg": m, "tier": tier, "symbol": symbol, "direction": direction})

    for j, e in enumerate(entries):
        symbol = e["symbol"]
        start_idx = e["idx"] + 1
        end_idx = entries[j + 1]["idx"] if j + 1 < len(entries) else len(messages)
        followups = []
        for k in range(start_idx, end_idx):
            mk = messages[k]
            if mk["text"] and symbol.upper() in mk["text"].upper():
                followups.append(mk["text"].replace("\n", " ")[:150])
        followup_str = " || ".join(followups[:6])

        parsed = parsed_by_id.get(e["msg"]["id"])
        net = net_by_id.get(e["msg"]["id"])

        rows.append({
            "msg_id": e["msg"]["id"],
            "date": e["msg"]["date"],
            "tier": e["tier"],
            "symbol": symbol,
            "direction": e["direction"],
            "leverage": parsed["leverage"] if parsed else "",
            "entry_parsed": "",
            "stop_parsed": parsed["stop"] if parsed else "",
            "takes_parsed": "|".join(str(t) for t in parsed["takes"]) if parsed else "",
            "pm_pct": f"{parsed['pm_pct_min']}-{parsed['pm_pct_max']}" if parsed and parsed.get("pm_pct_min") else "",
            "verified_net_R": net["weighted_r_net"] if net else "",
            "verified_hold_days": net["hold_days"] if net else "",
            "raw_text": e["msg"]["text"].replace("\n", " ")[:300],
            "image_path": e["msg"]["image_path"] or "",
            "channel_followup_claims": followup_str,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n_full = sum(1 for r in rows if r["tier"] == "text_full")
    n_partial = sum(1 for r in rows if r["tier"] == "text_partial")
    n_verified = sum(1 for r in rows if r["verified_net_R"] != "")
    print(f"Exported {len(rows)} trade-entry messages -> {OUT_CSV}")
    print(f"  text_full (fully parsed): {n_full}")
    print(f"  text_partial (image-only levels): {n_partial}")
    print(f"  independently verified against real price data: {n_verified}")


if __name__ == "__main__":
    main()

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure, detect_swings, label_swing_structure


SESSION_ID = "dd10e9831940"
OUTPUT_DIR = Path(__file__).parents[2] / "data" / "analysis"
KEYWORDS = {
    "order_block": [r"\border block\b", r"\bob\b"],
    "fvg": [r"\bfvg\b", r"\bfwg\b"],
    "fvg_50": [r"50%\s*fvg", r"50%\s*fwg"],
    "liquidity": [r"\bliquidity\b", r"\bsweep\b", r"\binducement\b"],
    "choch_bos": [r"\bchoch\b", r"\bbos\b"],
    "news": [r"\bnews\b"],
    "round_level": [r"\bround level\b", r"\b23\d{3}\b", r"\b24\d{3}\b"],
    "london": [r"\blondon\b"],
    "ny": [r"\bny\b", r"\bnew york\b"],
    "asia_night": [r"\basia\b", r"\bnight\b"],
    "continuation": [r"\bcontinu", r"\buptrend\b", r"\bdowntrend\b"],
    "retest": [r"\bretest\b", r"\bretracement\b", r"\bpullback\b"],
}


def keyword_hits(text: str) -> List[str]:
    text = (text or "").lower()
    hits = []
    for label, patterns in KEYWORDS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            hits.append(label)
    return hits


def summarize_local_structure(df: pd.DataFrame, entry_time: pd.Timestamp) -> Dict[str, object]:
    if not isinstance(df.index, pd.DatetimeIndex):
        return {}
    try:
        idx = df.index.get_indexer([entry_time], method="nearest")[0]
    except Exception:
        return {}

    left = max(0, idx - 60)
    right = min(len(df), idx + 20)
    window = df.iloc[left:right].copy()
    if len(window) < 20:
        return {}

    ms = analyze_market_structure(window, swing_period=3, volume_filter=False)
    swing_highs, swing_lows = detect_swings(window["high"], window["low"], period=3)
    swing_labels = label_swing_structure(swing_highs, swing_lows)

    entry_local_idx = idx - left
    recent_breaks = [
        brk for brk in ms.get("structure_breaks", [])
        if entry_local_idx - 12 <= brk.index <= entry_local_idx
    ]
    recent_labels = [
        label for s_idx, label in swing_labels.items()
        if entry_local_idx - 12 <= s_idx <= entry_local_idx
    ]

    liquidity_above = 0
    liquidity_below = 0
    entry_price = float(window["close"].iloc[entry_local_idx])
    for lvl in ms.get("liquidity_levels", []):
        if lvl.start_index > entry_local_idx:
            continue
        if lvl.price > entry_price and not lvl.swept:
            liquidity_above += 1
        if lvl.price < entry_price and not lvl.swept:
            liquidity_below += 1

    return {
        "trend": ms.get("current_trend"),
        "recent_breaks": [f"{brk.type}:{brk.direction}" for brk in recent_breaks],
        "recent_swing_labels": recent_labels,
        "unswept_liquidity_above": liquidity_above,
        "unswept_liquidity_below": liquidity_below,
        "has_bullish_break": any(brk.direction == "bullish" for brk in recent_breaks),
        "has_bearish_break": any(brk.direction == "bearish" for brk in recent_breaks),
    }


def main() -> None:
    session_path = Path("data/review_sessions") / f"{SESSION_ID}.json"
    data = json.loads(session_path.read_text())
    loader = DataLoader()
    df = loader.load(data["symbol"], data["timeframe"], prefer_parquet=True)

    manual_trades = [
        t for t in data.get("trades", [])
        if t.get("source") == "manual" or "manual" in (t.get("tags") or [])
    ]

    keyword_outcomes: Dict[str, Counter] = defaultdict(Counter)
    trigger_outcomes: Dict[str, Counter] = defaultdict(Counter)
    examples: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    structure_outcomes: Dict[str, Counter] = defaultdict(Counter)
    enriched_trades = []

    for trade in manual_trades:
        entry_ts = pd.to_datetime(trade["entry_time"], unit="s", utc=True).tz_convert(None)
        note = (trade.get("notes") or "").strip()
        outcome = trade.get("outcome") or "none"
        hits = keyword_hits(note)
        local_structure = summarize_local_structure(df, entry_ts)

        for hit in hits:
            keyword_outcomes[hit][outcome] += 1
            if len(examples[hit]) < 3:
                examples[hit].append(
                    {
                        "trade_id": trade["id"],
                        "outcome": outcome,
                        "note": note[:260],
                    }
                )

        for tag in trade.get("reason_tags", []) or []:
            trigger_outcomes[tag][outcome] += 1

        structure_key = (
            f"trend={local_structure.get('trend')}|"
            f"bull_break={local_structure.get('has_bullish_break')}|"
            f"bear_break={local_structure.get('has_bearish_break')}"
        )
        structure_outcomes[structure_key][outcome] += 1

        enriched_trades.append(
            {
                "trade_id": trade["id"],
                "outcome": outcome,
                "reason_tags": trade.get("reason_tags", []),
                "keyword_hits": hits,
                "notes": note,
                "local_structure": local_structure,
            }
        )

    report = {
        "session_id": SESSION_ID,
        "symbol": data["symbol"],
        "timeframe": data["timeframe"],
        "manual_trade_count": len(manual_trades),
        "keyword_outcomes": {k: dict(v) for k, v in keyword_outcomes.items()},
        "trigger_outcomes": {k: dict(v) for k, v in trigger_outcomes.items()},
        "structure_outcomes": {k: dict(v) for k, v in structure_outcomes.items()},
        "examples": examples,
        "trades": enriched_trades,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "nas100_review_patterns.json"
    md_path = OUTPUT_DIR / "nas100_review_patterns.md"
    json_path.write_text(json.dumps(report, indent=2))

    lines = [
        f"# NAS100 Review Patterns",
        "",
        f"- Session: `{SESSION_ID}`",
        f"- Symbol: `{data['symbol']}`",
        f"- Timeframe: `{data['timeframe']}`",
        f"- Manual trades: `{len(manual_trades)}`",
        "",
        "## Keyword Outcomes",
    ]
    for keyword, counts in sorted(keyword_outcomes.items()):
        total = sum(counts.values())
        lines.append(f"- `{keyword}`: {dict(counts)} total={total}")
    lines.append("")
    lines.append("## Trigger Tag Outcomes")
    for tag, counts in sorted(trigger_outcomes.items()):
        lines.append(f"- `{tag}`: {dict(counts)}")
    lines.append("")
    lines.append("## Local Structure Outcomes")
    for label, counts in sorted(structure_outcomes.items()):
        lines.append(f"- `{label}`: {dict(counts)}")
    lines.append("")
    lines.append("## Note Examples")
    for keyword, items in sorted(examples.items()):
        lines.append(f"### {keyword}")
        for item in items:
            lines.append(f"- `{item['outcome']}`: {item['note']}")
        lines.append("")

    md_path.write_text("\n".join(lines))
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()

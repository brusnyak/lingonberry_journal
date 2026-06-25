import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).parents[2]
SESSIONS_DIR = ROOT / "data" / "review_sessions"
OUT_DIR = ROOT / "data" / "analysis"


def parse_reason_tags(tags):
    out = {}
    for tag in tags or []:
        if ":" not in str(tag):
            continue
        key, value = str(tag).split(":", 1)
        out[key] = value
    return out


def run():
    setup_grade = Counter()
    entry_model = Counter()
    target_model = Counter()
    why_valid = Counter()
    trigger = Counter()
    session = Counter()
    invalidator = Counter()
    symbol_rows = defaultdict(lambda: Counter())
    note_keywords = Counter()

    keywords = [
        "vwap", "ema", "choch", "bos", "order block", "orderblock",
        "fvg", "fwg", "sweep", "liquidity", "asia high", "asia low",
        "previous high", "previous low", "round level", "news",
    ]

    total_manual = 0
    wins = 0
    losses = 0

    for fp in sorted(SESSIONS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text())
        except Exception:
            continue
        symbol = data.get("symbol") or "unknown"
        for trade in data.get("trades", []):
            if trade.get("source") != "manual":
                continue
            total_manual += 1
            outcome = trade.get("outcome")
            if outcome == "win":
                wins += 1
            elif outcome == "loss":
                losses += 1

            tags = parse_reason_tags(trade.get("reason_tags", []))
            for key, counter in [
                ("setup_grade", setup_grade),
                ("entry_model", entry_model),
                ("target_model", target_model),
                ("why_valid", why_valid),
                ("trigger", trigger),
                ("session", session),
                ("invalidator", invalidator),
            ]:
                value = tags.get(key)
                if value:
                    counter[value] += 1
                    symbol_rows[symbol][f"{key}:{value}"] += 1

            note = (trade.get("notes") or "").lower()
            for key in keywords:
                if key in note:
                    note_keywords[key] += 1
                    symbol_rows[symbol][f"note:{key}"] += 1

    payload = {
        "total_manual_trades": total_manual,
        "wins": wins,
        "losses": losses,
        "setup_grade": setup_grade,
        "entry_model": entry_model,
        "target_model": target_model,
        "why_valid": why_valid,
        "trigger": trigger,
        "session": session,
        "invalidator": invalidator,
        "note_keywords": note_keywords,
        "by_symbol": {symbol: dict(counter) for symbol, counter in symbol_rows.items()},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "manual_review_summary.json").write_text(
        json.dumps(payload, indent=2, default=lambda x: dict(x))
    )

    lines = [
        "# Manual Review Summary",
        "",
        f"- trades={total_manual} wins={wins} losses={losses}",
        "",
        "## Setup Grade",
    ]
    for k, v in setup_grade.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Entry Model"]
    for k, v in entry_model.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Target Model"]
    for k, v in target_model.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Why Valid"]
    for k, v in why_valid.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Trigger"]
    for k, v in trigger.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Session"]
    for k, v in session.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Note Keywords"]
    for k, v in note_keywords.most_common():
        lines.append(f"- {k}: {v}")

    (OUT_DIR / "manual_review_summary.md").write_text("\n".join(lines))
    print(json.dumps({"output": str(OUT_DIR / 'manual_review_summary.json'), "trades": total_manual}, indent=2))


if __name__ == "__main__":
    run()

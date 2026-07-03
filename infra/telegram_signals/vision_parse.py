"""
Stage 1 pilot: extract trade parameters (entry, stop, TP ladder) from a
chart screenshot using a free OpenRouter vision model.

This is the piece PLAN.md previously rejected as unreliable for live
execution ("Telegram scraper -- visual content not reliably extractable").
It's back in scope only because the user explicitly wants to test it, and
only ever as a PROPOSAL a human confirms -- never as a silent auto-executor.
Every extraction should be checked against a human-read ground truth before
it's trusted, which is exactly what this pilot does for the two seed images.

Usage:
    python infra/telegram_signals/vision_parse.py <image_path> "<caption text>"
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
VISION_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

PROMPT = """You are reading a TradingView chart screenshot of a crypto futures \
trade plan. It has colored zones and price labels marking an entry, a stop \
loss, and one or more take-profit levels.

Caption text posted alongside the chart: "{caption}"

Return ONLY a JSON object, no prose, with this exact shape:
{{
  "symbol": "<ticker, e.g. WLD or VELVET>",
  "direction": "LONG" or "SHORT",
  "entry": <number>,
  "stop": <number>,
  "takes": [<number>, <number>, ...]  // ordered nearest-to-entry first
}}

Rules:
- For a SHORT: stop is ABOVE entry, takes are BELOW entry, in increasing distance.
- For a LONG: stop is BELOW entry, takes are ABOVE entry, in increasing distance.
- Read the price labels on the right axis / colored zone boundaries exactly as shown.
- If a value is ambiguous, use your best reading -- do not omit fields.
"""


def parse_chart(image_path: str, caption: str) -> dict:
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT.format(caption=caption)},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in model response: {content!r}")
    return json.loads(match.group(0))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vision_parse.py <image_path> [caption]")
        sys.exit(1)
    path = sys.argv[1]
    cap = sys.argv[2] if len(sys.argv) > 2 else ""
    result = parse_chart(path, cap)
    print(json.dumps(result, indent=2))

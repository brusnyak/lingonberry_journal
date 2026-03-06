#!/bin/bash
# Test the manual trade API endpoint

echo "Testing /api/trades/manual endpoint..."
echo ""

# Test payload similar to what the frontend sends
curl -X POST http://localhost:5000/api/trades/manual?account_id=3 \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "entry_price": 1.08500,
    "exit_price": 1.08700,
    "sl": 1.08300,
    "tp": 1.08700,
    "ts_open": 1709740800,
    "ts_close": 1709744400,
    "lots": 0.1,
    "notes": "Test trade from API",
    "mindset": "Calm and focused",
    "setup": "Breakout",
    "risk": 1.0,
    "drawings": [
      {
        "type": "trendline",
        "points": [
          {"time": 1709740800, "price": 1.08500},
          {"time": 1709744400, "price": 1.08600}
        ],
        "style": {"color": "#00ff00", "width": 2}
      }
    ]
  }' | python -m json.tool

echo ""
echo "Test completed!"

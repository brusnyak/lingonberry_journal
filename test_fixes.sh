#!/bin/bash
# Test script for UI fixes

echo "🧪 Testing Trading Journal UI Fixes"
echo "===================================="
echo ""

# Check if Flask is running
echo "1. Checking if Flask webapp is running..."
if curl -s http://localhost:5000/api/dashboard > /dev/null 2>&1; then
    echo "   ✅ Flask is running"
else
    echo "   ❌ Flask is NOT running"
    echo "   Please start it with: make webapp"
    exit 1
fi

echo ""
echo "2. Testing Monte Carlo endpoint..."
MONTE_CARLO=$(curl -s http://localhost:5000/api/analytics/monte-carlo)
if echo "$MONTE_CARLO" | grep -q "simulations"; then
    echo "   ✅ Monte Carlo endpoint returns data"
    echo "   Response preview:"
    echo "$MONTE_CARLO" | python3 -m json.tool | head -20
else
    echo "   ⚠️  Monte Carlo endpoint may have issues"
    echo "   Response: $MONTE_CARLO"
fi

echo ""
echo "3. Testing dashboard endpoint..."
DASHBOARD=$(curl -s http://localhost:5000/api/dashboard)
if echo "$DASHBOARD" | grep -q "stats"; then
    echo "   ✅ Dashboard endpoint returns data"
    TRADE_COUNT=$(echo "$DASHBOARD" | python3 -c "import sys, json; print(json.load(sys.stdin)['stats']['total_trades'])")
    echo "   Total trades: $TRADE_COUNT"
else
    echo "   ❌ Dashboard endpoint has issues"
fi

echo ""
echo "4. Testing trades endpoint..."
TRADES=$(curl -s http://localhost:5000/api/trades)
if echo "$TRADES" | python3 -c "import sys, json; trades = json.load(sys.stdin); print(f'{len(trades)} trades')" 2>/dev/null; then
    echo "   ✅ Trades endpoint returns data"
else
    echo "   ❌ Trades endpoint has issues"
fi

echo ""
echo "5. Checking static files..."
for file in webapp/static/js/trade-modal.js webapp/static/js/filters.js; do
    if [ -f "$file" ]; then
        echo "   ✅ $file exists"
    else
        echo "   ❌ $file missing"
    fi
done

echo ""
echo "===================================="
echo "✨ Test complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:5000/mini in your browser"
echo "2. Click on a trade to test the modal"
echo "3. Open http://localhost:5000/analytics to test analytics"
echo "4. Try the date filters"
echo ""

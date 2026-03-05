#!/bin/bash
# Quick start script for local development

echo "🍒 Lingonberry Journal - Local Development"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv/bin/activate

# Check if database exists
if [ ! -f "data/journal.db" ]; then
    echo "⚠️  Database not found. Initializing..."
    python -c "from bot import journal_db; journal_db.init_db()"
fi

# Run tests
echo ""
echo "🧪 Running tests..."
python test_webapp.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed! Please fix the issues above."
    exit 1
fi

echo ""
echo "✅ All tests passed!"
echo ""
echo "🚀 Starting webapp..."
echo "   Open: http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

# Start webapp
python webapp/app.py

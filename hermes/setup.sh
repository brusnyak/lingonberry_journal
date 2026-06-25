#!/bin/bash
# Hermes Agent Setup Script for Trading
# Run this on Oracle server or locally

set -e

echo "=== Hermes Trading Agent Setup ==="
echo ""

# Check if Hermes is installed
if ! command -v hermes &> /dev/null; then
    echo "Installing Hermes Agent..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null
fi

echo "Hermes version:"
hermes --version
echo ""

# Setup OpenRouter
echo "Setting up OpenRouter..."
hermes setup --openrouter
echo ""

# Setup Telegram
echo "Setting up Telegram..."
hermes setup --telegram
echo ""

# Create trading skills directory
SKILLS_DIR="$HOME/.hermes/skills/trading"
mkdir -p "$SKILLS_DIR"

# Copy skills
echo "Copying trading skills..."
cp "$(dirname "$0")/skills/market_analysis.py" "$SKILLS_DIR/"
cp "$(dirname "$0")/skills/paper_trade.py" "$SKILLS_DIR/"
cp "$(dirname "$0")/skills/trade_review.py" "$SKILLS_DIR/"
cp "$(dirname "$0")/skills/daily_briefing.py" "$SKILLS_DIR/"

echo ""
echo "Setting up cron jobs..."

# Morning briefing (07:00 UTC, 1 hour before London)
hermes cron create "0 7 * * 1-5" --prompt "Run morning briefing: python $SKILLS_DIR/daily_briefing.py morning" --name "morning-briefing"

# EOD summary (21:00 UTC, after NY close)
hermes cron create "0 21 * * 1-5" --prompt "Run EOD summary: python $SKILLS_DIR/daily_briefing.py eod" --name "eod-summary"

# Trade monitoring (every 15 min during London/NY)
hermes cron create "*/15 7-16 * * 1-5" --prompt "Check for new paper trades and review: python $SKILLS_DIR/trade_review.py review 5" --name "trade-monitor"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Cron jobs created:"
echo "  - morning-briefing: 07:00 UTC Mon-Fri"
echo "  - eod-summary: 21:00 UTC Mon-Fri"
echo "  - trade-monitor: Every 15 min during London/NY"
echo ""
echo "To start Hermes:"
echo "  hermes"
echo ""
echo "To test skills locally:"
echo "  python $SKILLS_DIR/market_analysis.py"
echo "  python $SKILLS_DIR/paper_trade.py status"
echo "  python $SKILLS_DIR/daily_briefing.py morning"

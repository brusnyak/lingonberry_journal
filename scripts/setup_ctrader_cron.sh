#!/bin/bash
# Setup monthly cTrader token refresh cron job
# Runs on the 1st of every month at midnight

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_DIR/.venv"
PYTHON_PATH="$VENV_PATH/bin/python"
REFRESH_SCRIPT="$PROJECT_DIR/scripts/automate_ctrader_token.py"

echo "🔧 Setting up cTrader token refresh cron job..."

# Check if script exists
if [ ! -f "$REFRESH_SCRIPT" ]; then
    echo "❌ Refresh script not found at $REFRESH_SCRIPT"
    exit 1
fi

# Create cron job entry
# Runs at 00:00 on day-of-month 1
CRON_JOB="0 0 1 * * cd $PROJECT_DIR && $PYTHON_PATH $REFRESH_SCRIPT >> $PROJECT_DIR/data/logs/ctrader_refresh.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "automate_ctrader_token.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "automate_ctrader_token.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ cTrader token refresh cron job installed!"
echo ""
echo "📅 Schedule: 1st day of every month at midnight"
echo "📝 Log file: $PROJECT_DIR/data/logs/ctrader_refresh.log"
echo ""
echo "Note: The script updates your .env file automatically."

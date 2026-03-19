#!/bin/bash
# Setup proactive alerts cron job
# Runs every 15 minutes to check for daily loss and inactivity

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_DIR/.venv"
PYTHON_PATH="$VENV_PATH/bin/python"
ALERTS_SCRIPT="$PROJECT_DIR/jobs/proactive_alerts.py"

echo "🔧 Setting up proactive alerts cron job..."

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Run 'make venv install' first"
    exit 1
fi

# Check if alerts script exists
if [ ! -f "$ALERTS_SCRIPT" ]; then
    echo "❌ Alerts script not found at $ALERTS_SCRIPT"
    exit 1
fi

# Create cron job entry
# Format: minute hour day month day-of-week command
# */15 * * * * = Every 15 minutes
CRON_JOB="*/15 * * * * cd $PROJECT_DIR && $PYTHON_PATH $ALERTS_SCRIPT >> $PROJECT_DIR/data/logs/proactive_alerts.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "proactive_alerts.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "proactive_alerts.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Proactive alerts cron job installed!"
echo ""
echo "📅 Schedule: Every 15 minutes"
echo "📝 Log file: $PROJECT_DIR/data/logs/proactive_alerts.log"
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"

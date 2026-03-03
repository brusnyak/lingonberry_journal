#!/bin/bash
# Setup daily trading reminder cron job
# Runs Mon-Fri at 7pm UTC (19:00)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_DIR/.venv"
PYTHON_PATH="$VENV_PATH/bin/python"
REMINDER_SCRIPT="$PROJECT_DIR/jobs/daily_reminder.py"

echo "🔧 Setting up daily trading reminder cron job..."

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Run 'make venv install' first"
    exit 1
fi

# Check if reminder script exists
if [ ! -f "$REMINDER_SCRIPT" ]; then
    echo "❌ Reminder script not found at $REMINDER_SCRIPT"
    exit 1
fi

# Create cron job entry
# Format: minute hour day month day-of-week command
# 0 19 * * 1-5 = 7pm UTC, Monday to Friday
CRON_JOB="0 19 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH $REMINDER_SCRIPT >> $PROJECT_DIR/data/logs/daily_reminder.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_reminder.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "daily_reminder.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Daily reminder cron job installed!"
echo ""
echo "📅 Schedule: Monday-Friday at 7:00 PM UTC"
echo "📝 Log file: $PROJECT_DIR/data/logs/daily_reminder.log"
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove this cron job:"
echo "  crontab -l | grep -v 'daily_reminder.py' | crontab -"
echo ""
echo "To test the reminder manually:"
echo "  make daily-reminder"

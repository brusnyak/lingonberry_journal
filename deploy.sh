#!/bin/bash
# Quick deployment script for Oracle Cloud

set -e

echo "🚀 Deploying Lingonberry Journal..."

# Pull latest code
git pull origin main

# Activate venv
source .venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Restart services
sudo systemctl restart journal-bot journal-webapp

echo "✅ Deployment complete!"
echo "📊 Check status:"
echo "   sudo systemctl status journal-bot"
echo "   sudo systemctl status journal-webapp"

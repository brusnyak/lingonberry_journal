#!/bin/bash
# Helper script to deploy .env file and restart services

ORACLE_IP="${ORACLE_VM_IP:-84.8.249.139}"
ORACLE_USER="ubuntu"

echo "🔐 Deploying .env file to Oracle Cloud..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "   Create it first: cp .env.example .env"
    exit 1
fi

# Copy .env
echo "📤 Copying .env file..."
scp .env $ORACLE_USER@$ORACLE_IP:lingonberry_journal/

# Restart services
echo "🔄 Restarting services..."
ssh $ORACLE_USER@$ORACLE_IP << 'ENDSSH'
cd lingonberry_journal
sudo systemctl restart journal-bot journal-webapp
echo "✅ Services restarted"
echo ""
echo "📊 Service Status:"
sudo systemctl status journal-bot --no-pager -l | head -3
sudo systemctl status journal-webapp --no-pager -l | head -3
ENDSSH

echo ""
echo "✅ Done! Your app is now using the updated configuration."
echo "   Access it at: http://$ORACLE_IP/mini"

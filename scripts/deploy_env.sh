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

# SSH Key
SSH_KEY="ssh-key-2026-02-21.key"
if [ ! -f "$SSH_KEY" ]; then
    echo "⚠️  SSH Key ($SSH_KEY) not found in root. Trying to proceed without identity file..."
    SSH_OPT=""
else
    chmod 600 "$SSH_KEY"
    SSH_OPT="-i $SSH_KEY"
fi

# Copy .env
echo "📤 Copying .env file..."
scp $SSH_OPT .env $ORACLE_USER@$ORACLE_IP:lingonberry_journal/

# Restart services
echo "🔄 Restarting services..."
ssh $SSH_OPT $ORACLE_USER@$ORACLE_IP << 'ENDSSH'
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

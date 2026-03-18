#!/bin/bash
# Deployment script for Lingonberry Trading Journal
# Usage: ./deploy.sh

set -euo pipefail

echo "🚀 Deploying Lingonberry Trading Journal to Oracle Cloud"
echo "=========================================================="

ORACLE_IP="${ORACLE_VM_IP:-84.8.249.139}"
ORACLE_USER="${ORACLE_USER:-ubuntu}"
SSH_KEY_PATH="${SSH_KEY_PATH:-./ssh-key-2026-02-21.key}"
REPO_URL="${GITHUB_JOURNAL_REPO:-https://github.com/brusnyak/lingonberry_journal.git}"
APP_DIR="${APP_DIR:-lingonberry_journal}"
SSH_OPTS=(-i "$SSH_KEY_PATH" -o BatchMode=yes -o ConnectTimeout=10)

echo
echo "📋 Configuration:"
echo "   Oracle IP: $ORACLE_IP"
echo "   User: $ORACLE_USER"
echo "   Repository: $REPO_URL"
echo "   SSH Key: $SSH_KEY_PATH"
echo

echo "🔌 Testing SSH connection..."
ssh "${SSH_OPTS[@]}" "$ORACLE_USER@$ORACLE_IP" exit
echo "✅ SSH connection successful"

echo
echo "📦 Deploying application..."

ssh "${SSH_OPTS[@]}" "$ORACLE_USER@$ORACLE_IP" "bash -s" <<'ENDSSH'
set -euo pipefail

APP_DIR="$HOME/lingonberry_journal"
BACKUP_ROOT="$HOME/lingonberry_deploy_backups"
mkdir -p "$BACKUP_ROOT"

echo "📥 Updating system packages..."
sudo apt update -qq

echo "📦 Installing dependencies..."
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx > /dev/null 2>&1

echo "📂 Setting up application directory..."
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git fetch origin
else
    git clone https://github.com/brusnyak/lingonberry_journal.git "$APP_DIR"
    cd "$APP_DIR"
fi

echo "🧹 Preparing runtime backup..."
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR"
if [ -f data/.ctrader_sync_state.txt ]; then
    cp data/.ctrader_sync_state.txt "$BACKUP_DIR"/
fi

echo "📥 Updating repository..."
git stash push --include-untracked -m "codex-deploy-$STAMP" || true
git pull --ff-only origin main

echo "🐍 Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "💾 Initializing database..."
python3 -c "from bot import journal_db; journal_db.init_db()"

if [ -f "$BACKUP_DIR/.ctrader_sync_state.txt" ]; then
    cp "$BACKUP_DIR/.ctrader_sync_state.txt" data/.ctrader_sync_state.txt
fi

restart_with_manage() {
    echo "🔄 Restarting app via scripts/manage.sh..."
    bash scripts/manage.sh restart all
    sleep 2
    bash scripts/manage.sh status
}

restart_with_systemd() {
    echo "🔄 Restarting app via systemd..."
    sudo systemctl daemon-reload
    sudo systemctl enable journal-bot journal-webapp journal-ctrader-refresh.timer nginx >/dev/null 2>&1 || true
    sudo nginx -t
    sudo systemctl restart nginx journal-bot journal-webapp journal-ctrader-refresh.timer
    sudo systemctl --no-pager --full status journal-bot journal-webapp nginx | head -20
}

if [ -f scripts/manage.sh ]; then
    restart_with_manage
elif systemctl list-unit-files | grep -q '^journal-webapp.service'; then
    restart_with_systemd
else
    echo "⚠️ No known service manager found; app files updated but processes were not restarted."
fi

echo "---"
echo "HEAD $(git rev-parse --short HEAD)"
echo "Stashes:"
git stash list | head -3 || true
ENDSSH

echo
echo "=========================================================="
echo "✅ Deployment completed"
echo
echo "Primary URL:"
echo "   https://lingonberry.work.gd/mini"
echo
echo "If needed, verify remotely:"
echo "   ssh -i $SSH_KEY_PATH $ORACLE_USER@$ORACLE_IP"
echo "   cd $APP_DIR && bash scripts/manage.sh status"
echo
echo "=========================================================="

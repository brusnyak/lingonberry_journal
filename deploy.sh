#!/bin/bash
# Deployment script for Lingonberry Trading Journal
# Usage: ./deploy.sh

set -e  # Exit on error

echo "🚀 Deploying Lingonberry Trading Journal to Oracle Cloud"
echo "=========================================================="

# Configuration
ORACLE_IP="${ORACLE_VM_IP:-84.8.249.139}"
ORACLE_USER="ubuntu"
REPO_URL="${GITHUB_JOURNAL_REPO:-https://github.com/brusnyak/lingonberry_journal.git}"
APP_DIR="lingonberry_journal"

echo ""
echo "📋 Configuration:"
echo "   Oracle IP: $ORACLE_IP"
echo "   User: $ORACLE_USER"
echo "   Repository: $REPO_URL"
echo ""

# Check if we can connect
echo "🔌 Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $ORACLE_USER@$ORACLE_IP exit 2>/dev/null; then
    echo "❌ Cannot connect to $ORACLE_IP"
    echo "   Make sure:"
    echo "   1. SSH key is added: ssh-copy-id $ORACLE_USER@$ORACLE_IP"
    echo "   2. Server is running"
    echo "   3. IP address is correct"
    exit 1
fi
echo "✅ SSH connection successful"

# Deploy
echo ""
echo "📦 Deploying application..."

ssh $ORACLE_USER@$ORACLE_IP << 'ENDSSH'
set -e

echo "📥 Updating system packages..."
sudo apt update -qq

echo "📦 Installing dependencies..."
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx > /dev/null 2>&1

echo "📂 Setting up application directory..."
if [ -d "lingonberry_journal" ]; then
    echo "   Updating existing installation..."
    cd lingonberry_journal
    git pull
else
    echo "   Fresh installation..."
    git clone https://github.com/brusnyak/lingonberry_journal.git
    cd lingonberry_journal
fi

echo "🐍 Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "💾 Initializing database..."
python3 -c "from bot import journal_db; journal_db.init_db()" 2>/dev/null || echo "   Database already initialized"

echo "⚙️  Setting up systemd services..."

# Bot service
sudo tee /etc/systemd/system/journal-bot.service > /dev/null << 'EOF'
[Unit]
Description=Trading Journal Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/lingonberry_journal
Environment="PATH=/home/ubuntu/lingonberry_journal/.venv/bin"
ExecStart=/home/ubuntu/lingonberry_journal/.venv/bin/python3 bot/journal_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Webapp service
sudo tee /etc/systemd/system/journal-webapp.service > /dev/null << 'EOF'
[Unit]
Description=Trading Journal Web Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/lingonberry_journal
Environment="PATH=/home/ubuntu/lingonberry_journal/.venv/bin"
ExecStart=/home/ubuntu/lingonberry_journal/.venv/bin/python3 webapp/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Nginx config
sudo tee /etc/nginx/sites-available/journal > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# Enable nginx site
if [ ! -L "/etc/nginx/sites-enabled/journal" ]; then
    sudo ln -s /etc/nginx/sites-available/journal /etc/nginx/sites-enabled/
fi

# Remove default nginx site
sudo rm -f /etc/nginx/sites-enabled/default

echo "🔥 Configuring firewall..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

echo "🔄 Reloading services..."
sudo systemctl daemon-reload
sudo systemctl enable journal-bot journal-webapp nginx
sudo nginx -t && sudo systemctl restart nginx
sudo systemctl restart journal-bot journal-webapp

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Service Status:"
sudo systemctl status journal-bot --no-pager -l | head -3
sudo systemctl status journal-webapp --no-pager -l | head -3
sudo systemctl status nginx --no-pager -l | head -3

ENDSSH

echo ""
echo "=========================================================="
echo "✅ Deployment successful!"
echo ""
echo "📝 Next steps:"
echo "   1. Copy your .env file to the server:"
echo "      scp .env $ORACLE_USER@$ORACLE_IP:$APP_DIR/"
echo ""
echo "   2. Restart services:"
echo "      ssh $ORACLE_USER@$ORACLE_IP 'sudo systemctl restart journal-bot journal-webapp'"
echo ""
echo "   3. Check logs:"
echo "      ssh $ORACLE_USER@$ORACLE_IP 'sudo journalctl -u journal-bot -f'"
echo "      ssh $ORACLE_USER@$ORACLE_IP 'sudo journalctl -u journal-webapp -f'"
echo ""
echo "   4. Access your app:"
echo "      http://$ORACLE_IP/mini"
echo ""
echo "   5. (Optional) Setup SSL with domain:"
echo "      ssh $ORACLE_USER@$ORACLE_IP"
echo "      sudo certbot --nginx -d your-domain.com"
echo ""
echo "=========================================================="

# Quick Deploy to Oracle + lingonberry.work.gd

## 1. Oracle Server Setup (First Time Only)

```bash
# SSH to Oracle
ssh ubuntu@YOUR_ORACLE_IP

# Clone repo
git clone https://github.com/brusnyak/lingonberry_journal.git
cd lingonberry_journal

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Add your tokens

# Init DB
python3 -c "from bot import journal_db; journal_db.init_db()"
```

## 2. Create Services

```bash
# Bot service
sudo tee /etc/systemd/system/journal-bot.service > /dev/null <<EOF
[Unit]
Description=Trading Journal Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/lingonberry_journal
Environment="PATH=/home/ubuntu/lingonberry_journal/.venv/bin"
ExecStart=/home/ubuntu/lingonberry_journal/.venv/bin/python3 bot/journal_daemon.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Webapp service
sudo tee /etc/systemd/system/journal-webapp.service > /dev/null <<EOF
[Unit]
Description=Trading Journal Webapp
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/lingonberry_journal
Environment="PATH=/home/ubuntu/lingonberry_journal/.venv/bin"
ExecStart=/home/ubuntu/lingonberry_journal/.venv/bin/python3 webapp/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable journal-bot journal-webapp
sudo systemctl start journal-bot journal-webapp
```

## 3. Setup Nginx

```bash
sudo apt install -y nginx

sudo tee /etc/nginx/sites-available/journal > /dev/null <<'EOF'
server {
    listen 80;
    server_name lingonberry.work.gd;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/journal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 4. Configure lingonberry.work.gd Domain

Go to DNSExit control panel:
1. Add A record: `@` → `YOUR_ORACLE_IP`
2. Add A record: `www` → `YOUR_ORACLE_IP`
3. Wait 5-10 minutes for DNS propagation

Test: `curl http://lingonberry.work.gd/mini`

## 5. Setup SSL (Optional but Recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d lingonberry.work.gd -d www.lingonberry.work.gd
```

## 6. Update Telegram Bot

In `.env` on server:
```
WEBAPP_URL=https://lingonberry.work.gd/mini
```

Restart bot:
```bash
sudo systemctl restart journal-bot
```

## Future Updates

Just run on Oracle server:
```bash
cd ~/lingonberry_journal
./deploy.sh
```

## Check Status

```bash
# Services
sudo systemctl status journal-bot journal-webapp

# Logs
sudo journalctl -u journal-bot -f
sudo journalctl -u journal-webapp -f

# Test
curl http://localhost:5000/mini
curl http://lingonberry.work.gd/mini
```

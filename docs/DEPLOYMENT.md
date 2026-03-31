# Deployment Guide

Complete guide to deploy Lingonberry Journal to Oracle Cloud (or any Linux server).

## Prerequisites

- Oracle Cloud account (free tier works great)
- Domain name (optional but recommended) - $10-15/year
- SSH access to your server

## Step 1: Local Development Setup

Make sure everything works locally first:

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Telegram bot token and chat ID

# 3. Test locally
make bot &        # Start bot in background
make webapp       # Start webapp

# 4. Test Mini App
# Open: http://localhost:5000/mini
# Should see your dashboard
```

## Step 2: Get a Domain (Recommended)

### Why you need a domain:
- Telegram Mini Apps require HTTPS
- Professional URL: `journal.yourdomain.com` vs `123.45.67.89:5000`
- Easy SSL with Cloudflare or Let's Encrypt
- Can move servers without changing bot config

### Where to buy:
- **Namecheap** - $10-12/year
- **Cloudflare** - $10/year (includes free SSL proxy)
- **Porkbun** - $8-10/year

### Setup with Cloudflare (Recommended):
1. Buy domain anywhere
2. Point nameservers to Cloudflare (free account)
3. Add A record: `journal` → Your Oracle IP
4. Enable "Proxied" (orange cloud) for free SSL
5. Done! You have `https://journal.yourdomain.com`

## Step 3: Oracle Cloud Setup

### Create VM Instance:

1. Go to Oracle Cloud Console
2. Create Compute Instance:
   - **Image**: Ubuntu 22.04
   - **Shape**: VM.Standard.E2.1.Micro (free tier)
   - **Network**: Allow HTTP (80) and HTTPS (443)
   - **SSH**: Upload your public key

3. Note your public IP address

### Configure Firewall:

```bash
# SSH into your server
ssh ubuntu@YOUR_ORACLE_IP

# Open ports
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo netfilter-persistent save
```

## Step 4: Deploy Application

### On your Oracle server:

```bash
# 1. Install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx

# 2. Clone repository
cd ~
git clone https://github.com/YOUR_USERNAME/lingonberry_journal.git
cd lingonberry_journal

# 3. Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env
# Update:
# - TELEGRAM_JOURAL=your_bot_token
# - TELEGRAM_JOURNAL_CHAT=your_chat_id
# - WEBAPP_URL=https://journal.yourdomain.com/mini (or http://YOUR_IP:5000/mini)
# - WEBAPP_PORT=5000

# 5. Initialize database
python3 -c "from bot import journal_db; journal_db.init_db()"
```

## Step 5: Setup as System Service

Do not run the app with `nohup`, `screen`, or manual `python ... &` on the server. That creates duplicate pollers and fake restarts. Install the bundled systemd units instead. The web service runs under `gunicorn`, not Flask's development server:

```bash
bash scripts/install_systemd.sh --enable --restart

# Check status
bash scripts/manage.sh status

# View logs
bash scripts/manage.sh logs bot
bash scripts/manage.sh logs webapp
```

This installs and manages:
- `journal-bot.service`
- `journal-webapp.service`
- `journal-ctrader-sync.service`
- `journal-sltp-poller.service`

After that, `bash scripts/manage.sh ...` automatically delegates to `systemd` on the server.

## Step 6: Setup Nginx Reverse Proxy (Optional but Recommended)

This allows you to use port 80/443 instead of 5000:

```bash
sudo nano /etc/nginx/sites-available/journal
```

```nginx
server {
    listen 80;
    server_name journal.yourdomain.com;  # or YOUR_IP

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/journal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 7: Setup SSL (If using domain)

```bash
# Get free SSL certificate from Let's Encrypt
sudo certbot --nginx -d journal.yourdomain.com

# Auto-renewal is configured automatically
# Test renewal:
sudo certbot renew --dry-run
```

## Step 8: Update Telegram Bot

Update your bot's Mini App URL:

1. Go to @BotFather on Telegram
2. Send `/mybots`
3. Select your bot
4. Go to "Bot Settings" → "Menu Button"
5. Set URL to: `https://journal.yourdomain.com/mini`

Or update in your `.env`:
```bash
WEBAPP_URL=https://journal.yourdomain.com/mini
```

Then restart bot:
```bash
bash scripts/manage.sh restart bot
```

## Step 9: Test Everything

1. **Test webapp**: Visit `https://journal.yourdomain.com/mini`
2. **Test bot**: Send `/start` to your bot on Telegram
3. **Test Mini App**: Send `/mini` or use the menu button
4. **Log a trade**: Send `/journal` and complete the flow
5. **Check dashboard**: Should see your trade in the Mini App

## Maintenance

For future updates:

```bash
cd ~/lingonberry_journal
git pull --ff-only origin main
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "from bot import journal_db; journal_db.init_db()"
bash scripts/install_systemd.sh --enable --restart
bash scripts/manage.sh status
```

### Update code:

```bash
cd ~/lingonberry_journal
git pull
sudo systemctl restart journal-bot journal-webapp
```

### View logs:

```bash
# Bot logs
sudo journalctl -u journal-bot -f

# Webapp logs
sudo journalctl -u journal-webapp -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Backup database:

```bash
# Backup
cp data/journal.db data/journal.db.backup

# Or automated daily backup
echo "0 2 * * * cp ~/lingonberry_journal/data/journal.db ~/backups/journal-$(date +\%Y\%m\%d).db" | crontab -
```

## Troubleshooting

### Bot not responding:
```bash
sudo systemctl status journal-bot
sudo journalctl -u journal-bot -n 50
```

### Webapp not loading:
```bash
sudo systemctl status journal-webapp
sudo journalctl -u journal-webapp -n 50
curl http://localhost:5000/mini
```

### Mini App shows error:
- Check WEBAPP_URL in `.env` matches your actual URL
- Ensure HTTPS is working (required for Telegram)
- Check CORS is enabled in Flask (already configured)

### SSL certificate issues:
```bash
sudo certbot certificates
sudo certbot renew --force-renewal
```

## Cost Estimate

- **Oracle Cloud VM**: FREE (always free tier)
- **Domain**: $10-15/year
- **SSL Certificate**: FREE (Let's Encrypt)
- **Total**: ~$10-15/year

## Security Notes

1. **Never commit `.env` file** - contains secrets
2. **Use strong passwords** for Oracle Cloud
3. **Keep system updated**: `sudo apt update && sudo apt upgrade`
4. **Restrict SSH**: Only allow your IP if possible
5. **Monitor logs** regularly for suspicious activity

## Next Steps

- Setup automated backups
- Configure monitoring (Uptime Robot, etc.)
- Add more analytics features
- Integrate with cTrader for auto-import

---

Need help? Check the main README or open an issue on GitHub.

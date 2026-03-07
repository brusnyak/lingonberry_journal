# Deploy to Oracle (84.8.249.139)

## SSH and Deploy:
```bash
ssh ubuntu@84.8.249.139
cd lingonberry_journal || git clone https://github.com/brusnyak/lingonberry_journal.git && cd lingonberry_journal
git pull
./deploy.sh
```

## First Time Setup:
```bash
# Install nginx
sudo apt install -y nginx

# Create nginx config
sudo tee /etc/nginx/sites-available/journal > /dev/null <<'EOF'
server {
    listen 80;
    server_name lingonberry.work.gd;
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/journal /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

## DNSExit Setup:
1. Go to DNSExit control panel
2. Add A record: `@` → `84.8.249.139`
3. Wait 5 minutes

## Update Bot:
Edit `.env` on server:
```
WEBAPP_URL=http://lingonberry.work.gd/mini
```

Restart: `sudo systemctl restart journal-bot`

## Done!
Visit: http://lingonberry.work.gd/mini

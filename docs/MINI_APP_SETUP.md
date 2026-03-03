# Telegram Mini App Setup Guide

To use the Trading Journal as a proper Telegram Mini App, your web server must be publicly accessible via HTTPS.

## 1. Expose your Local Server

Since the bot runs locally (or on a server), you need a tunnel for the web app:

### Option A: Ngrok (Fastest)

1. Install Ngrok: `brew install ngrok`
2. Run: `ngrok http 5000`
3. Copy the `https://...` URL provided by Ngrok.

### Option B: Cloudflare Tunnel (Recommended for Production)

1. Install `cloudflared`.
2. Run: `cloudflared tunnel --url http://localhost:5000`
3. Copy the generated `https://...` domain.

## 2. Update .env

Set the `WEBAPP_URL` in your `.env` file to your public URL:

```env
WEBAPP_URL=https://your-tunnel-url.ngrok-free.app
```

## 3. Configure Telegram Bot

Use `/setwebapp` via BotFather or simply use the `/mini` command in your bot after setting the environment variable. The `/mini` command will now point to your premium, mobile-optimized dashboard.

## 4. Why HTTPS?

Telegram requires Mini Apps to be served over HTTPS for security and to allow access to web features (like local storage for your Dark/Light theme).

# rSpotify OAuth Callback Service

## Overview

Self-contained aiohttp web service with automatic SSL certificate management via certbot for handling Spotify OAuth callbacks.

**Architecture:** aiohttp + certbot (v2.0)  
**Story:** 1.4 - Spotify OAuth Authentication Flow  
**Status:** Implementation Complete - Ready for Deployment

## Features

✅ **Async Web Framework** - aiohttp 3.9.1 for high-performance async request handling  
✅ **Automatic SSL** - certbot integration for Let's Encrypt certificate provisioning and renewal  
✅ **Dual-Server Setup** - HTTP (port 80) for ACME challenges, HTTPS (port 443) for OAuth callbacks  
✅ **State Validation** - Secure state parameter validation with 5-minute expiry  
✅ **MongoDB Integration** - Auth code storage with automatic TTL expiry (10 minutes)  
✅ **Telegram Deep Links** - Seamless redirect back to bot after OAuth  
✅ **Error Handling** - User-friendly HTML error pages for all failure scenarios  

## Architecture Flow

```
1. User → /login command in Telegram bot
2. Bot generates secure state parameter
3. Bot stores state in temporary storage (5 min expiry)
4. Bot sends Spotify authorization URL to user
5. User clicks URL → Spotify login/authorization
6. Spotify redirects → https://DOMAIN/spotify/callback?code=...&state=...
7. Web service validates state against temporary storage
8. Web service stores auth code in MongoDB (10 min TTL)
9. Web service redirects → https://t.me/BOT_USERNAME?start={code_id}
10. User clicks → Opens Telegram bot
11. Bot receives /start {code_id}
12. Bot retrieves auth code from MongoDB
13. Bot exchanges code for tokens via Spotify API
14. Bot encrypts and stores tokens
15. Bot confirms success to user
```

## Requirements

### System Requirements
- **OS:** Linux (Ubuntu 20.04+ recommended)
- **Python:** 3.11+
- **Ports:** 80 (HTTP/ACME), 443 (HTTPS/callbacks) must be open and accessible from internet
- **Root Access:** Required for binding to ports 80/443 (or use systemd socket activation)

### DNS Configuration
- **Domain:** A record pointing to your VPS IP
- **Example:** `rspotify.shhvang.space` → `YOUR_VPS_IP`
- **Propagation:** Allow 5-60 minutes for DNS changes to propagate
- **Verification:** `dig rspotify.shhvang.space +short` should return your IP

### Environment Variables

Required in `.env` file:

```bash
# Bot Configuration
BOT_USERNAME=your_bot_username  # Without @ symbol

# Spotify OAuth
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=https://rspotify.shhvang.space/spotify/callback

# SSL Configuration
DOMAIN=rspotify.shhvang.space
CERTBOT_EMAIL=your_email@example.com  # For Let's Encrypt notifications

# Database
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=rspotify_bot
ENCRYPTION_KEY=your_encryption_key
```

## Installation

### 1. Install Dependencies

```bash
cd rspotify-bot
pip install -r requirements.txt
```

**Dependencies:**
- `aiohttp==3.9.1` - Async web framework
- `certbot==2.7.4` - SSL certificate management
- `acme==2.7.4` - ACME protocol implementation
- `pymongo==4.6.1` - MongoDB driver

### 2. Configure Spotify App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications)
2. Create/select your app
3. Go to "Edit Settings"
4. Add Redirect URI: `https://YOUR_DOMAIN/spotify/callback`
5. Save changes

### 3. DNS Setup

```bash
# Verify DNS is configured correctly
dig rspotify.shhvang.space +short
# Should output: YOUR_VPS_IP
```

## Running the Service

### Development (HTTP only - no SSL)

**⚠️ Warning:** Development mode uses HTTP only. OAuth will NOT work without HTTPS in production.

```bash
cd web_callback
python app.py
```

### Production (HTTPS with Let's Encrypt)

**First Run** - Certificate Provisioning:

```bash
# Run as root or with sudo (required for ports 80/443)
sudo python web_callback/app.py
```

On first run, certbot will:
1. Start HTTP server on port 80
2. Request certificate from Let's Encrypt
3. Complete ACME HTTP-01 challenge
4. Download and install certificate
5. Start HTTPS server on port 443

**Certificate Location:** `web_callback/certs/live/YOUR_DOMAIN/`

### Systemd Service (Recommended)

Create `/etc/systemd/system/rspotify-oauth.service`:

```ini
[Unit]
Description=rSpotify OAuth Callback Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/rspotify-bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python web_callback/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rspotify-oauth
sudo systemctl start rspotify-oauth
sudo systemctl status rspotify-oauth
```

## Testing

### Health Check

```bash
# HTTP
curl http://YOUR_DOMAIN/health

# HTTPS (after SSL setup)
curl https://YOUR_DOMAIN/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "oauth-callback",
  "database": "connected",
  "ssl": "enabled"
}
```

### OAuth Flow Test

1. Start the bot: `python rspotify.py`
2. Send `/login` to bot
3. Click authorization URL
4. Authorize with Spotify
5. Should redirect back to Telegram bot
6. Bot should confirm successful connection

### Manual Callback Test

```bash
# Test callback endpoint (after OAuth flow initiated)
curl "https://YOUR_DOMAIN/spotify/callback?code=TEST_CODE&state=TEST_STATE"
```

## Certificate Renewal

Certificates expire after 90 days. Renewal is automatic:

### Manual Renewal

```bash
cd web_callback/certs
certbot renew --config-dir .
```

### Automatic Renewal (Cron)

Add to crontab:

```bash
# Renew certificates daily at 2 AM
0 2 * * * cd /path/to/rspotify-bot/web_callback/certs && certbot renew --config-dir . --quiet
```

The service automatically checks for renewal on startup.

## Troubleshooting

### SSL Certificate Issues

**Problem:** Certificate provisioning fails  
**Solution:**
1. Verify DNS: `dig YOUR_DOMAIN +short` returns correct IP
2. Verify port 80 is open: `sudo netstat -tulpn | grep :80`
3. Check firewall: `sudo ufw status`
4. View certbot logs: `cat web_callback/certs/logs/letsencrypt.log`

### Port Permission Denied

**Problem:** `PermissionError: [Errno 13] Permission denied`  
**Solution:** Run as root/sudo or use port 8080/8443 with reverse proxy

### Database Connection Issues

**Problem:** `Failed to connect to database`  
**Solution:**
1. Verify `MONGODB_URI` in `.env`
2. Check MongoDB Atlas IP whitelist
3. Test connection: `mongosh "YOUR_MONGODB_URI"`

### OAuth State Expired

**Problem:** "Session Expired" error after Spotify redirect  
**Solution:**
- State parameters expire after 5 minutes
- User must complete OAuth flow within 5 minutes
- If expired, use `/login` to start new flow

## API Endpoints

### `GET /`
Root endpoint - service information

### `GET /health`
Health check endpoint
- Returns: JSON with service status and database connection

### `GET /.well-known/acme-challenge/{token}`
ACME challenge endpoint for Let's Encrypt validation
- Used automatically by certbot
- Do not call manually

### `GET /spotify/callback`
OAuth callback endpoint
- Query Parameters:
  - `code` - Authorization code from Spotify
  - `state` - State parameter for CSRF protection
  - `error` - (optional) OAuth error code
- Returns: HTTP 302 redirect to Telegram bot deep link

## Security Considerations

✅ **HTTPS Required** - All callbacks use HTTPS with valid Let's Encrypt certificate  
✅ **State Validation** - CSRF protection via state parameter  
✅ **Time-Limited States** - 5-minute expiry window  
✅ **Time-Limited Auth Codes** - 10-minute MongoDB TTL  
✅ **One-Time Use** - Auth codes deleted after exchange  
✅ **Token Encryption** - All tokens encrypted before database storage  
✅ **Telegram ID Validation** - Auth codes validated against user  

## Files

```
web_callback/
├── app.py                    # Main aiohttp application (NEW v2.0)
├── app_flask_backup.py       # Old Flask implementation (backup)
├── README.md                 # This file
└── certs/                    # SSL certificates (auto-generated, gitignored)
    ├── live/
    │   └── YOUR_DOMAIN/
    │       ├── fullchain.pem
    │       └── privkey.pem
    ├── work/                 # Certbot working directory
    └── logs/                 # Certbot logs
```

## Migration from Flask

The old Flask implementation has been replaced with aiohttp + certbot. Key changes:

- **Before:** Flask + Nginx + manual certbot CLI
- **After:** aiohttp + integrated certbot Python library
- **Benefits:**
  - Self-contained SSL automation
  - No Nginx dependency
  - No manual certificate setup
  - Fully portable Python deployment
  - Cleaner async architecture

Old Flask implementation backed up at `web_callback/app_flask_backup.py`.

## Support

For issues or questions:
- Story: `docs/stories/1.4.spotify-oauth-authentication-flow.md`
- Architecture: `docs/architecture/6-core-workflows.md#oauth-2.0-authorization-flow`
- Config: `.env.example` for required environment variables

## License

Part of rSpotify Bot - See main project README for license information.

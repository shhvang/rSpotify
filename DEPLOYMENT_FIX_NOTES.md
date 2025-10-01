# Deployment Fix Notes - October 1, 2025

## Problem Summary
The CI/CD deployment was failing with these errors:
1. `nginx: [emerg] open() "/etc/letsencrypt/options-ssl-nginx.conf" failed` - Nginx trying to load SSL config that doesn't exist
2. `rspotify-flask: ERROR (spawn error)` - Supervisor trying to start Flask app that no longer exists
3. Architecture mismatch - deployment script still configured for old Flask + Nginx setup

## Root Cause
The deployment script (`scripts/deploy.sh`) and GitHub Actions workflow (`.github/workflows/main.yml`) were **not updated** when we pivoted from Flask+Nginx to aiohttp+certbot architecture.

## What Was Fixed

### 1. Deployment Script (`scripts/deploy.sh`)
**Removed:**
- ❌ Nginx installation (`apt-get install nginx`)
- ❌ Nginx configuration file creation
- ❌ `rspotify-flask` supervisor configuration
- ❌ DUCKDNS_TOKEN and DUCKDNS_DOMAIN environment variables

**Updated:**
- ✅ Renamed supervisor service: `rspotify-flask` → `rspotify-oauth`
- ✅ Updated service description: "Flask OAuth" → "aiohttp OAuth callback service with automatic SSL"
- ✅ Added `DOMAIN`, `BOT_USERNAME`, `CERTBOT_EMAIL` environment variables
- ✅ Created `/opt/rspotify-bot/letsencrypt` directory for SSL certificates
- ✅ Updated `SPOTIFY_REDIRECT_URI` to use fixed domain: `https://rspotify.shhvang.space/spotify/callback`

### 2. GitHub Actions Workflow (`.github/workflows/main.yml`)
**Removed:**
- ❌ `DUCKDNS_TOKEN` and `DUCKDNS_DOMAIN` secret exports

**Added:**
- ✅ `BOT_USERNAME` secret export
- ✅ `CERTBOT_EMAIL` secret export

## GitHub Secrets That Need To Be Added
Before the next deployment, add these secrets to the GitHub repository:
1. `BOT_USERNAME` - Your Telegram bot username (e.g., `rspotify_bot`)
2. `CERTBOT_EMAIL` - Email for Let's Encrypt notifications (e.g., `your-email@example.com`)

**To add secrets:**
1. Go to: `https://github.com/shhvang/rSpotify/settings/secrets/actions`
2. Click "New repository secret"
3. Add both secrets listed above

## Manual VPS Cleanup Required (Optional)
If you want to clean up the old configuration on your VPS, SSH in and run:

```bash
# Remove old Flask supervisor config
sudo rm -f /etc/supervisor/conf.d/rspotify-flask.conf

# Remove Nginx configuration
sudo rm -f /etc/nginx/sites-enabled/rspotify
sudo rm -f /etc/nginx/sites-available/rspotify

# Optionally uninstall Nginx (if not used by other services)
# sudo apt-get remove nginx

# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update
```

## New Architecture Summary
- **Web Framework:** aiohttp 3.9.1 (replaces Flask 3.0)
- **SSL Management:** certbot 2.7.4 Python library (replaces manual Nginx + Certbot CLI)
- **Reverse Proxy:** None needed (aiohttp handles HTTPS directly)
- **Ports:** 80 (ACME challenges), 443 (HTTPS callbacks)
- **Domain:** rspotify.shhvang.space (DNS A record must point to VPS IP)

## Next Deployment
The next deployment will:
1. ✅ Skip Nginx installation and configuration
2. ✅ Create `rspotify-oauth` supervisor service (not `rspotify-flask`)
3. ✅ Run aiohttp web server with integrated SSL automation
4. ✅ Automatically provision Let's Encrypt certificates on first run

## Verification Steps After Deployment
1. Check supervisor status: `sudo supervisorctl status`
   - Should see: `rspotify-bot: RUNNING` and `rspotify-oauth: RUNNING`
2. Check logs: 
   - Bot: `/opt/rspotify-bot/logs/bot_output.log`
   - OAuth: `/opt/rspotify-bot/logs/oauth_output.log`
3. Test OAuth flow:
   - Send `/login` to bot
   - Click Spotify authorization link
   - Should redirect to Telegram with success message

## Related Documentation
- **Architecture Change:** See `SPRINT_CHANGE_PROPOSAL.md` for detailed architectural analysis
- **Story 1.4:** See `docs/stories/1.4.spotify-oauth-authentication-flow.md` for implementation details
- **Implementation Guide:** See `IMPLEMENTATION_GUIDE.md` for development setup

---

**Status:** ✅ Fixed and pushed to main branch (commit 2f8d07a, 586c7ab)
**Next Action:** Add GitHub secrets (`BOT_USERNAME`, `CERTBOT_EMAIL`) then trigger deployment

---

## Update: Port Binding Fix (October 1, 2025)

### Additional Problem Discovered
After initial deployment fix, the `rspotify-oauth` service was still failing with a spawn error:
```
rspotify-oauth: ERROR (not running)
rspotify-oauth: ERROR (spawn error)
```

**Root Cause:** The aiohttp OAuth service needs to bind to **privileged ports 80 and 443** for SSL certificate provisioning and HTTPS traffic. By default, only root can bind to ports < 1024.

### Solution: Linux Capabilities
Instead of running the service as root (security risk), we use Linux capabilities to grant the Python binary permission to bind to privileged ports:

```bash
# Install libcap2-bin package
apt-get install -y libcap2-bin

# Grant Python the CAP_NET_BIND_SERVICE capability
setcap 'cap_net_bind_service=+ep' /opt/rspotify-bot/venv/bin/python3.11
```

This allows the `rspotify` user (non-root) to safely bind to ports 80 and 443.

### Changes Made
- ✅ Added `libcap2-bin` to apt package list
- ✅ Added `setcap` command after pip install
- ✅ Service continues to run as `rspotify` user (secure)

**Status:** ✅ Fixed in commit [pending]

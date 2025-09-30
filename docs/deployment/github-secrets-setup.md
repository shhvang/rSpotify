# GitHub Secrets Setup Guide

Complete guide for configuring all GitHub Secrets required for automated deployment.

## Required Secrets Checklist

- [ ] DEPLOY_SSH_KEY
- [ ] STAGING_HOST  
- [ ] STAGING_BOT_TOKEN
- [ ] STAGING_MONGODB_URI
- [ ] PRODUCTION_HOST
- [ ] PRODUCTION_BOT_TOKEN
- [ ] PRODUCTION_MONGODB_URI
- [ ] SPOTIFY_CLIENT_ID
- [ ] SPOTIFY_CLIENT_SECRET
- [ ] DUCKDNS_TOKEN
- [ ] DUCKDNS_DOMAIN
- [ ] OWNER_TELEGRAM_ID
- [ ] ENCRYPTION_KEY

## 1. SSH Deployment Key

**Name:** `DEPLOY_SSH_KEY`

Generate SSH key pair:
```bash
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/rspotify_deploy
ssh-copy-id -i ~/.ssh/rspotify_deploy.pub user@your-vps-ip
cat ~/.ssh/rspotify_deploy  # Copy this entire output
```

Add the PRIVATE key content to GitHub Secrets.

## 2. Staging Secrets

**STAGING_HOST:** Your staging VPS IP (e.g., `192.168.1.100`)  
**STAGING_BOT_TOKEN:** Get from @BotFather (test bot)  
**STAGING_MONGODB_URI:** `mongodb+srv://user:pass@cluster.mongodb.net/`

## 3. Production Secrets

**PRODUCTION_HOST:** Your production VPS IP  
**PRODUCTION_BOT_TOKEN:** Get from @BotFather (production bot, 24/7)  
**PRODUCTION_MONGODB_URI:** Same as staging or separate cluster

## 4. Spotify API

Get from https://developer.spotify.com/dashboard:
- **SPOTIFY_CLIENT_ID:** Client ID from your Spotify app
- **SPOTIFY_CLIENT_SECRET:** Client secret from your Spotify app

Add redirect URIs in Spotify dashboard:
- `https://yourdomain.duckdns.org/callback`

## 5. DuckDNS

Get from https://www.duckdns.org:
- **DUCKDNS_TOKEN:** Your DuckDNS token
- **DUCKDNS_DOMAIN:** Just subdomain (e.g., `rspotify`, not full URL)

## 6. Owner Configuration

**OWNER_TELEGRAM_ID:** Get from @userinfobot on Telegram

## 7. Encryption Key

Generate with Python:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

**ENCRYPTION_KEY:** Use the generated key

## Adding to GitHub

1. Go to repository Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Add each secret with exact name from above
4. Verify all 13 secrets are added

## Next Steps

After adding all secrets, proceed to [Initial Deployment](./initial-deployment.md).

# Initial Deployment Guide

Step-by-step guide for deploying rSpotify bot to your VPS for the first time.

## Prerequisites

- [ ] VPS with Ubuntu 22.04 (or similar)
- [ ] SSH access to VPS
- [ ] All GitHub Secrets configured ([guide](./github-secrets-setup.md))
- [ ] Bot tokens from @BotFather
- [ ] DuckDNS subdomain configured

## Phase 1: VPS Preparation

### 1.1 VPS Requirements

- Ubuntu 22.04 LTS (recommended)
- Minimum 1GB RAM
- 10GB storage
- Public IP address
- Port 22 (SSH), 80 (HTTP), 443 (HTTPS) open

### 1.2 Initial VPS Setup

SSH into your VPS:
```bash
ssh your-user@your-vps-ip
```

Update system:
```bash
sudo apt update && sudo apt upgrade -y
```

Create deployment user (if needed):
```bash
sudo adduser rspotify
sudo usermod -aG sudo rspotify
```

### 1.3 Configure SSH Access

Add your deploy SSH public key:
```bash
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# Paste your public key, save and exit
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

Test SSH access from local machine:
```bash
ssh -i ~/.ssh/rspotify_deploy user@vps-ip
```

## Phase 2: Configure Inventory Files

### 2.1 Edit Staging Inventory

Edit `rspotify-bot/ansible/staging_inventory`:
```ini
[rspotify_servers]
staging-vps ansible_host=YOUR_STAGING_IP ansible_user=YOUR_USER ansible_port=22
```

Replace:
- `YOUR_STAGING_IP` with actual IP
- `YOUR_USER` with SSH username

### 2.2 Edit Production Inventory

Edit `rspotify-bot/ansible/production_inventory`:
```ini
[rspotify_servers]
production-vps ansible_host=YOUR_PRODUCTION_IP ansible_user=YOUR_USER ansible_port=22
```

## Phase 3: Create Develop Branch

```bash
cd rspotify-bot
git checkout main
git pull origin main
git checkout -b develop
git push -u origin develop
```

## Phase 4: Staging Deployment

### 4.1 Merge to Develop

```bash
git checkout develop
git merge feature/story-1.6-deployment-operationalization
git push origin develop
```

### 4.2 Monitor Deployment

1. Go to GitHub Actions tab
2. Watch "CI/CD Pipeline" workflow
3. Check "Deploy to Staging" job

### 4.3 Verify Staging Deployment

SSH to staging VPS:
```bash
ssh user@staging-vps-ip

# Check bot process
sudo supervisorctl status rspotify-bot

# Check logs
tail -f /opt/rspotify-bot/logs/bot_output.log

# Test bot
# Message your test bot with /ping
```

Expected response: Bot should reply to /ping command

## Phase 5: Production Deployment

### 5.1 Create Pull Request

1. Create PR from `develop` to `main`
2. Review all changes
3. Merge PR after approval

### 5.2 Monitor Production Deployment

1. Watch GitHub Actions
2. Check "Deploy to Production" job
3. Wait for owner notification from bot

### 5.3 Verify Production

SSH to production VPS:
```bash
ssh user@production-vps-ip
sudo supervisorctl status rspotify-bot
tail -f /opt/rspotify-bot/logs/bot_output.log
```

Test production bot with /ping

## Phase 6: Post-Deployment Checks

### 6.1 Verify All Services

```bash
# Check supervisor
sudo supervisorctl status

# Check nginx
sudo systemctl status nginx

# Check SSL certificate
sudo certbot certificates

# Check DuckDNS
curl "https://www.duckdns.org/update?domains=YOURDOMAIN&token=YOURTOKEN&ip="
```

### 6.2 Test OAuth Flow

1. Message bot with /login
2. Click OAuth link
3. Verify redirect works (HTTPS)
4. Complete Spotify authorization
5. Check bot receives tokens

### 6.3 Monitor Logs

```bash
# Bot logs
tail -f /opt/rspotify-bot/logs/bot_output.log

# Nginx logs
tail -f /opt/rspotify-bot/logs/nginx_access.log

# System logs
sudo journalctl -u supervisor -f
```

## Common First-Time Issues

### Issue: Ansible fails with permission denied
**Solution:** Verify SSH key is added to GitHub Secrets correctly

### Issue: Bot doesn't start
**Solution:** Check environment variables in `/opt/rspotify-bot/.env`

### Issue: SSL certificate fails
**Solution:** Verify DuckDNS domain points to VPS IP, wait for DNS propagation

### Issue: OAuth callback 404
**Solution:** Check nginx config and Flask server on port 8080

## Success Criteria

- [ ] Staging bot responds to /ping
- [ ] Production bot responds to /ping
- [ ] Owner receives startup notification
- [ ] HTTPS works for OAuth callback
- [ ] Logs are being written
- [ ] Supervisor auto-restarts bot on crash

## Next Steps

- Test OAuth flow completely
- Configure monitoring/alerts
- Set up regular backups
- Review [Troubleshooting Guide](./troubleshooting.md)

---

**Story:** 1.6 - Deployment Operationalization  
**Last Updated:** September 30, 2025

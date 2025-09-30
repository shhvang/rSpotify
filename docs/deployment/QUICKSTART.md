# Quick Start - Simplified Deployment (No Staging)

**Your Setup:** Single VPS, local testing, no DuckDNS yet

## Step 1: Fill in VPS Details

Edit `ansible/production_inventory`:

```ini
[rspotify_servers]
production-vps ansible_host=YOUR_VPS_IP_HERE ansible_user=root ansible_port=22
```

Replace `YOUR_VPS_IP_HERE` with your actual VPS IP address.

## Step 2: Required GitHub Secrets (Minimal Set)

Add these 6 secrets to GitHub (Settings > Secrets > Actions):

### 1. DEPLOY_SSH_KEY
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "deploy" -f ~/.ssh/rspotify_deploy

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/rspotify_deploy.pub root@YOUR_VPS_IP

# Copy PRIVATE key content for GitHub
cat ~/.ssh/rspotify_deploy
# Paste entire output as DEPLOY_SSH_KEY secret
```

### 2. PRODUCTION_HOST
Value: Your VPS IP address (e.g., `192.168.1.100`)

### 3. PRODUCTION_BOT_TOKEN
1. Message @BotFather on Telegram
2. `/newbot`
3. Follow prompts
4. Copy token (e.g., `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 4. MONGODB_URI
Your existing MongoDB Atlas connection string
(e.g., `mongodb+srv://user:pass@cluster.mongodb.net/`)

### 5. OWNER_TELEGRAM_ID
1. Message @userinfobot on Telegram
2. Copy your ID (e.g., `123456789`)

### 6. ENCRYPTION_KEY
```python
# Run this in Python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
# Copy output
```

## Step 3: Commit and Deploy

```bash
# Commit simplified configuration
git add .
git commit -m "config: Simplify deployment for single VPS setup"
git push origin feature/story-1.6-deployment-operationalization

# Merge to main
git checkout main
git merge feature/story-1.6-deployment-operationalization
git push origin main
```

This will automatically trigger deployment! 🚀

## Step 4: Verify Deployment

```bash
# SSH to VPS
ssh -i ~/.ssh/rspotify_deploy root@YOUR_VPS_IP

# Check bot is running
sudo supervisorctl status

# Check logs
tail -f /opt/rspotify-bot/logs/bot_output.log

# Exit SSH
exit
```

## Step 5: Test Bot

Message your bot on Telegram:
- `/ping` → Should respond with confirmation

You should also receive a startup notification!

## What About OAuth/Spotify?

We'll add that in Story 1.4 when implementing authentication:
- Get DuckDNS domain
- Add Spotify app credentials
- Configure OAuth callback

For now, the bot works without OAuth (just basic commands).

## Troubleshooting

**Deployment fails?**
- Check GitHub Actions logs
- Verify all 6 secrets are added correctly
- Test SSH access: `ssh -i ~/.ssh/rspotify_deploy root@VPS_IP`

**Bot doesn't start?**
- SSH to VPS
- Check logs: `tail -f /opt/rspotify-bot/logs/bot_error.log`
- Verify environment: `cat /opt/rspotify-bot/.env`

## What's Different from Original Plan?

- ✅ No staging environment (test locally)
- ✅ No DuckDNS yet (Story 1.4)
- ✅ No Spotify OAuth yet (Story 1.4)
- ✅ Simplified GitHub Secrets (6 instead of 13)
- ✅ Direct to production deployment

---

**Last Updated:** September 30, 2025

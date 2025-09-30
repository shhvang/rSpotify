# Troubleshooting Guide

Common deployment issues and their solutions.

## Ansible Deployment Issues

### Error: Permission denied (publickey)

**Symptoms:** Ansible cannot connect to VPS

**Solutions:**
1. Verify SSH key is correct in GitHub Secrets:
   ```bash
   cat ~/.ssh/rspotify_deploy  # Should match DEPLOY_SSH_KEY
   ```

2. Check VPS authorized_keys:
   ```bash
   ssh user@vps-ip
   cat ~/.ssh/authorized_keys
   ```

3. Test SSH manually:
   ```bash
   ssh -i ~/.ssh/rspotify_deploy user@vps-ip
   ```

4. Verify inventory file has correct user/host

### Error: Ansible playbook fails on task X

**Solutions:**
1. Check Ansible logs in GitHub Actions
2. SSH to VPS and run failed command manually
3. Verify VPS has internet access
4. Check VPS disk space: `df -h`

## Bot Not Starting

### Supervisor shows bot as FATAL

**Check logs:**
```bash
sudo supervisorctl tail rspotify-bot stderr
tail -f /opt/rspotify-bot/logs/bot_error.log
```

**Common causes:**
1. **Missing environment variable**
   ```bash
   cat /opt/rspotify-bot/.env  # Verify all vars present
   ```

2. **Invalid bot token**
   ```bash
   # Test token manually
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
   ```

3. **Python dependencies missing**
   ```bash
   cd /opt/rspotify-bot/src
   ../venv/bin/pip list
   ```

4. **Database connection failed**
   ```bash
   # Test MongoDB connection
   ../venv/bin/python -c "from pymongo import MongoClient; client = MongoClient('YOUR_URI'); print(client.server_info())"
   ```

### Bot starts but doesn't respond

**Check:**
1. Bot process is running: `sudo supervisorctl status`
2. Network connectivity: `ping telegram.org`
3. Firewall rules: `sudo ufw status`
4. Bot logs for errors

## SSL/HTTPS Issues

### Certificate generation fails

**Error:** Certbot cannot obtain certificate

**Solutions:**
1. Verify DuckDNS domain resolves to VPS:
   ```bash
   nslookup yourdomain.duckdns.org
   dig yourdomain.duckdns.org
   ```

2. Update DuckDNS IP:
   ```bash
   curl "https://www.duckdns.org/update?domains=YOURDOMAIN&token=TOKEN&ip="
   ```

3. Wait for DNS propagation (up to 10 minutes)

4. Check port 80 is accessible:
   ```bash
   sudo netstat -tulpn | grep :80
   ```

5. Temporarily stop nginx and retry:
   ```bash
   sudo systemctl stop nginx
   sudo certbot certonly --standalone -d yourdomain.duckdns.org
   sudo systemctl start nginx
   ```

### OAuth callback returns 502

**Solutions:**
1. Check Flask app is running:
   ```bash
   netstat -tulpn | grep 8080
   ```

2. Check nginx configuration:
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

3. Check nginx error logs:
   ```bash
   tail -f /opt/rspotify-bot/logs/nginx_error.log
   ```

## Database Connection Issues

### MongoDB connection timeout

**Solutions:**
1. Verify MongoDB URI format is correct
2. Check MongoDB Atlas network access:
   - Add VPS IP to whitelist
   - Or allow access from anywhere (0.0.0.0/0)

3. Test connection:
   ```bash
   /opt/rspotify-bot/venv/bin/python -c "from pymongo import MongoClient; print(MongoClient('URI').server_info())"
   ```

## GitHub Actions Issues

### Workflow fails on secrets

**Error:** Secret not found or empty

**Solutions:**
1. Go to GitHub Settings > Secrets > Actions
2. Verify secret name matches exactly (case-sensitive)
3. Re-add secret with correct value
4. Re-run workflow

### Deployment job stuck

**Solutions:**
1. Cancel and re-run workflow
2. Check VPS is accessible
3. Review Ansible task logs

## Bot Specific Issues

### Bot receives messages but doesn't respond

**Check:**
1. Command handlers registered:
   ```python
   # In logs, should see: "Registered command: /ping"
   ```

2. Error in command handler:
   ```bash
   tail -f /opt/rspotify-bot/logs/bot_error.log | grep -i error
   ```

3. Rate limiting triggered

### OAuth flow breaks

**Symptoms:** User clicks login but callback fails

**Solutions:**
1. Verify Spotify redirect URI matches:
   - Spotify Dashboard: `https://yourdomain.duckdns.org/callback`
   - Bot .env file: Check SPOTIFY_REDIRECT_URI

2. Check Flask web callback is running:
   ```bash
   ps aux | grep flask
   netstat -tulpn | grep 8080
   ```

3. Test callback endpoint:
   ```bash
   curl https://yourdomain.duckdns.org/callback
   # Should not return 404
   ```

## Useful Debugging Commands

### Check all services
```bash
sudo supervisorctl status
sudo systemctl status nginx
sudo systemctl status supervisor
```

### View all logs
```bash
# Bot logs
tail -f /opt/rspotify-bot/logs/*.log

# System logs
sudo journalctl -u supervisor -f
sudo journalctl -u nginx -f
```

### Test bot manually
```bash
cd /opt/rspotify-bot/src
../venv/bin/python rspotify.py
# Ctrl+C to stop
```

### Restart services
```bash
sudo supervisorctl restart rspotify-bot
sudo systemctl restart nginx
```

### Check disk space
```bash
df -h
du -sh /opt/rspotify-bot/*
```

### Monitor resource usage
```bash
htop
free -h
```

## Getting Help

If issues persist:

1. Check GitHub Actions logs
2. Review all VPS logs
3. Test each component individually
4. Verify all secrets/credentials
5. Check [Initial Deployment Guide](./initial-deployment.md)

## Emergency Rollback

If deployment completely breaks, see [Rollback Guide](./rollback-guide.md).

---

**Story:** 1.6 - Deployment Operationalization  
**Last Updated:** September 30, 2025

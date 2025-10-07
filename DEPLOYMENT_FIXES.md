# Deployment Fixes Documentation

## Issues Fixed - October 7, 2025

### 1. **josepy Version Conflict** 
**Problem:** `josepy` v2.1.0 removed `ComparableX509` attribute causing `acme==2.7.4` to crash on import.

**Solution:** Pinned `josepy==1.14.0` in `requirements.txt`

**Impact:** Prevents OAuth service startup failures on fresh deployments.

---

### 2. **PID File Collision Between Environments**
**Problem:** Both production and test bots used `/tmp/rspotify-bot.pid`, causing race conditions where processes would terminate each other.

**Solution:** 
- Added `RS_BOT_PID_FILE` environment variable support
- Updated deployment scripts to set unique PID files:
  - Production: `/tmp/rspotify-bot-production.pid`
  - Test: `/tmp/rspotify-bot-test.pid`
- Added `RS_BOT_PID_FILE` to `.env.example`

**Impact:** Eliminates bot restart loops in dual-environment deployments.

---

### 3. **Misleading Flask Supervisor Service**
**Problem:** Service named `rspotify-flask` was actually running aiohttp OAuth service, causing confusion.

**Solution:** 
- Removed `rspotify-flask` supervisor config
- Service properly named `rspotify-oauth` in deployment scripts
- No Flask dependencies or code remain in the project

**Impact:** Clearer service naming and reduced confusion.

---

### 4. **OAuth Port Configuration for Multi-Environment**
**Problem:** Both production and test OAuth services attempted to use privileged ports 80/443, causing port conflicts and SSL certificate issues.

**Solution:**
- **Production:** Port 6969 (HTTP), Port 6970 (HTTPS)
- **Test:** Port 7000 (HTTP), Port 7001 (HTTPS)
- Updated `.env.example` with port configuration
- Both deployment scripts now configure unique ports

**Impact:** 
- Eliminates port conflicts between environments
- Allows both OAuth services to obtain SSL certificates
- No root privileges needed (CAP_NET_BIND_SERVICE handles it)

---

## Files Modified

### Requirements
- ✅ `requirements.txt` - Added `josepy==1.14.0` pin

### Configuration
- ✅ `.env.example` - Added `RS_BOT_PID_FILE` and OAuth port configuration

### Deployment Scripts
- ✅ `scripts/deploy.sh` - Added PID file env var, updated ports to 6969/6970
- ✅ `scripts/deploy-test.sh` - Added PID file env var, updated ports to 7000/7001

---

## Verification Steps for Fresh Deployment

1. **Check dependencies install correctly:**
   ```bash
   pip install -r requirements.txt
   # Should install josepy==1.14.0 (not 2.1.0)
   ```

2. **Verify unique PID files:**
   ```bash
   # Production will use: /tmp/rspotify-bot-production.pid
   # Test will use: /tmp/rspotify-bot-test.pid
   ls -la /tmp/rspotify-bot*.pid
   ```

3. **Verify service ports:**
   ```bash
   # Production OAuth on 6969/6970
   netstat -tulpn | grep ':6969'
   
   # Test OAuth on 7000/7001
   netstat -tulpn | grep ':7000'
   ```

4. **Verify no Flask services:**
   ```bash
   supervisorctl status | grep flask
   # Should return nothing
   ```

---

## Important Notes

### Port 80 Transition
- **Current production** is still running on port 80 temporarily
- **Future deployments to `main` branch** will use port 6969/6970
- No manual intervention needed - deployment script handles it

### SSL Certificates
- Each OAuth service obtains its own SSL certificate via certbot
- Certificates stored in: `${APP_DIR}/repo/web_callback/certs/`
- Automatic renewal configured by certbot

### Python Capabilities
- Both environments use `CAP_NET_BIND_SERVICE` to bind to ports without root
- Set on: `/usr/bin/python3.11` via `setcap`

---

## Future Deployment Checklist

When deploying to a fresh VPS:

- [ ] Ensure DNS is configured for both domains
- [ ] Run production deployment: `./scripts/deploy.sh`
- [ ] Run test deployment: `./scripts/deploy-test.sh`
- [ ] Verify all services running: `supervisorctl status`
- [ ] Check OAuth endpoints respond on configured ports
- [ ] Verify SSL certificates obtained successfully
- [ ] Test Spotify OAuth flow on both environments

---

## Rollback Instructions

If issues occur:

1. **Check logs:**
   ```bash
   tail -f /opt/rspotify-bot/logs/oauth_error.log
   tail -f /opt/rspotify-bot-test/logs/oauth_error.log
   ```

2. **Restart services:**
   ```bash
   supervisorctl restart rspotify-bot rspotify-oauth
   supervisorctl restart rspotify-bot-test rspotify-oauth-test
   ```

3. **Clear PID files if stuck:**
   ```bash
   rm -f /tmp/rspotify-bot*.pid
   supervisorctl restart all
   ```

---

## Contact & Support

- GitHub Issues: https://github.com/shhvang/rSpotify/issues
- Deployment managed via GitHub Actions
- Manual deployment scripts in `scripts/` directory

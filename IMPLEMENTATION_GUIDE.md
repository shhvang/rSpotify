# ?? Implementation Guide: aiohttp + SSL Automation

**Story:** 1.4 - Spotify OAuth Authentication Flow  
**Architecture:** Self-contained aiohttp + certbot SSL automation  
**Status:** Ready to implement  

---

## Quick Start Checklist

### DNS Configuration (Do This First!)
- [ ] Log into your domain registrar (where you bought `shhvang.space`)
- [ ] Add A record: `rspotify.shhvang.space` ? Your VPS IP
- [ ] Wait 5-60 minutes for DNS propagation
- [ ] Test: `dig rspotify.shhvang.space +short` should return your VPS IP

### Environment Variables (Add to `.env`)
```bash
# Existing vars
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=https://rspotify.shhvang.space/spotify/callback

# NEW - Add these
BOT_USERNAME=your_bot_username  # e.g., "rSpotifyBot" (without @)
DOMAIN=rspotify.shhvang.space
CERTBOT_EMAIL=your_email@example.com  # For Let's Encrypt notifications
```

### Dependencies (Update `requirements.txt`)
```txt
# REMOVE
Flask==3.0

# ADD
aiohttp==3.9.1
certbot==2.7.4
acme==2.7.4
```

---

## Implementation Tasks

### Task 1: Update Story 1.4 Documentation
Update `docs/stories/1.4.spotify-oauth-authentication-flow.md` with new tasks:

**Key Changes:**
1. Replace Task 2 (Flask implementation) with aiohttp + certbot task
2. Replace Task 3 (auth service) to use code retrieval pattern
3. Add new Task 9b for bot deep link handler
4. Update Dev Notes with new OAuth flow diagram

**Reference:** See Sprint Change Proposal for detailed task breakdowns

---

### Task 2: Implement aiohttp Web Service

**File:** `web_callback/app.py`

**Core Structure:**
```python
import asyncio
import logging
from datetime import datetime, timedelta
from aiohttp import web
from certbot import main as certbot_main
from rspotify_bot.config import Config
from rspotify_bot.services.database import DatabaseService

# Initialize
app = web.Application()
db_service = None

# ACME Challenge Handler
async def acme_challenge(request):
    '''Serve ACME challenge for Let's Encrypt validation.'''
    token = request.match_info['token']
    # Read challenge response from certbot directory
    challenge_path = f'/path/to/acme-challenge/{token}'
    with open(challenge_path, 'r') as f:
        return web.Response(text=f.read())

# OAuth Callback Handler
async def spotify_callback(request):
    '''Handle Spotify OAuth callback with code storage.'''
    try:
        # 1. Get code and state from query params
        auth_code = request.query.get('code')
        state = request.query.get('state')
        error = request.query.get('error')
        
        if error:
            return web.Response(text=f'OAuth cancelled: {error}', status=400)
        
        if not auth_code or not state:
            return web.Response(text='Missing parameters', status=400)
        
        # 2. Validate state (get telegram_id from temporary storage)
        # TODO: Implement temporary storage lookup
        
        # 3. Store auth code in oauth_codes collection
        code_doc = {
            'telegram_id': telegram_id,  # From state validation
            'auth_code': auth_code,
            'state': state,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=10)
        }
        result = await db_service.database.oauth_codes.insert_one(code_doc)
        code_id = str(result.inserted_id)
        
        # 4. Redirect to Telegram deep link
        bot_username = Config.BOT_USERNAME
        telegram_url = f'https://t.me/{bot_username}?start={code_id}'
        
        return web.Response(
            status=302,
            headers={'Location': telegram_url}
        )
        
    except Exception as e:
        logging.error(f'Callback error: {e}')
        return web.Response(text='Internal error', status=500)

# Routes
app.router.add_get('/.well-known/acme-challenge/{token}', acme_challenge)
app.router.add_get('/spotify/callback', spotify_callback)

# SSL Setup Function
async def setup_ssl():
    '''Request SSL certificate via certbot if not exists.'''
    cert_path = f'web_callback/certs/live/{Config.DOMAIN}/fullchain.pem'
    
    if not os.path.exists(cert_path):
        logging.info('Requesting SSL certificate from Let's Encrypt...')
        # Run certbot to get certificate
        certbot_main.main([
            'certonly',
            '--standalone',
            '--non-interactive',
            '--agree-tos',
            '--email', Config.CERTBOT_EMAIL,
            '-d', Config.DOMAIN,
            '--config-dir', 'web_callback/certs'
        ])
        logging.info('SSL certificate obtained!')
    else:
        logging.info('SSL certificate already exists')

# Main Entry
if __name__ == '__main__':
    # Initialize database
    loop = asyncio.get_event_loop()
    db_service = DatabaseService()
    loop.run_until_complete(db_service.connect())
    
    # Setup SSL
    loop.run_until_complete(setup_ssl())
    
    # Run HTTPS server
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(
        f'web_callback/certs/live/{Config.DOMAIN}/fullchain.pem',
        f'web_callback/certs/live/{Config.DOMAIN}/privkey.pem'
    )
    
    web.run_app(app, host='0.0.0.0', port=443, ssl_context=ssl_context)
```

**Note:** This is a skeleton. You'll need to:
1. Implement proper temporary storage for state validation
2. Add comprehensive error handling
3. Add logging throughout
4. Handle certificate renewal logic
5. Implement graceful shutdown

---

### Task 3: Update Bot for Deep Link Handling

**File:** `rspotify_bot/handlers/user_commands.py`

**Add/Update Start Handler:**
```python
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handle /start command with OAuth code retrieval.'''
    telegram_id = update.effective_user.id
    
    # Check if command has parameter (deep link code_id)
    if context.args:
        code_id = context.args[0]
        await handle_oauth_code_retrieval(update, context, telegram_id, code_id)
        return
    
    # Normal start message
    await update.message.reply_text("Welcome to rSpotify! Use /login to connect your Spotify account.")

async def handle_oauth_code_retrieval(update, context, telegram_id, code_id):
    '''Retrieve auth code and exchange for tokens.'''
    try:
        from bson import ObjectId
        from rspotify_bot.services.auth import exchange_code_for_tokens
        from rspotify_bot.services.database import DatabaseService
        
        db = DatabaseService()
        
        # 1. Retrieve auth code from oauth_codes collection
        code_doc = await db.database.oauth_codes.find_one({'_id': ObjectId(code_id)})
        
        if not code_doc:
            await update.message.reply_text("? Invalid or expired authorization code. Please try /login again.")
            return
        
        # 2. Validate telegram_id matches
        if code_doc['telegram_id'] != telegram_id:
            await update.message.reply_text("? Security error: Authorization code mismatch.")
            await db.database.oauth_codes.delete_one({'_id': ObjectId(code_id)})
            return
        
        # 3. Exchange code for tokens
        auth_code = code_doc['auth_code']
        tokens = await exchange_code_for_tokens(auth_code)
        
        # 4. Store encrypted tokens in users collection
        # TODO: Encrypt tokens and store in database
        
        # 5. Delete auth code (one-time use)
        await db.database.oauth_codes.delete_one({'_id': ObjectId(code_id)})
        
        # 6. Confirm success
        await update.message.reply_text(
            "? Successfully connected to Spotify!\\n\\n"
            "Now set your custom name with /setname"
        )
        
    except Exception as e:
        logging.error(f'OAuth code retrieval error: {e}')
        await update.message.reply_text("? Authentication failed. Please try /login again.")
```

---

### Task 4: Create MongoDB Indexes

**Run on MongoDB Atlas or via Python:**
```python
# In your database initialization
db.oauth_codes.create_index([("expires_at", 1)], expireAfterSeconds=0)
db.oauth_codes.create_index([("telegram_id", 1)])
```

**Or MongoDB Shell:**
```javascript
use rspotify_bot
db.oauth_codes.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })
db.oauth_codes.createIndex({ "telegram_id": 1 })
```

---

## Testing Strategy

### Local Testing (Before VPS Deployment)
1. **Mock SSL:** Use self-signed certificate for local testing
2. **ngrok:** Use ngrok for temporary HTTPS tunnel
3. **Let's Encrypt Staging:** Test with staging environment first

**ngrok command:**
```bash
ngrok http 5000
# Use the https URL as SPOTIFY_REDIRECT_URI for testing
```

### Integration Testing on VPS
1. Ensure DNS is propagated
2. Deploy web service
3. Watch logs: `tail -f logs/rspotify_bot.log`
4. Test OAuth flow end-to-end
5. Verify SSL certificate in `web_callback/certs/live/`

---

## Deployment Script Updates

**File:** `scripts/setup-vps-minimal.sh`

```bash
#!/bin/bash
# Minimal VPS setup - SSL handled by Python app

set -e

echo "?? rSpotify VPS Setup"

# Get VPS IP
VPS_IP=(hostname -I | awk '{print }')
echo "?? VPS IP: VPS_IP"

# Configure firewall
echo "?? Configuring firewall..."
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP (ACME)
ufw allow 443/tcp  # HTTPS (OAuth)
ufw --force enable

echo "? Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure DNS: rspotify.shhvang.space ? VPS_IP"
echo "2. Wait for DNS propagation (test with: dig rspotify.shhvang.space)"
echo "3. Deploy bot (SSL auto-provisions)"
```

---

## Common Issues & Solutions

### Issue: SSL Certificate Fails to Provision
**Cause:** DNS not propagated or ports not open  
**Solution:** 
- Verify DNS: `dig rspotify.shhvang.space +short`
- Check firewall: `ufw status`
- Test port 80: `curl http://rspotify.shhvang.space/.well-known/acme-challenge/test`

### Issue: "Invalid or expired authorization code"
**Cause:** Code already used or expired (10 min TTL)  
**Solution:** MongoDB TTL index working correctly, user needs to retry /login

### Issue: Telegram deep link doesn't open bot
**Cause:** BOT_USERNAME incorrect or bot not started  
**Solution:** Verify BOT_USERNAME in .env matches actual bot username

---

## Reference Links

**certbot Python API:**  
https://certbot.eff.org/docs/using.html#certbot-api

**aiohttp SSL Support:**  
https://docs.aiohttp.org/en/stable/web_advanced.html#ssl-certificate

**Telegram Deep Links:**  
https://core.telegram.org/api/links#bot-links

**Let's Encrypt Rate Limits:**  
https://letsencrypt.org/docs/rate-limits/

---

## Success Checklist

- [ ] DNS A record configured
- [ ] DNS propagation verified
- [ ] Dependencies updated (aiohttp, certbot)
- [ ] Environment variables added
- [ ] aiohttp web service implemented
- [ ] SSL automation working
- [ ] OAuth callback storing codes
- [ ] Bot deep link handler implemented
- [ ] MongoDB oauth_codes collection created
- [ ] Indexes created
- [ ] End-to-end OAuth flow tested
- [ ] SSL certificate auto-provisioned
- [ ] Documentation updated

---

**Ready to Start?** Begin with DNS configuration and dependency updates!

**Questions?** Refer to Sprint Change Proposal for detailed rationale and architecture decisions.

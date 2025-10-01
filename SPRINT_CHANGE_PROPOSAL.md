# 🔄 Sprint Change Proposal: OAuth Architecture Migration

**Date:** October 1, 2025  
**Story:** 1.4 - Spotify OAuth Authentication Flow  
**Change Type:** Technical Architecture Pivot  
**Status:** ✅ APPROVED

---

## 1. Executive Summary

**Issue:** SSL certificate configuration for custom domain (`rspotify.shhvang.space`) is causing deployment blockers with the manual Nginx + Certbot approach.

**Proposed Solution:** Migrate to self-contained Python architecture using aiohttp with integrated certbot library for automatic SSL management, adopting the proven spotipie OAuth flow pattern (auth code storage → Telegram redirect → bot retrieval).

**Impact:** Medium scope increase to Story 1.4, but eliminates infrastructure dependencies and solves SSL issues. No impact to future epics.

**Benefits:**
- ✅ Solves SSL certificate provisioning issues
- ✅ Eliminates Nginx dependency
- ✅ Fully self-contained Python deployment
- ✅ Cleaner separation of concerns (web service stores code, bot exchanges tokens)
- ✅ Uses battle-tested certbot library for ACME protocol
- ✅ More portable and easier to maintain

---

## 2. Change Trigger & Context

### Triggering Story
**Story 1.4: Spotify OAuth Authentication Flow** - Currently in implementation on feature branch `feature/story-1.4-spotify-oauth-authentication-flow`

### Core Problem
SSL certificate configuration for the custom domain using manual Nginx + Certbot setup is proving problematic in practice, creating deployment friction. The current approach requires:
- Manual DNS server configuration (BIND)
- Nginx reverse proxy setup
- Certbot SSL certificate management
- Complex 150-line setup script

### Root Cause
The original architecture assumed manual infrastructure would be straightforward, but SSL cert provisioning with custom domain on monthly-rotating VPS creates operational complexity.

### Discovery
Research revealed the spotipie-webserver project uses a cleaner OAuth pattern (store code → redirect to Telegram → bot retrieves code), and Python's certbot library can automate SSL without external dependencies.

---

## 3. Epic & Artifact Impact Analysis

### Epic 1 Impact
- **Story 1.4:** ✅ Can be completed with modified approach
- **Story 1.5:** ✅ No impact (depends on auth being working, which this delivers)
- **Story 1.6:** ✅ Already complete, Nginx AC was already deferred

### Future Epics (2, 3, 4)
✅ **No Impact** - No dependencies on Flask/Nginx infrastructure

### Affected Artifacts

| Artifact | Impact | Update Type |
|----------|--------|-------------|
| **PRD** (Story 1.1, 1.4, 1.6) | Medium | Replace Flask→aiohttp, remove Nginx, add SSL automation |
| **Architecture** (Sections 3, 5, 6, 7, 4) | Medium | Update tech stack, components, workflows, data models |
| **Story 1.4** | High | Rewrite tasks, add OAuth code retrieval, update Dev Notes |
| **Deployment Scripts** | Low | Simplify setup script (remove Nginx/Certbot steps) |
| **Code** (`web_callback/app.py`) | High | Rewrite Flask→aiohttp with certbot integration |
| **Requirements** | Low | Replace Flask with aiohttp + certbot libraries |

---

## 4. Architecture Changes

### 4.1 Tech Stack Changes

**REMOVED:**
- Flask 3.0 (web framework)
- Nginx (reverse proxy)
- Manual Certbot (SSL management)

**ADDED:**
- aiohttp 3.9 (async web framework)
- certbot 2.7 (Python library for ACME/SSL)
- acme 2.7 (ACME protocol implementation)

### 4.2 New OAuth Flow Pattern

**OLD PATTERN (Flask + State Validation):**
1. Bot generates state, sends auth URL
2. Spotify redirects to Flask
3. Flask validates state
4. Flask exchanges code for tokens immediately
5. Flask stores tokens in DB
6. Flask returns success page

**NEW PATTERN (aiohttp + Code Storage):**
1. Bot generates state, sends auth URL
2. Spotify redirects to aiohttp
3. aiohttp validates state
4. **aiohttp stores auth code in MongoDB**
5. **aiohttp redirects to Telegram deep link**
6. **Bot receives deep link, retrieves code**
7. **Bot exchanges code for tokens**
8. Bot stores tokens in DB
9. Bot confirms to user

**Benefits:**
- Cleaner separation of concerns
- Web service doesn't need Spotify client secret
- Bot maintains full control of auth state
- Natural error handling through Telegram

### 4.3 New Data Model

**Collection: oauth_codes**
`javascript
{
  "_id": ObjectId("..."),
  "telegram_id": 123456789,
  "auth_code": "AQD...",
  "state": "secure_random_string",
  "created_at": ISODate("..."),
  "expires_at": ISODate("...")  // 10 minutes TTL
}
`

**Indexes:**
- TTL index on `expires_at` (automatic cleanup)
- Index on `telegram_id` (fast lookups)

---

## 5. Implementation Changes

### 5.1 Updated Story 1.4 Tasks

**NEW Task 2: Implement aiohttp OAuth Callback Web Service with Certbot SSL**
- Create aiohttp application in `web_callback/app.py`
- Integrate certbot Python library for SSL automation
- Implement certificate provisioning on first run (ACME HTTP-01)
- Configure aiohttp on ports 80 (ACME) and 443 (HTTPS)
- Implement automatic certificate renewal (daily check, renew if <30 days)
- Implement `/.well-known/acme-challenge/{token}` handler
- Implement `/spotify/callback` route
- Validate state parameter
- Store auth code in `oauth_codes` collection
- Redirect to Telegram deep link: `https://t.me/BOT?start={code_id}`
- Comprehensive error handling and logging
- Integration tests

**UPDATED Task 3: Implement Spotify Authentication Service**
- Add `retrieve_auth_code()` function (fetch from `oauth_codes`)
- `exchange_code_for_tokens()` function
- `refresh_access_token()` function
- Clean up used auth codes after exchange
- All existing token management logic

**NEW Task 9b: Integrate OAuth Code Retrieval in Bot**
- Handle `/start` command with parameter parsing
- Extract `code_id` from `/start {code_id}`
- Retrieve auth code from `oauth_codes` collection
- Validate `telegram_id` matches (security check)
- Call `exchange_code_for_tokens()`
- Store encrypted tokens
- Delete auth code from collection
- Send success message
- Error handling (expired, mismatched, already used)
- Logging and unit tests

### 5.2 Updated Environment Variables

**NEW .env variables:**
`ash
# Existing
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=https://rspotify.shhvang.space/spotify/callback

# NEW
BOT_USERNAME=your_bot_username  # For Telegram deep links
DOMAIN=rspotify.shhvang.space   # For SSL certificate
CERTBOT_EMAIL=your@email.com    # For Let's Encrypt notifications
`

### 5.3 Updated Requirements

**requirements.txt changes:**
`diff
- Flask==3.0
+ aiohttp==3.9.1
+ certbot==2.7.4
+ acme==2.7.4
`

### 5.4 Simplified Deployment

**NEW: scripts/setup-vps-minimal.sh** (replaces 150-line setup-oauth-domain.sh)
`ash
#!/bin/bash
# Minimal VPS setup - SSL handled by Python app

VPS_IP=$'(hostname -I | awk '{print $'1}')'
DOMAIN="rspotify.shhvang.space"

# Configure firewall only
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP (ACME challenges)
ufw allow 443/tcp  # HTTPS (OAuth callbacks)
ufw --force enable

echo "Next steps:"
echo "1. Configure DNS: "'$'"DOMAIN → "'$'"VPS_IP"
echo "2. Wait for DNS propagation"
echo "3. Deploy bot (SSL auto-provisions)"
`

**No longer needed:**
- Nginx installation
- Nginx configuration
- Certbot installation
- Manual SSL commands
- DNS server setup (BIND)

---

## 6. Domain & SSL Setup

### Your Domain: shhvang.space

**What you need to do:**
1. **Add DNS A Record at your domain registrar:**
   `
   Type: A
   Name: rspotify
   Value: YOUR_VPS_IP (e.g., 178.128.48.130)
   TTL: 3600 (or default)
   `

2. **Wait for DNS propagation** (5-60 minutes)
   - Test with: `dig rspotify.shhvang.space +short`
   - Should return your VPS IP

3. **Deploy Python app** (SSL happens automatically)

**What you DON'T need:**
- ❌ Pre-existing SSL certificate
- ❌ Web hosting service
- ❌ Nginx or Apache
- ❌ Manual certbot commands
- ❌ Cron jobs for renewal

**The Python app handles everything:**
- Listens on port 80 for ACME challenges
- Responds to Let's Encrypt validation requests
- Downloads SSL certificate automatically
- Starts HTTPS server on port 443
- Auto-renews certificate every 60 days

---

## 7. Testing Strategy

### Unit Tests
- aiohttp route handlers (mocked requests)
- OAuth code storage/retrieval logic
- certbot integration (mocked ACME)
- Bot deep link parameter parsing
- Token exchange logic

### Integration Tests
- Full OAuth flow with test Spotify app
- SSL certificate provisioning (Let's Encrypt staging)
- Telegram deep link redirect
- Code expiry and cleanup (TTL index)

### Manual Testing
- Real OAuth flow with production Spotify app
- SSL certificate auto-renewal
- Error scenarios (expired codes, mismatched users)
- Certificate persistence across restarts

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| certbot integration complexity | Use official certbot Python library (well-documented), test with staging Let's Encrypt first |
| aiohttp SSL configuration | Follow aiohttp SSL docs, test with self-signed certs locally |
| OAuth flow changes | Fresh implementation in Story 1.4, no existing OAuth to break |
| DNS propagation delays | Document 5-60 minute wait, provide dig test command |
| Port 80/443 conflicts | VPS setup script ensures ports are open, check with netstat |

---

## 9. Rollback Plan

**If implementation fails:**

1. **Immediate:** Use ngrok for local testing (documented in `OAUTH_LOCAL_TESTING.md`)
2. **Short-term:** Revert to Flask + manual Nginx/Certbot (setup script available)
3. **Long-term:** Complete Story 1.4 with Flask, create new story for SSL automation

**Since Story 1.4 is on feature branch:**
- Clean rollback - abandon/reset branch
- No production impact
- No merged code to revert

---

## 10. Success Criteria

✅ Story 1.4 acceptance criteria met with new architecture  
✅ SSL certificates auto-provision on first run  
✅ OAuth flow completes end-to-end without manual infrastructure  
✅ Bot deployment simplified (no Nginx/Certbot steps)  
✅ All tests passing (unit + integration)  
✅ Documentation updated and accurate  
✅ VPS setup reduced from 150-line script to minimal firewall config  

---

## 11. Implementation Timeline

**Estimated Additional Effort:** +2-3 days to Story 1.4

**Recommended Order:**
1. Day 1: Update requirements, implement aiohttp skeleton, basic routing
2. Day 2: Integrate certbot SSL, implement ACME challenge handler, test SSL provisioning
3. Day 3: Complete OAuth callback with code storage, implement bot deep link handler
4. Day 4: Integration testing, deployment testing, documentation finalization

---

## 12. Final Recommendation

**Status:** ✅ **APPROVED AND PROCEEDING**

**Rationale:**
1. ✅ Solves immediate SSL certificate blocker
2. ✅ Simplifies deployment significantly (-90% infrastructure complexity)
3. ✅ Uses proven, battle-tested libraries (certbot, aiohttp)
4. ✅ Cleaner architecture with better separation of concerns
5. ✅ No impact to future epics
6. ✅ Perfect timing - Story 1.4 already in progress

**Long-term Value:**
- Eliminates ongoing SSL management overhead
- More portable solution (easy VPS migration)
- Easier to maintain and debug
- Better developer experience

---

**Change Proposal Prepared By:** Sarah (Product Owner Agent)  
**Date:** October 1, 2025  
**Approved By:** User (Product Owner / Technical Lead)  
**Status:** ✅ APPROVED - Implementation in progress

---

## Next Steps

1. ✅ Documentation updates completed
2. 🔄 Update Story 1.4 task list
3. 🔄 Implement aiohttp web service with certbot
4. 🔄 Implement bot deep link handler
5. 🔄 Integration testing
6. 🔄 Deployment testing on VPS

**Ready to begin implementation!** 🚀
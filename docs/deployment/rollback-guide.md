# Rollback Guide

Quick rollback procedures for rSpotify bot deployments.

## When to Rollback

Rollback when:
- New deployment breaks critical functionality
- Bot crashes repeatedly after deployment
- Database migrations fail
- OAuth flow stops working
- Owner verification needed before keeping changes

## Rollback Methods

### Method 1: GitHub Actions (Recommended)

Fastest method - uses existing workflow.

```bash
# 1. Find the last working commit
git log --oneline -10

# 2. Go to GitHub Actions
# URL: https://github.com/shhvang/rSpotify/actions

# 3. Select 'Rollback Deployment' workflow
# 4. Click 'Run workflow'
# 5. Enter commit hash or leave empty for previous commit
# 6. Select environment (staging/production)
# 7. Click 'Run workflow'
```

**Time:** ~3-5 minutes

### Method 2: Manual Rollback via Ansible

Use when GitHub Actions unavailable.

```bash
# 1. Checkout previous version locally
git checkout PREVIOUS_COMMIT_HASH

# 2. Run Ansible playbook manually
cd ansible

# For staging:
ansible-playbook -i staging_inventory setup.yml

# For production:
ansible-playbook -i production_inventory setup.yml
```

**Time:** ~5-7 minutes

### Method 3: SSH Direct Rollback

Emergency rollback directly on VPS.

```bash
# 1. SSH into VPS
ssh your_user@your_vps_ip

# 2. Navigate to app directory
cd /opt/rspotify-bot/src

# 3. Checkout previous version
sudo -u rspotify git log --oneline -10
sudo -u rspotify git checkout PREVIOUS_COMMIT

# 4. Restart bot
sudo supervisorctl restart rspotify-bot

# 5. Verify
sudo supervisorctl status rspotify-bot
tail -f /opt/rspotify-bot/logs/bot_output.log
```

**Time:** ~2-3 minutes (fastest for emergencies)

## Post-Rollback Verification

After rollback, verify:

- [ ] Bot process running: sudo supervisorctl status rspotify-bot
- [ ] Bot responds to /ping command
- [ ] No errors in logs: 	ail -f /opt/rspotify-bot/logs/bot_error.log
- [ ] OAuth callback working (test /login if applicable)
- [ ] Owner notification received (if applicable)

## Rollback Checklist

```markdown
[ ] Identify issue requiring rollback
[ ] Note current commit hash for reference
[ ] Choose rollback method based on urgency
[ ] Execute rollback procedure
[ ] Verify bot functionality
[ ] Test critical features
[ ] Notify team of rollback
[ ] Investigate root cause
[ ] Plan fix for next deployment
```

## Finding Previous Stable Version

```bash
# View recent commits
git log --oneline -20

# View commits with deployment tags
git log --tags --oneline

# View specific file history
git log --oneline -- rspotify_bot/bot.py

# Show commit details
git show COMMIT_HASH
```

## Testing After Rollback

```bash
# 1. Test basic functionality
# Telegram: Send /ping to bot

# 2. Check logs
ssh your_user@your_vps_ip
tail -f /opt/rspotify-bot/logs/bot_output.log

# 3. Test OAuth (if implemented)
# Telegram: Send /login to bot

# 4. Monitor for stability
# Wait 15-30 minutes, check logs periodically
```

## Preventing Need for Rollbacks

**Best Practices:**

1. **Always test on staging first**
   - Deploy to develop branch
   - Test thoroughly before production

2. **Use feature flags for major changes**
   - Disable risky features by default
   - Enable gradually after monitoring

3. **Monitor deployments closely**
   - Watch GitHub Actions logs
   - Check bot logs immediately after deploy
   - Test /ping within 5 minutes

4. **Keep good commit history**
   - Descriptive commit messages
   - Tag stable releases
   - Document breaking changes

5. **Have rollback plan ready**
   - Know last stable commit
   - Keep this guide handy
   - Practice rollback in staging

## Rollback vs Forward Fix

**Rollback when:**
- Critical functionality broken
- Data corruption risk
- Unknown root cause
- Time pressure (restore service fast)

**Forward fix when:**
- Minor bug with known fix
- Fix is simple (one-line change)
- Rollback would lose valuable data
- Already in middle of migration

## Emergency Contact

**If rollback fails:**
1. Check all three methods above
2. Review troubleshooting.md
3. Verify VPS is accessible
4. Check supervisor status
5. Review all logs carefully

## Rollback Time Targets

| Method | Target Time | Complexity |
|--------|-------------|------------|
| SSH Direct | < 3 minutes | Low |
| GitHub Actions | < 5 minutes | Low |
| Manual Ansible | < 7 minutes | Medium |

All methods should complete in under 5 minutes per requirements.

---
Story 1.6 - Deployment Operationalization

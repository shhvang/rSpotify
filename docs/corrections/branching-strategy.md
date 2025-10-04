# Branching Strategy & CI/CD Workflow

**Date:** October 4, 2025  
**Version:** 1.0  
**Status:** Active - Supersedes any previous branching documentation  
**Epic Milestone:** Epic 1 Complete

---

## Table of Contents

1. [Overview](#overview)
2. [Branch Structure](#branch-structure)
3. [Workflow](#workflow)
4. [CI/CD Configuration](#cicd-configuration)
5. [Deployment Processes](#deployment-processes)
6. [Testing Strategy](#testing-strategy)

---

## Overview

### Purpose
This document defines the official branching strategy and CI/CD workflow for the rSpotify bot project. This configuration enables safe feature development, comprehensive testing, and controlled production deployments.

### Key Principles
- **Production safety**: All features tested in `develop` before reaching `main`
- **Isolated development**: Feature branches for all new work
- **Automated testing**: CI/CD on both `develop` and `main` branches
- **Clear separation**: Test and production environments with distinct bot tokens and process labels

---

## Branch Structure

### 1. `main` (Production Branch)
- **Purpose**: Production-ready code only
- **Protection**: Protected branch, requires PR approval
- **Deployment**: Automatically deploys to production VPS
- **Bot Token**: Production bot token (`TELEGRAM_BOT_TOKEN`)
- **Process Label**: `rspotify`
- **CI/CD**: Full deployment pipeline on push

### 2. `develop` (Testing/Staging Branch)
- **Purpose**: Integration branch for completed features awaiting production release
- **Protection**: Protected branch, requires PR approval from feature branches
- **Deployment**: Automatically deploys to test environment
- **Bot Token**: Test bot token (`TELEGRAM_BOT_TOKEN_TEST`)
- **Process Label**: `rspotify_test`
- **CI/CD**: Full deployment pipeline mirroring production (different credentials)

### 3. Feature Branches
- **Naming Convention**: `feature/story-{number}-{brief-description}`
  - Example: `feature/story-1.5-custom-name-setup-management`
- **Base Branch**: Created from `develop`
- **Merge Target**: Merged back to `develop` via PR
- **Lifespan**: Deleted after successful merge
- **CI/CD**: Optional - can run tests on push

---

## Workflow

### Development Process

```
1. Create Feature Branch
   develop ─────> feature/story-X.Y-description
   
2. Implement Story
   - Follow Task 0: Read rules.md and docs/corrections/
   - Complete all story tasks
   - Write/update tests
   - Local testing
   
3. Merge to Develop
   feature/story-X.Y ─────> develop (via PR)
   └─> Triggers CI/CD for test environment
   └─> Automated testing on test bot
   
4. Testing in Develop
   - Test bot token used (rspotify_test process)
   - Validate all acceptance criteria
   - Monitor for issues
   
5. Release to Production
   develop ─────> main (via PR)
   └─> Triggers CI/CD for production environment
   └─> Deploys to production bot (rspotify process)
```

### Branch Flow Diagram

```
main (production)
  │
  │  ← merge when ready for production
  │
develop (testing)
  │
  ├─> feature/story-1.5-custom-name  ──┐
  │                                     │ merge when complete
  ├─> feature/story-1.6-deployment   ──┤
  │                                     │
  └──────────────────────────────────────┘
```

---

## CI/CD Configuration

### GitHub Actions Workflows

#### 1. Production Workflow (`.github/workflows/main.yml`)
- **Trigger**: Push to `main` branch
- **Environment**: Production
- **Secrets Required**:
  - `TELEGRAM_BOT_TOKEN` (production bot)
  - `SSH_PRIVATE_KEY`
  - `SSH_HOST`
  - `SSH_USER`
  - Other production secrets

#### 2. Test Workflow (`.github/workflows/develop.yml`)
- **Trigger**: Push to `develop` branch
- **Environment**: Test/Staging
- **Secrets Required**:
  - `TELEGRAM_BOT_TOKEN_TEST` (test bot) ⚠️ **MUST ADD TO SECRETS**
  - `SSH_PRIVATE_KEY_TEST` (or reuse production if same server)
  - `SSH_HOST_TEST` (or reuse production if same server)
  - `SSH_USER_TEST` (or reuse production if same server)
  - Other test environment secrets

### Workflow Differences

| Aspect | Production (`main`) | Test (`develop`) |
|--------|-------------------|------------------|
| Bot Token | `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN_TEST` |
| Process Name | `rspotify` | `rspotify_test` |
| PM2 Ecosystem | `ecosystem.config.js` | `ecosystem.test.config.js` |
| Branch | `main` | `develop` |
| Server | Production VPS | Test VPS (or same with different process) |

---

## Deployment Processes

### Process Labels

#### Production Process
```bash
# PM2 process name
pm2 start ecosystem.config.js --name rspotify

# Process listing shows
│ rspotify │ 0 │ fork │ 12345 │ online │
```

#### Test Process
```bash
# PM2 process name
pm2 start ecosystem.test.config.js --name rspotify_test

# Process listing shows
│ rspotify_test │ 0 │ fork │ 12346 │ online │
```

### Process Management

Both processes can run simultaneously on the same server if needed:
```bash
# List all processes
pm2 list

# Restart specific process
pm2 restart rspotify          # production
pm2 restart rspotify_test     # test

# View logs
pm2 logs rspotify            # production logs
pm2 logs rspotify_test       # test logs

# Monitor
pm2 monit
```

---

## Testing Strategy

### Before Merge to Develop
- ✅ All unit tests pass locally
- ✅ Code follows rules.md guidelines
- ✅ All story tasks completed
- ✅ Local testing successful

### After Merge to Develop
- ✅ CI/CD deploys to test environment
- ✅ Test bot (`rspotify_test`) running
- ✅ Manual validation of acceptance criteria
- ✅ Integration testing with test bot
- ✅ Monitor logs for errors

### Before Merge to Main
- ✅ All develop branch testing successful
- ✅ No critical bugs identified
- ✅ PR approved by reviewer
- ✅ Ready for production users

### After Merge to Main
- ✅ CI/CD deploys to production
- ✅ Production bot (`rspotify`) running
- ✅ Monitor production logs
- ✅ Verify critical commands working

---

## Epic 1 Status

**Epic 1: Core Bot Foundation & MVP Features** - ✅ **COMPLETE**

All stories in Epic 1 have been implemented and are production-ready:
- ✅ Story 1.1: Project Initialization & Core Bot Setup
- ✅ Story 1.2: Owner-Only Command & Notification Framework
- ✅ Story 1.3: Secure User Data Storage
- ✅ Story 1.4: Spotify OAuth Authentication Flow
- ✅ Story 1.5: Custom Name Setup & Management
- ✅ Story 1.6: Deployment & Operationalization Documentation
- ✅ Story 1.7: Motor Migration & Test Coverage Improvement

**Current Version**: v1.0.0 (tagged in main branch)

---

## Implementation Checklist

### Immediate Actions Required

- [ ] Create `develop` branch from current `main`
- [ ] Add `TELEGRAM_BOT_TOKEN_TEST` to GitHub Actions secrets
- [ ] Create `.github/workflows/develop.yml` (duplicate of main.yml with test credentials)
- [ ] Create `ecosystem.test.config.js` for test process configuration
- [ ] Update branch protection rules in GitHub:
  - [ ] Protect `main` branch (require PR approval)
  - [ ] Protect `develop` branch (require PR approval)
- [ ] Update all future stories to include Task 0 referencing rules.md and corrections/

### Documentation Updates Required

- [ ] Update PRD (single + sharded) with branching strategy
- [ ] Update Architecture (single + sharded) with CI/CD details
- [ ] Add Task 0 template to story template
- [ ] Update deployment documentation

---

## Related Documents

- [OAuth Implementation](./oauth-implementation.md) - OAuth v2.0 actual implementation
- [Development Rules](../rules.md) - Mandatory development guidelines
- PRD v2.1+ - Updated with branching strategy
- Architecture v2.0+ - Updated with CI/CD workflow

---

**Last Updated**: October 4, 2025  
**Next Review**: After Epic 2 planning

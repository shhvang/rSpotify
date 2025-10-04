# rSpotify Bot

**Version 1.1.0** - Last working perfectly code

A production-ready Telegram bot for Spotify OAuth authentication and user management with secure data storage, automated deployment, and comprehensive testing infrastructure.

## Project Status

- Production Ready - Fully tested and deployed
- 207 Tests Passing - Comprehensive unit and integration test coverage
- OAuth Flow Complete - Secure Spotify authentication with aiohttp callback service
- Async Architecture - Non-blocking I/O with proper thread-pool handling for MongoDB
- Supervisor-Managed - Production deployment with automated process supervision

## Features

### Spotify OAuth Authentication (Story 1.4)
- Secure OAuth 2.0 Flow with PKCE support
- aiohttp Callback Service - Standalone SSL-enabled web service for OAuth redirects
- Cross-Process State Management - MongoDB-backed temporary storage
- Token Exchange and Refresh - Automated token management with httpx AsyncClient
- Deep Link Integration - Seamless redirect back to Telegram bot
- Error Tracking - UUID-based error IDs for debugging

### Core Functionality
- Custom user display names (12 character limit)
- Spotify account connection via /login command
- MongoDB Atlas data persistence with async thread-pool handling
- Secure token storage with Fernet encryption
- Production-ready logging with structured error reporting

### Security and Privacy (Story 1.3)
- Encrypted Data Storage - Fernet symmetric encryption for OAuth tokens
- Input Sanitization - Protection against NoSQL injection and XSS attacks
- Data Privacy Compliance - GDPR-compliant data export and deletion
- Async-Safe Database Operations - All pymongo calls wrapped with asyncio.to_thread()
- User Commands: /logout, /exportdata
- Repository Pattern with comprehensive error handling

### Owner Administration (Story 1.2)
- Owner-only command framework with authorization middleware
- Maintenance mode for scheduled updates
- Bot usage statistics and analytics
- User blacklist/whitelist management
- Rate limiting protection
- Startup notifications with version tracking

### Infrastructure and Deployment
- Supervisor Process Management - Automated service supervision on VPS
- aiohttp OAuth Service - Separate SSL-enabled callback server
- MongoDB Backend - Cross-process temporary storage with TTL indexes
- Async Architecture - Non-blocking I/O with thread-pool for blocking operations
- Comprehensive Testing - 207 tests (unit + integration)
- Error Tracking - UUID-based error IDs and structured logging
- SSL Automation - Certbot integration for automatic certificate management

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB Atlas account
- Telegram Bot Token (from @BotFather)
- Spotify Developer Account

### Installation

1. Clone the repository:
   git clone https://github.com/shhvang/rSpotify.git
   cd rSpotify/rspotify-bot

2. Setup Python environment:
   python -m venv .venv
   .venv\\Scripts\\Activate.ps1  # Windows
   source .venv/bin/activate      # Linux/Mac
   pip install -e .[dev]

3. Configure environment:
   cp .env.example .env
   # Edit .env with your credentials

4. Run the bot:
   python rspotify.py

5. Run the OAuth callback service (separate terminal):
   cd web_callback
   python app.py

### Testing

pytest                    # All tests (207 tests)
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only
pytest --cov=rspotify_bot # Coverage report

## Project Structure

rspotify-bot/
 rspotify_bot/              # Main application package
    bot.py                 # Core bot implementation
    config.py              # Configuration management
    handlers/              # Command handlers
       owner_commands.py  # Admin commands
       user_commands.py   # User commands
    services/              # Core services
        auth.py            # Spotify OAuth token exchange
        database.py        # MongoDB operations (async-safe)
        encryption.py      # Token encryption (Fernet)
        middleware.py      # Temp storage, rate limiting
        notifications.py   # Owner notifications
        repository.py      # Data access layer
        validation.py      # Input sanitization
 web_callback/              # OAuth callback service
    app.py                 # aiohttp web service with SSL
 tests/                     # Test suite (207 tests)
    unit/                  # Unit tests
    integration/           # Integration tests
 docs/                      # Documentation
 scripts/                   # Utility scripts
 .env.example               # Environment template
 pyproject.toml             # Project config
 requirements.txt           # Python dependencies
 rspotify.py               # Entry point

## Environment Variables

### Core Configuration
- TELEGRAM_BOT_TOKEN: Telegram bot token from @BotFather
- OWNER_TELEGRAM_ID: Your Telegram user ID
- MONGODB_URI: MongoDB Atlas connection string

### Security
- ENCRYPTION_KEY: Fernet encryption key for OAuth tokens
- SPOTIFY_CLIENT_ID: Spotify application client ID
- SPOTIFY_CLIENT_SECRET: Spotify application client secret
- SPOTIFY_REDIRECT_URI: OAuth redirect URI

### Infrastructure
- ENVIRONMENT: development or production
- DEBUG: Enable debug logging (true/false)
- LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)

## Owner Commands

- /maintenance [on|off] - Toggle bot maintenance mode
- /stats [days] - View bot usage statistics
- /blacklist <user_id> [reason] - Block a user
- /whitelist <user_id> - Unblock a user

## User Commands

- /start - Initialize bot and create user profile
- /ping - Check bot status and database connection
- /help - Display available commands
- /login - Connect your Spotify account via OAuth
- /logout - Delete all your personal data (GDPR compliance)
- /exportdata - Export your personal data (GDPR compliance)

## Development

### Code Standards
- Language: Python 3.11+
- Formatter: Black (88 char line length)
- Linter: Flake8
- Type Checker: MyPy (strict mode)
- Testing: pytest with asyncio support
- Coverage: Minimum 80% required

### Critical Development Rules
1. Async MongoDB Operations: Always wrap pymongo calls with asyncio.to_thread()
2. PyMongo Database Checks: Use is None / is not None (never truthy checks)
3. httpx Response Methods: .json() and .text() are synchronous (do NOT await)
4. Supervisor Deployment: Never manually start bot processes; use supervisor only
5. Process Management: Always check for duplicate processes before deploy

### Testing Strategy
- Unit Tests: Fast, isolated component testing
- Integration Tests: Service integration validation
- E2E Tests: Complete OAuth workflow validation
- 207 tests total - all passing

## Architecture

### Tech Stack
- Bot Framework: python-telegram-bot 21.0.1 (async)
- OAuth Service: aiohttp 3.9.1 (async web service)
- Database: MongoDB Atlas with pymongo 4.6.1
- HTTP Client: httpx >=0.27.0 (async)
- Security: cryptography 41.0.7 (Fernet encryption)
- SSL: certbot 2.7.4 (automated certificate management)
- Process Manager: supervisord (VPS deployment)

### Design Patterns
- Repository Pattern: Clean data access abstraction
- Middleware Pattern: Rate limiting, blacklist, OAuth state
- Service Layer: Encryption, validation, notifications
- Async/Thread Pool: Non-blocking I/O with thread execution for blocking ops

### Database Collections
- users: Telegram ID, custom name, encrypted tokens, timestamps
- temporary_storage: OAuth state with TTL (5 min expiry)
- usage_logs: Command tracking for analytics
- blacklist: Blocked users with reason tracking

## Deployment

### VPS Deployment (Production)
Services are managed by supervisor on VPS:
1. rspotify-bot - Main Telegram bot (port 8443)
2. rspotify-oauth - OAuth callback service (port 443, SSL)

### Supervisor Management
sudo supervisorctl status
sudo supervisorctl restart rspotify-bot rspotify-oauth
sudo supervisorctl tail -f rspotify-bot

### Deployment Process
1. SSH into VPS
2. Pull latest code: cd /opt/rspotify-bot/repo && git pull
3. Restart services: sudo supervisorctl restart rspotify-bot rspotify-oauth
4. Monitor logs for errors

### Important Notes
- Never manually start bot processes - always use supervisor
- Check for duplicate processes before deploy
- Only supervisor-managed processes should be running
- Logs are in /opt/rspotify-bot/logs/

## Testing and Quality

### Test Coverage
- 207 tests passing (as of v1.1.0)
- Unit tests: encryption, repository, validation, OAuth flows
- Integration tests: database, owner auth, end-to-end OAuth
- Coverage target: >80%

### Run Tests
pytest
pytest --cov=rspotify_bot --cov-report=html
pytest tests/unit/test_story_1_4_oauth_e2e.py

## Contributing

1. Fork the repository
2. Create a feature branch: git checkout -b feature/story-x.y-description
3. Add tests for new functionality
4. Run linting: black . && flake8 && mypy rspotify_bot
5. Ensure all tests pass: pytest
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: https://github.com/shhvang/rSpotify/issues
- Documentation: See /docs directory
- Stories: See /docs/stories for detailed user stories

## Version History

### v1.1.0 (Current - Last Working Perfectly)
- Complete OAuth 2.0 flow with aiohttp callback service
- Async-safe MongoDB operations with thread-pool
- UUID-based error tracking
- 207 tests passing
- Production deployment with supervisor
- SSL automation with certbot

### v1.2.0 (In Development)
- Spotify playback controls
- Track search and recommendations
- Queue management

Built with love for seamless Spotify + Telegram integration

# rSpotify Bot

A Telegram bot for Spotify track sharing and recommendations with automated deployment infrastructure.

## Features

### 🎵 Core Functionality
- Spotify track sharing and recommendations
- Telegram bot integration with slash commands
- MongoDB Atlas data persistence
- Secure OAuth integration with DuckDNS

### � Web App Bots (Optional)
Includes two additional lightweight bots that can be deployed alongside rSpotify:

- **Better Than Very Bot** (@BetterThanVeryBot) - Suggests stronger single-word replacements for "very + word" phrases
- **Perfect Circle Bot** (@PerfectCircleBot) - Fun game to test your circle drawing accuracy

These bots run as independent processes but share the same deployment infrastructure.

### �🔒 Security & Privacy (Story 1.3)
- **Encrypted Data Storage**: Fernet symmetric encryption for OAuth tokens
- **Input Sanitization**: Protection against NoSQL injection and XSS attacks
- **Data Privacy Compliance**: GDPR-compliant data export and deletion
- **User Commands**:
  - `/logout` - Delete all personal data and revoke access
  - `/exportdata` - Export your personal data
- **Repository Pattern**: Clean data access layer with comprehensive error handling
- **Secure Token Management**: Encrypted storage with key rotation capabilities

### 👑 Owner Administration (Story 1.2)
- Owner-only command framework with authorization middleware
- Maintenance mode for scheduled updates
- Bot usage statistics and analytics
- User blacklist/whitelist management
- Rate limiting protection

### 🔄 Infrastructure
- Automated deployment with monthly server rotation
- Comprehensive testing suite (Unit/Integration/E2E)
- Database connection pooling and health monitoring
- Notification system for bot status and critical errors

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB Atlas account
- Telegram Bot Token
- Spotify Developer Account

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rspotify-bot/rspotify-bot.git
   cd rspotify-bot
   ```

2. **Setup Python environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
   pip install -e .[dev]
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the bot:**
   ```bash
   python rspotify.py
   ```

### Testing

Run the test suite:
```bash
pytest                    # All tests
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only
pytest --cov=rspotify_bot # Coverage report
```

### Deployment

Deploy using Ansible:
```bash
cd ansible
ansible-playbook setup.yml -i inventory
```

## Project Structure

```
rspotify-bot/
├── ansible/              # Deployment automation
├── docs/                 # Project documentation
├── rspotify_bot/         # Main application package
│   ├── assets/           # Static assets
│   ├── handlers/         # Telegram command handlers
│   │   ├── owner_commands.py   # Admin commands (maintenance, stats, blacklist)
│   │   └── user_commands.py    # Privacy commands (logout, exportdata)
│   └── services/         # Core services
│       ├── auth.py              # Owner authorization
│       ├── database.py          # MongoDB operations
│       ├── encryption.py        # Token encryption (Fernet)
│       ├── middleware.py        # Rate limiting, blacklist
│       ├── notifications.py     # Owner notifications
│       ├── repository.py        # Data access layer
│       └── validation.py        # Input sanitization
├── tests/                # Test suite (126 tests)
│   ├── unit/             # Unit tests (70%)
│   │   ├── test_encryption.py      # 18 encryption tests
│   │   ├── test_repository.py      # 27 repository tests
│   │   └── test_validation.py      # 46 validation tests
│   ├── integration/      # Integration tests (20%)
│   │   ├── test_database_integration.py  # 21 MongoDB tests
│   │   └── test_owner_auth.py            # 16 owner auth tests
│   └── e2e/              # End-to-end tests (10%)
├── web_callback/         # OAuth callback service
├── .env.example          # Environment template
├── pyproject.toml        # Python project configuration
└── rspotify.py          # Application entry point
```

## Environment Variables

Required environment variables (see `.env.example`):

### Core Configuration
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from @BotFather
- `OWNER_TELEGRAM_ID`: Your Telegram user ID (for owner commands)
- `MONGODB_URI`: MongoDB Atlas connection string

### Security (Story 1.3)
- `ENCRYPTION_KEY`: Fernet encryption key for OAuth tokens
  - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  - **CRITICAL**: Keep this secret and never commit to version control

### Spotify Integration (Future)
- `SPOTIFY_CLIENT_ID`: Spotify application client ID
- `SPOTIFY_CLIENT_SECRET`: Spotify application client secret

### Infrastructure
- `DUCKDNS_TOKEN`: DuckDNS update token
- `DUCKDNS_DOMAIN`: Your DuckDNS domain name
- `ENVIRONMENT`: `development` or `production` (default: `development`)
- `DEBUG`: Enable debug logging (`true`/`false`, default: `false`)
- `LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## Owner Setup

### Getting Your Telegram ID

To use owner-only commands, you need to set your Telegram user ID:

1. **Start a chat with @userinfobot** on Telegram
2. **Send any message** to get your user ID
3. **Copy the user ID number** (e.g., `123456789`)
4. **Add it to your `.env` file:**
   ```bash
   OWNER_TELEGRAM_ID=123456789
   ```

### Owner Commands

Once configured, you have access to these administrative commands:

- `/maintenance [on|off]` - Toggle bot maintenance mode
- `/stats [days]` - View bot usage statistics (default: 7 days)  
- `/blacklist <user_id> [reason]` - Block a user from using the bot
- `/whitelist <user_id>` - Remove a user from the blacklist

## User Commands

Available to all users:

- `/start` - Initialize bot and create user profile
- `/ping` - Check bot status and database connection
- `/help` - Display available commands
- `/logout` - **Delete all your personal data** (GDPR compliance)
- `/exportdata` - **Export your personal data** (GDPR compliance)

### Privacy Features (Story 1.3)

The bot provides comprehensive data privacy controls:

- **Data Encryption**: All OAuth tokens stored with Fernet symmetric encryption
- **Data Deletion**: `/logout` command permanently removes:
  - User profile
  - Encrypted Spotify tokens
  - Usage history and logs
  - Cached search results
- **Data Export**: `/exportdata` command provides:
  - Complete user profile data
  - Account creation and update timestamps
  - Spotify connection status (tokens excluded for security)
- **Security**: Input sanitization prevents injection attacks

### Features for Owners

- **Startup Notifications**: Receive a message when the bot starts/restarts
- **Error Reports**: Get detailed error reports via pastebin links
- **Maintenance Mode**: Disable bot for regular users while keeping owner access
- **Usage Analytics**: Comprehensive statistics on bot usage and user activity
- **Rate Limit Bypass**: Owner commands are not subject to rate limiting
- **User Management**: Block/unblock users as needed

### Security Notes

- Keep your `OWNER_TELEGRAM_ID` secure and private
- **CRITICAL**: Never commit `ENCRYPTION_KEY` to version control
- Generate unique encryption keys for each environment (dev/prod)
- Rotate encryption keys periodically for enhanced security
- Only the configured owner can access administrative functions
- Error reports may contain sensitive information - pastebin links expire automatically
- Maintenance mode messages are user-friendly and don't reveal system details
- All user inputs are sanitized to prevent NoSQL injection and XSS attacks

## Development

### Code Standards

- **Language**: Python 3.11+
- **Formatter**: Black (88 char line length)
- **Linter**: Flake8 (E203, W503, E501 ignored for Black)
- **Type Checker**: MyPy (strict mode with full import validation)
- **Testing**: pytest with asyncio support
- **Coverage**: Minimum 80% required

### Linting Commands

```bash
# Format code with Black
python -m black .

# Run Flake8 linting
python -m flake8 rspotify_bot --max-line-length=88 --extend-ignore=E203,W503,E501

# Run MyPy type checking (strict)
python -m mypy rspotify_bot

# Run all linting at once
python -m black . && python -m flake8 rspotify_bot --max-line-length=88 --extend-ignore=E203,W503,E501 && python -m mypy rspotify_bot
```

### Git Workflow

1. Create feature branch from `main`
2. Implement changes with tests
3. Run full test suite + linting
4. Create pull request
5. Automated CI/CD deployment

### Testing Strategy

- **70% Unit Tests**: Fast, isolated component testing (91 tests for Story 1.3)
- **20% Integration Tests**: Service integration validation (21 MongoDB tests)
- **10% E2E Tests**: Complete user workflow validation
- **Minimum 80% code coverage** required
- **All 126 Story 1.3 tests passing**

## Architecture

### Tech Stack
- **Bot Framework**: python-telegram-bot 21.0.1 (async)
- **Database**: MongoDB Atlas with pymongo 4.6.1
- **Security**: cryptography 41.0.7 (Fernet encryption)
- **API Client**: httpx >=0.27.0 for Spotify integration
- **Web Service**: Flask 3.0 for OAuth callbacks
- **Image Processing**: Pillow 10.1.0 (thread-safe)
- **Infrastructure**: Ansible 2.15 with monthly rotation

### Design Patterns
- **Repository Pattern**: Clean data access abstraction
- **Middleware Pattern**: Rate limiting, blacklist, owner auth
- **Decorator Pattern**: Input validation, command protection
- **Service Layer**: Encryption, validation, notifications

### Database Schema (Story 1.3)
- **users**: Telegram ID, custom name, encrypted tokens, timestamps
- **search_cache**: Query results with TTL (30 days auto-cleanup)
- **usage_logs**: Command tracking for analytics
- **blacklist**: Blocked users with reason tracking

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/story-x.y-description`)
3. Add tests for new functionality (maintain 80% coverage)
4. Run linting: `black . && flake8 && mypy rspotify_bot`
5. Ensure all tests pass: `pytest`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [rspotify-bot/issues](https://github.com/rspotify-bot/rspotify-bot/issues)
- Documentation: See `/docs` directory
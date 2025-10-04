#!/usr/bin/env python3
"""
rSpotify Test Bot Runner

This script runs the rSpotify bot in test mode using:
- Test bot token (7870675278:AAGjTXvPOHkMpJggMwK8QIVG5yADzA55Q88)
- Separate test database (rspotify_bot_test)
- .env.test configuration file

Usage:
    python rspotify_test.py

Environment:
    Loads .env.test instead of .env to avoid conflicts with production bot
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Set environment file to .env.test BEFORE importing anything else
os.environ['ENV_FILE'] = '.env.test'

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import after setting environment
from rspotify_bot.bot import RSpotifyBot
from rspotify_bot.config import Config, setup_logging, validate_environment

logger = logging.getLogger(__name__)


async def main():
    """Run the rSpotify test bot"""
    
    # Setup logging first
    setup_logging()
    
    # Verify we're using test environment
    if Config.ENVIRONMENT != 'test':
        print(f"ERROR: Environment is not 'test'. Check .env.test file.")
        print(f"Current environment: {Config.ENVIRONMENT}")
        sys.exit(1)
    
    # Verify we're using test database
    if not Config.MONGODB_DATABASE.endswith('_test'):
        print(f"ERROR: Database name doesn't end with '_test'. Safety check failed.")
        print(f"Current database: {Config.MONGODB_DATABASE}")
        sys.exit(1)
    
    # Display test bot info
    print("=" * 80)
    print("TEST BOT Starting...")
    print("=" * 80)
    print(f"Environment: {Config.ENVIRONMENT}")
    print(f"Database: {Config.MONGODB_DATABASE}")
    print(f"Debug Mode: {Config.DEBUG}")
    print(f"Test Bot Token: ...{Config.TELEGRAM_BOT_TOKEN[-20:]}")
    print("=" * 80)
    print("")
    print("WARNING: This is a TEST bot - not for production use!")
    print("")
    print("Commands to test:")
    print("  /ping       - Test basic functionality + response timings")
    print("  /help       - Show all available commands")
    print("  /logs       - Test new log retrieval (owner only)")
    print("  /errorlogs  - Test error log retrieval (owner only)")
    print("  /stats      - Test statistics command (owner only)")
    print("")
    print("Press Ctrl+C to stop the test bot")
    print("=" * 80)
    print("")
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        sys.exit(1)
    
    # Initialize and run bot
    try:
        bot = RSpotifyBot(Config.TELEGRAM_BOT_TOKEN)
        await bot.start()
    except KeyboardInterrupt:
        print("\nTest bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test bot failed to start: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Test bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest bot stopped.")
        sys.exit(0)

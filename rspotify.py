#!/usr/bin/env python3
"""
rSpotify Bot - Main Entry Point

A Telegram bot for Spotify track sharing and recommendations.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rspotify_bot.config import setup_logging, validate_environment, config
from rspotify_bot.bot import RSpotifyBot

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main application entry point."""
    print("🎵 Starting rSpotify Bot...")

    # Setup logging
    setup_logging()
    logger.info("rSpotify Bot starting up...")

    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        sys.exit(1)

    # Create and start bot
    try:
        bot = RSpotifyBot(config.TELEGRAM_BOT_TOKEN)
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("rSpotify Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

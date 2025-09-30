"""
Owner authorization service for rSpotify Bot.
Provides decorators and middleware for owner-only commands.
"""

import logging
from functools import wraps
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from ..config import Config

logger = logging.getLogger(__name__)


def owner_only(func: Callable) -> Callable:
    """
    Decorator to restrict command access to bot owner only.

    Args:
        func: The command handler function to wrap

    Returns:
        Wrapped function that checks owner authorization
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """
        Wrapper function that checks if user is the bot owner.

        Args:
            update: Telegram update object
            context: Bot context

        Returns:
            Result of wrapped function if authorized, None otherwise
        """
        user = update.effective_user
        owner_id = Config.OWNER_TELEGRAM_ID

        if not update.message:
            logger.error("No message in update")
            return None

        if not owner_id:
            logger.error("OWNER_TELEGRAM_ID not configured")
            await update.message.reply_html(
                "<b>⚠️ Configuration Error</b>\n"
                "<i>Owner authentication not properly configured.</i>"
            )
            return None

        if not user or str(user.id) != owner_id:
            logger.warning(
                f"Unauthorized access attempt from user {user.id if user else 'Unknown'}"
            )
            await update.message.reply_html(
                "<b>🚫 Access Denied</b>\n"
                "<i>This command is restricted to the bot owner only.</i>"
            )
            return None

        logger.info(f"Owner command access granted to user {user.id}")
        return await func(update, context)

    return wrapper


async def is_owner(user_id: int) -> bool:
    """
    Check if a user ID matches the configured owner ID.

    Args:
        user_id: Telegram user ID to check

    Returns:
        True if user is owner, False otherwise
    """
    owner_id = Config.OWNER_TELEGRAM_ID
    if not owner_id:
        logger.error("OWNER_TELEGRAM_ID not configured")
        return False

    return str(user_id) == owner_id


def get_owner_id() -> str:
    """
    Get the configured owner Telegram ID.

    Returns:
        Owner Telegram ID as string, empty if not configured
    """
    return Config.OWNER_TELEGRAM_ID

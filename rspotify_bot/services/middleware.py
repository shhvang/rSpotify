"""
Middleware services for rSpotify Bot.
Provides rate limiting, blacklist checking, and other protective measures.
"""

import logging
from typing import Callable, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from .database import DatabaseService
from .auth import is_owner

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Middleware for rate limiting user commands."""

    def __init__(self, database_service: DatabaseService):
        """
        Initialize rate limit middleware.

        Args:
            database_service: Database service instance
        """
        self.db = database_service
        self.rate_limits: Dict[str, Dict[str, Any]] = {
            "default": {"max_calls": 10, "window_minutes": 1},
            "search": {"max_calls": 5, "window_minutes": 1},
            "playlist": {"max_calls": 3, "window_minutes": 2},
            "nowplaying": {"max_calls": 15, "window_minutes": 1},
        }

    async def check_rate_limit(self, update: Update, command: str) -> bool:
        """
        Check if user has exceeded rate limit.

        Args:
            update: Telegram update object
            command: Command being executed

        Returns:
            True if within rate limit, False if exceeded
        """
        user = update.effective_user
        if not user:
            return True

        # Owner bypasses rate limits
        if await is_owner(user.id):
            return True

        # Get rate limit settings for command
        limit_config = self.rate_limits.get(command, self.rate_limits["default"])

        # Check rate limit
        within_limit = await self.db.check_rate_limit(
            user.id, command, limit_config["max_calls"], limit_config["window_minutes"]
        )

        if not within_limit:
            # Record violation
            await self.db.record_rate_limit_violation(user.id, command)

            # Send rate limit message
            await self._send_rate_limit_message(update, command, limit_config)

            logger.warning(
                f"Rate limit exceeded for user {user.id} on command {command}"
            )

        return within_limit

    async def _send_rate_limit_message(
        self, update: Update, command: str, config: Dict[str, Any]
    ) -> None:
        """
        Send rate limit exceeded message to user.

        Args:
            update: Telegram update object
            command: Command that was rate limited
            config: Rate limit configuration
        """
        try:
            window_text = (
                "minute"
                if config["window_minutes"] == 1
                else f"{config['window_minutes']} minutes"
            )

            message = (
                f"<b>⏱ Rate Limit Exceeded</b>\n\n"
                f"<b>Command:</b> <code>/{command}</code>\n"
                f"<b>Limit:</b> {config['max_calls']} uses per {window_text}\n\n"
                f"<i>Please wait a moment before trying again.</i>"
            )

            if not update.message:
                return

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Failed to send rate limit message: {e}")


class BlacklistMiddleware:
    """Middleware for checking blacklisted users."""

    def __init__(self, database_service: DatabaseService):
        """
        Initialize blacklist middleware.

        Args:
            database_service: Database service instance
        """
        self.db = database_service

    async def check_blacklist(self, update: Update) -> bool:
        """
        Check if user is blacklisted.

        Args:
            update: Telegram update object

        Returns:
            True if user is allowed, False if blacklisted
        """
        user = update.effective_user
        if not user:
            return True

        # Owner cannot be blacklisted
        if await is_owner(user.id):
            return True

        is_blocked = await self.db.is_blacklisted(user.id)

        if is_blocked:
            await self._send_blacklist_message(update)
            logger.info(f"Blocked blacklisted user {user.id}")

        return not is_blocked

    async def _send_blacklist_message(self, update: Update) -> None:
        """
        Send blacklist message to blocked user.

        Args:
            update: Telegram update object
        """
        try:
            if not update.message:
                return

            message = (
                "<b>🚫 Access Restricted</b>\n\n"
                "<i>Your access to this bot has been restricted.</i>\n\n"
                "<b>Reason:</b> <i>Policy violation</i>\n"
                "<b>Contact:</b> <i>Bot administrator</i>"
            )

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Failed to send blacklist message: {e}")


class ProtectionMiddleware:
    """Combined middleware for all protection measures."""

    def __init__(self, database_service: DatabaseService):
        """
        Initialize protection middleware.

        Args:
            database_service: Database service instance
        """
        self.db = database_service
        self.rate_limiter = RateLimitMiddleware(database_service)
        self.blacklist_checker = BlacklistMiddleware(database_service)

    async def process_update(self, update: Update, command: str) -> bool:
        """
        Process update through all protection layers.

        Args:
            update: Telegram update object
            command: Command being executed

        Returns:
            True if update should be processed, False if blocked
        """
        # Check blacklist first
        if not await self.blacklist_checker.check_blacklist(update):
            return False

        # Check rate limits
        if not await self.rate_limiter.check_rate_limit(update, command):
            return False

        # Log successful usage
        user = update.effective_user
        if user:
            await self.db.log_usage(user.id, command)
            await self.db.update_user_activity(user.id)

        return True


def create_protection_wrapper(database_service: DatabaseService) -> Callable:
    """
    Create a protection wrapper function.

    Args:
        database_service: Database service instance

    Returns:
        Protection wrapper function
    """
    protection = ProtectionMiddleware(database_service)

    def protection_wrapper(command_name: str) -> Callable:
        """
        Decorator to add protection to command handlers.

        Args:
            command_name: Name of the command being protected
        """

        def decorator(func: Callable) -> Callable:
            async def wrapper(
                update: Update, context: ContextTypes.DEFAULT_TYPE
            ) -> Any:
                # Apply protection checks
                if not await protection.process_update(update, command_name):
                    return  # Blocked by protection middleware

                # Execute original handler
                return await func(update, context)

            return wrapper

        return decorator

    return protection_wrapper

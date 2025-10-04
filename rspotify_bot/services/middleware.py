"""
Middleware services for rSpotify Bot.
Provides rate limiting, blacklist checking, authentication, and other protective measures.
"""

import logging
import secrets
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from functools import wraps

from pymongo.database import Database as MongoDatabase
from pymongo.errors import PyMongoError
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


class TemporaryStorage:
    """Thread-safe temporary storage for OAuth state parameters with TTL.
    
    Supports both in-memory storage (for single process) and MongoDB backend
    (for cross-process sharing between bot and web callback).
    """

    def __init__(self):
        """Initialize temporary storage."""
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._database: Optional[MongoDatabase] = None  # MongoDB database for cross-process storage
        self._use_mongodb = False  # Flag to enable MongoDB backend

    async def start_cleanup_task(self):
        """Start background cleanup task for expired entries."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Temporary storage cleanup task started")

    async def _cleanup_loop(self):
        """Background task to clean up expired entries every 60 seconds."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Temporary storage cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_expired(self):
        """Remove expired entries from storage."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_keys = [
                key
                for key, data in self._storage.items()
                if data["expires_at"] < now
            ]
            for key in expired_keys:
                del self._storage[key]
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired state(s)")

    async def set(self, key: str, value: Any, expiry_seconds: int = 300) -> None:
        """
        Store a value with expiry time.

        Args:
            key: Storage key
            value: Value to store
            expiry_seconds: Time to live in seconds (default: 300 = 5 minutes)
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
        
        if self._use_mongodb and self._database is not None:
            # Store in MongoDB for cross-process sharing
            try:
                self._database.temp_storage.replace_one(
                    {"key": key},
                    {
                        "key": key,
                        "value": value,
                        "expires_at": expires_at
                    },
                    upsert=True
                )
                logger.debug(f"Stored key '{key}' in MongoDB with {expiry_seconds}s TTL")
            except Exception as e:
                logger.error(f"Failed to store in MongoDB: {e}")
                raise
        else:
            # Store in memory
            async with self._lock:
                self._storage[key] = {"value": value, "expires_at": expires_at}
                logger.debug(f"Stored key '{key}' in memory with {expiry_seconds}s TTL")

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by key.

        Args:
            key: Storage key

        Returns:
            Stored value if found and not expired, None otherwise
        """
        if self._use_mongodb and self._database is not None:
            # Retrieve from MongoDB
            try:
                data = self._database.temp_storage.find_one({"key": key})
                if not data:
                    logger.debug(f"Key '{key}' not found in MongoDB")
                    return None

                # Check expiry
                if data["expires_at"] < datetime.now(timezone.utc):
                    self._database.temp_storage.delete_one({"key": key})
                    logger.debug(f"Key '{key}' expired and removed from MongoDB")
                    return None

                logger.debug(f"Retrieved key '{key}' from MongoDB")
                return data["value"]
            except Exception as e:
                logger.error(f"Failed to retrieve from MongoDB: {e}")
                return None
        else:
            # Retrieve from memory
            async with self._lock:
                data = self._storage.get(key)
                if not data:
                    return None

                # Check expiry
                if data["expires_at"] < datetime.now(timezone.utc):
                    del self._storage[key]
                    logger.debug(f"Key '{key}' expired and removed")
                    return None

                return data["value"]

    async def delete(self, key: str) -> bool:
        """
        Delete a key from storage.

        Args:
            key: Storage key

        Returns:
            True if key was deleted, False if not found
        """
        if self._use_mongodb and self._database is not None:
            # Delete from MongoDB
            try:
                result = self._database.temp_storage.delete_one({"key": key})
                deleted = result.deleted_count > 0
                if deleted:
                    logger.debug(f"Deleted key '{key}' from MongoDB")
                return deleted
            except Exception as e:
                logger.error(f"Failed to delete from MongoDB: {e}")
                return False
        else:
            # Delete from memory
            async with self._lock:
                if key in self._storage:
                    del self._storage[key]
                    logger.debug(f"Deleted key '{key}' from memory")
                    return True
                return False

    async def stop_cleanup_task(self):
        """Stop the cleanup background task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Temporary storage cleanup task stopped")

    def configure_backend(self, database: Optional[MongoDatabase]) -> None:
        """Configure the storage backend for cross-process sharing."""

        if database is None:
            if self._use_mongodb:
                logger.warning(
                    "MongoDB backend unavailable; falling back to in-memory temporary storage"
                )
            self._database = None
            self._use_mongodb = False
            return

        self._database = database
        if not self._use_mongodb:
            logger.info("Temporary storage configured with MongoDB backend")
        self._use_mongodb = True

        try:
            database.temp_storage.create_index("expires_at", expireAfterSeconds=0)
            logger.debug("TTL index ensured on temp_storage collection")
        except PyMongoError as exc:
            logger.warning("Failed to ensure temp_storage TTL index: %s", exc)

    @property
    def uses_mongodb(self) -> bool:
        """Return True when the storage is backed by MongoDB."""

        return self._use_mongodb


# Global temporary storage instance
_temporary_storage: Optional[TemporaryStorage] = None


def get_temporary_storage() -> TemporaryStorage:
    """
    Get or create the global temporary storage instance.

    Returns:
        TemporaryStorage instance
    """
    global _temporary_storage
    if _temporary_storage is None:
        _temporary_storage = TemporaryStorage()
    return _temporary_storage


def require_spotify_auth(func: Callable) -> Callable:
    """
    Decorator to require Spotify authentication for command handlers.

    Checks if user has valid Spotify tokens and automatically refreshes if needed.

    Args:
        func: The command handler function to wrap

    Returns:
        Wrapped function that checks authentication
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """
        Wrapper function that checks Spotify authentication.

        Args:
            update: Telegram update object
            context: Bot context

        Returns:
            Result of wrapped function if authenticated, None otherwise
        """
        from .repository import UserRepository, RepositoryError
        from .database import DatabaseService
        from typing import cast

        user = update.effective_user

        if not user:
            logger.error("No user in update")
            return None

        if not update.message:
            logger.error("No message in update")
            return None

        telegram_id = user.id

        try:
            # Get database service
            db_service = cast(DatabaseService, context.bot_data.get("db_service"))
            if db_service is None or db_service.database is None:
                logger.error("Database service unavailable")
                await update.message.reply_html(
                    "<b>❌ Error</b>\n\n"
                    "Service temporarily unavailable. Please try again later."
                )
                return None

            # Get user from database
            user_repo = UserRepository(db_service.database)
            user_data = await user_repo.get_user(telegram_id)

            if not user_data:
                await update.message.reply_html(
                    "<b>🔐 Authentication Required</b>\n\n"
                    "You need to connect your Spotify account first.\n"
                    "Use /login to get started."
                )
                logger.info(f"User {telegram_id} not authenticated - no user record")
                return None

            # Check if user has Spotify tokens
            spotify_data = user_data.get("spotify")
            if not spotify_data or not spotify_data.get("access_token"):
                await update.message.reply_html(
                    "<b>🔐 Authentication Required</b>\n\n"
                    "You need to connect your Spotify account first.\n"
                    "Use /login to get started."
                )
                logger.info(f"User {telegram_id} not authenticated - no tokens")
                return None

            # Check token expiration and refresh if needed
            expires_at = spotify_data.get("expires_at")
            if expires_at:
                # Check if token is expired or will expire in next 5 minutes
                if expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
                    logger.info(
                        f"Token expired or expiring soon for user {telegram_id}, attempting refresh"
                    )

                    # Import here to avoid circular dependency
                    from .auth import SpotifyAuthService

                    auth_service = SpotifyAuthService()

                    try:
                        # Refresh token
                        new_tokens = await auth_service.refresh_access_token(
                            spotify_data["refresh_token"]
                        )

                        # Update tokens in database
                        await user_repo.update_spotify_tokens(
                            telegram_id,
                            new_tokens["access_token"],
                            new_tokens["refresh_token"],
                            new_tokens["expires_at"],
                        )

                        logger.info(f"Successfully refreshed token for user {telegram_id}")

                    except Exception as e:
                        logger.error(f"Failed to refresh token for user {telegram_id}: {e}")
                        await update.message.reply_html(
                            "<b>❌ Authentication Error</b>\n\n"
                            "Your Spotify session has expired and could not be refreshed.\n"
                            "Please use /login to reconnect your account."
                        )
                        return None

            # Authentication successful, proceed with command
            logger.debug(f"User {telegram_id} authenticated successfully")
            return await func(update, context)

        except RepositoryError as e:
            logger.error(f"Repository error in auth middleware: {e}")
            await update.message.reply_html(
                "<b>❌ Error</b>\n\n"
                f"Database error: {e}\nPlease try again later."
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error in auth middleware: {e}")
            await update.message.reply_html(
                "<b>❌ Error</b>\n\n"
                "An unexpected error occurred. Please try again later."
            )
            return None

    return wrapper

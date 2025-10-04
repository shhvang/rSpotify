"""
Database service for rSpotify Bot.
Handles MongoDB Atlas connection and operations.
"""

import logging
from typing import Optional, Dict, Any, cast
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from pymongo import IndexModel, ASCENDING, DESCENDING

from ..config import config

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service class for database operations with MongoDB Atlas."""

    def __init__(self) -> None:
        """Initialize database service."""
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database[Any]] = None
        self._connection_validated = False

    async def connect(self) -> bool:
        """
        Connect to MongoDB Atlas and validate connection.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            logger.info("Connecting to MongoDB Atlas...")

            # For basic implementation, we'll simulate connection
            # In production, replace with actual MongoDB connection
            if not config.MONGODB_URI or config.MONGODB_URI == "":
                logger.error("MongoDB URI not configured; database features are unavailable")
                self._connection_validated = False
                return False

            # Create client with connection pooling
            self.client = MongoClient(
                config.MONGODB_URI,
                maxPoolSize=10,
                minPoolSize=1,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=5000,
                serverSelectionTimeoutMS=10000,
            )

            # Get database
            self.database = self.client[config.MONGODB_DATABASE]

            # Validate connection
            self.client.admin.command("ping")
            self._connection_validated = True

            logger.info(f"Connected to MongoDB database: {config.MONGODB_DATABASE}")

            # Setup indexes (synchronous version)
            self._setup_indexes_sync()

            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            bool: True if connection is healthy, False otherwise.
        """
        if not self._connection_validated:
            return False

        if not self.client:
            return False

        try:
            # For sync client, wrap in executor
            self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False

    def _setup_indexes_sync(self) -> None:
        """Setup database indexes for optimal performance (synchronous version)."""
        if self.database is None:
            return

        try:
            # Users collection indexes
            users_indexes = [
                IndexModel([("telegram_id", ASCENDING)], unique=True),
                IndexModel([("created_at", DESCENDING)]),
                IndexModel([("last_active", DESCENDING)]),
            ]
            self.database.users.create_indexes(users_indexes)

            # Search cache collection indexes
            cache_indexes = [
                IndexModel([("query_string", ASCENDING)], unique=True),
                IndexModel(
                    [("created_at", ASCENDING)], expireAfterSeconds=2592000
                ),  # 30 days TTL
            ]
            self.database.search_cache.create_indexes(cache_indexes)

            # Usage logs collection indexes
            logs_indexes = [
                IndexModel([("telegram_id", ASCENDING)]),
                IndexModel([("timestamp", DESCENDING)]),
                IndexModel([("command", ASCENDING)]),
                IndexModel(
                    [("timestamp", ASCENDING)], expireAfterSeconds=7776000
                ),  # 90 days TTL
            ]
            self.database.usage_logs.create_indexes(logs_indexes)

            # Blacklist collection indexes
            blacklist_indexes = [
                IndexModel([("telegram_id", ASCENDING)], unique=True),
                IndexModel([("blocked_at", DESCENDING)]),
            ]
            self.database.blacklist.create_indexes(blacklist_indexes)

            # Rate limiting collection indexes
            ratelimit_indexes = [
                IndexModel([("user_id", ASCENDING)]),
                IndexModel(
                    [("window_start", ASCENDING)], expireAfterSeconds=3600
                ),  # 1 hour TTL
            ]
            self.database.rate_limits.create_indexes(ratelimit_indexes)

            # OAuth codes collection indexes (Story 1.4)
            oauth_codes_indexes = [
                IndexModel([("telegram_id", ASCENDING)]),
                IndexModel([("state", ASCENDING)]),
                IndexModel(
                    [("expires_at", ASCENDING)], expireAfterSeconds=0
                ),  # TTL index - documents auto-delete when expires_at < now
            ]
            self.database.oauth_codes.create_indexes(oauth_codes_indexes)

            logger.info("Database indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create database indexes: {e}")

    # Users Collection Methods

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User document or None if not found
        """
        if self.database is None:
            return None

        try:
            return self.database.users.find_one({"telegram_id": telegram_id})
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            return None

    async def create_user(
        self, telegram_id: int, custom_name: Optional[str] = None
    ) -> bool:
        """
        Create a new user record.

        Args:
            telegram_id: Telegram user ID
            custom_name: Optional custom display name

        Returns:
            True if user created successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            user_doc = {
                "telegram_id": telegram_id,
                "custom_name": custom_name,
                "spotify_tokens": None,  # Will be encrypted when added
                "created_at": datetime.now(timezone.utc),
                "last_active": datetime.now(timezone.utc),
                "preferences": {
                    "notifications": True,
                    "public_playlists": False,
                },
            }

            self.database.users.insert_one(user_doc)
            logger.info(f"Created user record for {telegram_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating user {telegram_id}: {e}")
            return False

    async def update_user_activity(self, telegram_id: int) -> bool:
        """
        Update user's last activity timestamp.

        Args:
            telegram_id: Telegram user ID

        Returns:
            True if updated successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            result = self.database.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"last_active": datetime.now(timezone.utc)}},
            )
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating activity for user {telegram_id}: {e}")
            return False

    # Search Cache Methods

    async def get_cached_search(self, query: str) -> Optional[str]:
        """
        Get cached Spotify track ID for search query.

        Args:
            query: Search query string

        Returns:
            Cached Spotify track ID or None if not found/expired
        """
        if self.database is None:
            return None

        try:
            result = self.database.search_cache.find_one({"query_string": query})
            if result:
                logger.debug(f"Cache hit for query: {query}")
                return cast(Optional[str], result.get("spotify_track_id"))
            return None

        except Exception as e:
            logger.error(f"Error getting cached search for '{query}': {e}")
            return None

    async def cache_search_result(self, query: str, spotify_track_id: str) -> bool:
        """
        Cache search result for future use.

        Args:
            query: Search query string
            spotify_track_id: Spotify track ID to cache

        Returns:
            True if cached successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            cache_doc = {
                "query_string": query,
                "spotify_track_id": spotify_track_id,
                "created_at": datetime.now(timezone.utc),
            }

            # Upsert to handle duplicate queries
            self.database.search_cache.replace_one(
                {"query_string": query}, cache_doc, upsert=True
            )

            logger.debug(f"Cached search result for query: {query}")
            return True

        except Exception as e:
            logger.error(f"Error caching search result for '{query}': {e}")
            return False

    # Usage Logs Methods

    async def log_usage(
        self,
        telegram_id: int,
        command: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log user command usage.

        Args:
            telegram_id: Telegram user ID
            command: Command name that was executed
            extra_data: Optional additional data to log

        Returns:
            True if logged successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            log_doc = {
                "telegram_id": telegram_id,
                "command": command,
                "timestamp": datetime.now(timezone.utc),
            }

            if extra_data:
                log_doc.update(extra_data)

            self.database.usage_logs.insert_one(log_doc)
            logger.debug(f"Logged usage: {telegram_id} -> {command}")
            return True

        except Exception as e:
            logger.error(f"Error logging usage for {telegram_id}: {e}")
            return False

    async def get_user_stats(self, telegram_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get user usage statistics for the specified period.

        Args:
            telegram_id: Telegram user ID
            days: Number of days to look back

        Returns:
            Dictionary with usage statistics
        """
        if self.database is None:
            return {}

        try:
            since_date = datetime.now(timezone.utc) - timedelta(days=days)

            pipeline = [
                {
                    "$match": {
                        "telegram_id": telegram_id,
                        "timestamp": {"$gte": since_date},
                    }
                },
                {"$group": {"_id": "$command", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]

            results = list(
                self.database.usage_logs.aggregate(cast(list[dict[str, Any]], pipeline))
            )

            stats = {
                "period_days": days,
                "total_commands": sum(result["count"] for result in results),
                "command_breakdown": {
                    result["_id"]: result["count"] for result in results
                },
                "most_used_command": results[0]["_id"] if results else None,
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting user stats for {telegram_id}: {e}")
            return {}

    # Database Management Methods

    async def cleanup_expired_data(self) -> Dict[str, int]:
        """
        Clean up expired cache and log entries.

        Returns:
            Dictionary with cleanup statistics
        """
        if self.database is None:
            return {}

        try:
            # MongoDB TTL indexes handle automatic cleanup,
            # but we can provide manual cleanup for monitoring

            # Count expired cache entries (older than 30 days)
            cache_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            expired_cache = self.database.search_cache.count_documents(
                {"created_at": {"$lt": cache_cutoff}}
            )

            # Count expired logs (older than 90 days)
            logs_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            expired_logs = self.database.usage_logs.count_documents(
                {"timestamp": {"$lt": logs_cutoff}}
            )

            # Manual deletion if needed (TTL indexes should handle this)
            if expired_cache > 0:
                cache_result = self.database.search_cache.delete_many(
                    {"created_at": {"$lt": cache_cutoff}}
                )
                logger.info(
                    f"Cleaned up {cache_result.deleted_count} expired cache entries"
                )

            if expired_logs > 0:
                logs_result = self.database.usage_logs.delete_many(
                    {"timestamp": {"$lt": logs_cutoff}}
                )
                logger.info(
                    f"Cleaned up {logs_result.deleted_count} expired log entries"
                )

            return {
                "expired_cache_entries": expired_cache,
                "expired_log_entries": expired_logs,
            }

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {}

    # Blacklist Management Methods

    async def add_to_blacklist(
        self, telegram_id: int, reason: str = "abuse", blocked_by: Optional[str] = None
    ) -> bool:
        """
        Add user to blacklist.

        Args:
            telegram_id: Telegram user ID to blacklist
            reason: Reason for blacklisting
            blocked_by: ID of admin who added the ban

        Returns:
            True if added successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            blacklist_doc = {
                "telegram_id": telegram_id,
                "reason": reason,
                "blocked_at": datetime.now(timezone.utc),
                "blocked_by": blocked_by,
            }

            self.database.blacklist.replace_one(
                {"telegram_id": telegram_id}, blacklist_doc, upsert=True
            )

            logger.info(f"Added user {telegram_id} to blacklist (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Error adding user {telegram_id} to blacklist: {e}")
            return False

    async def remove_from_blacklist(self, telegram_id: int) -> bool:
        """
        Remove user from blacklist.

        Args:
            telegram_id: Telegram user ID to remove from blacklist

        Returns:
            True if removed successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            result = self.database.blacklist.delete_one({"telegram_id": telegram_id})
            success = result.deleted_count > 0

            if success:
                logger.info(f"Removed user {telegram_id} from blacklist")
            else:
                logger.warning(f"User {telegram_id} was not found in blacklist")

            return success

        except Exception as e:
            logger.error(f"Error removing user {telegram_id} from blacklist: {e}")
            return False

    async def is_blacklisted(self, telegram_id: int) -> bool:
        """
        Check if user is blacklisted.

        Args:
            telegram_id: Telegram user ID to check

        Returns:
            True if user is blacklisted, False otherwise
        """
        if self.database is None:
            return False

        try:
            result = self.database.blacklist.find_one({"telegram_id": telegram_id})
            is_blocked = result is not None

            if is_blocked:
                logger.debug(f"User {telegram_id} is blacklisted")

            return is_blocked

        except Exception as e:
            logger.error(f"Error checking blacklist status for user {telegram_id}: {e}")
            return False

    async def get_blacklist_info(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get blacklist information for a user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Blacklist document or None if not blacklisted
        """
        if self.database is None:
            return None

        try:
            return self.database.blacklist.find_one({"telegram_id": telegram_id})
        except Exception as e:
            logger.error(f"Error getting blacklist info for user {telegram_id}: {e}")
            return None

    # Statistics Methods

    async def get_bot_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive bot statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with bot statistics
        """
        if self.database is None:
            return {}

        try:
            since_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Total users
            total_users = self.database.users.count_documents({})

            # Active users (used bot in specified period)
            active_users = self.database.usage_logs.distinct(
                "telegram_id", {"timestamp": {"$gte": since_date}}
            )
            active_user_count = len(active_users)

            # New users in period
            new_users = self.database.users.count_documents(
                {"created_at": {"$gte": since_date}}
            )

            # Command usage statistics
            command_pipeline = [
                {"$match": {"timestamp": {"$gte": since_date}}},
                {
                    "$group": {
                        "_id": "$command",
                        "count": {"$sum": 1},
                        "unique_users": {"$addToSet": "$telegram_id"},
                    }
                },
                {"$addFields": {"unique_user_count": {"$size": "$unique_users"}}},
                {"$project": {"unique_users": 0}},  # Remove the array field
                {"$sort": {"count": -1}},
            ]

            command_stats = list(
                self.database.usage_logs.aggregate(
                    cast(list[dict[str, Any]], command_pipeline)
                )
            )

            # Total commands executed
            total_commands = sum(stat["count"] for stat in command_stats)

            # Daily usage trend
            daily_pipeline = [
                {"$match": {"timestamp": {"$gte": since_date}}},
                {
                    "$group": {
                        "_id": {
                            "year": {"$year": "$timestamp"},
                            "month": {"$month": "$timestamp"},
                            "day": {"$dayOfMonth": "$timestamp"},
                        },
                        "commands": {"$sum": 1},
                        "unique_users": {"$addToSet": "$telegram_id"},
                    }
                },
                {"$addFields": {"users": {"$size": "$unique_users"}}},
                {"$project": {"unique_users": 0}},
                {"$sort": {"_id": 1}},
            ]

            daily_stats = list(
                self.database.usage_logs.aggregate(
                    cast(list[dict[str, Any]], daily_pipeline)
                )
            )

            # Blacklisted users count
            blacklisted_count = self.database.blacklist.count_documents({})

            return {
                "period_days": days,
                "users": {
                    "total": total_users,
                    "active": active_user_count,
                    "new": new_users,
                    "blacklisted": blacklisted_count,
                },
                "commands": {
                    "total": total_commands,
                    "breakdown": command_stats,
                    "most_popular": command_stats[0]["_id"] if command_stats else None,
                },
                "daily_usage": daily_stats,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting bot statistics: {e}")
            return {}

    # Rate Limiting Methods

    async def check_rate_limit(
        self, user_id: int, command: str, max_calls: int = 10, window_minutes: int = 1
    ) -> bool:
        """
        Check if user has exceeded rate limit for command.

        Args:
            user_id: Telegram user ID
            command: Command name
            max_calls: Maximum calls allowed in window
            window_minutes: Time window in minutes

        Returns:
            True if within rate limit, False if exceeded
        """
        if self.database is None:
            return True  # Allow if database unavailable

        try:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(minutes=window_minutes)

            # Count recent calls
            recent_calls = self.database.usage_logs.count_documents(
                {
                    "telegram_id": user_id,
                    "command": command,
                    "timestamp": {"$gte": window_start},
                }
            )

            return recent_calls < max_calls

        except Exception as e:
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            return True  # Allow on error

    async def record_rate_limit_violation(self, user_id: int, command: str) -> bool:
        """
        Record a rate limit violation.

        Args:
            user_id: Telegram user ID
            command: Command that was rate limited

        Returns:
            True if recorded successfully, False otherwise
        """
        if self.database is None:
            return False

        try:
            violation_doc = {
                "user_id": user_id,
                "command": command,
                "timestamp": datetime.now(timezone.utc),
                "type": "rate_limit_exceeded",
            }

            self.database.rate_limit_violations.insert_one(violation_doc)
            logger.warning(
                f"Rate limit violation recorded for user {user_id} on command {command}"
            )
            return True

        except Exception as e:
            logger.error(f"Error recording rate limit violation: {e}")
            return False

    async def check_connection(self) -> bool:
        """
        Check database connection status.

        Returns:
            True if connected and healthy, False otherwise
        """
        if not self._connection_validated:
            return False

        return await self.health_check()

"""
Repository layer for rSpotify Bot database operations.
Implements repository pattern for clean data access abstraction.
"""

import logging
from typing import Optional, Dict, Any, cast
from datetime import datetime, timedelta
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from .encryption import get_encryption_service
from .validation import validate_telegram_id, sanitize_custom_name, ValidationError

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Exception raised for repository-level errors."""

    pass


class UserRepository:
    """Repository for user data operations."""

    def __init__(self, database: Database):
        """
        Initialize user repository.

        Args:
            database: MongoDB database instance
        """
        self.db = database
        self.collection = database.users
        self.encryption_service = get_encryption_service()

    async def create_user(
        self,
        telegram_id: int,
        custom_name: Optional[str] = None,
        spotify_tokens: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Create a new user record with encrypted tokens.

        Args:
            telegram_id: Telegram user ID
            custom_name: Optional custom display name
            spotify_tokens: Optional dict with access_token and refresh_token

        Returns:
            True if user created successfully

        Raises:
            RepositoryError: If user creation fails
        """
        try:
            # Validate inputs
            telegram_id = validate_telegram_id(telegram_id)
            if custom_name:
                custom_name = sanitize_custom_name(custom_name)

            # Encrypt Spotify tokens if provided
            encrypted_spotify = None
            if spotify_tokens:
                encrypted_spotify = {
                    "access_token": self.encryption_service.encrypt_token(
                        spotify_tokens["access_token"]
                    ),
                    "refresh_token": self.encryption_service.encrypt_token(
                        spotify_tokens["refresh_token"]
                    ),
                    "expires_at": spotify_tokens.get("expires_at"),
                }

            # Create user document
            user_doc = {
                "telegram_id": telegram_id,
                "custom_name": custom_name,
                "spotify": encrypted_spotify,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            self.collection.insert_one(user_doc)
            logger.info(f"Created user record for telegram_id: {telegram_id}")
            return True

        except DuplicateKeyError:
            logger.warning(f"User {telegram_id} already exists")
            raise RepositoryError(f"User with telegram_id {telegram_id} already exists")
        except ValidationError as e:
            logger.error(f"Validation error creating user: {e}")
            raise RepositoryError(f"Invalid user data: {e}")
        except Exception as e:
            logger.error(f"Error creating user {telegram_id}: {e}")
            raise RepositoryError(f"Failed to create user: {e}")

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram ID with decrypted tokens.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User document with decrypted tokens, or None if not found

        Raises:
            RepositoryError: If retrieval fails
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)

            user = self.collection.find_one({"telegram_id": telegram_id})

            if not user:
                return None

            # Decrypt Spotify tokens if present
            if user.get("spotify") and user["spotify"].get("access_token"):
                try:
                    user["spotify"]["access_token"] = (
                        self.encryption_service.decrypt_token(
                            user["spotify"]["access_token"]
                        )
                    )
                    user["spotify"]["refresh_token"] = (
                        self.encryption_service.decrypt_token(
                            user["spotify"]["refresh_token"]
                        )
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt tokens for user {telegram_id}: {e}"
                    )
                    # Return user without tokens rather than failing completely
                    user["spotify"] = None

            return cast(dict[str, Any], user)

        except ValidationError as e:
            logger.error(f"Validation error getting user: {e}")
            raise RepositoryError(f"Invalid telegram_id: {e}")
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            raise RepositoryError(f"Failed to get user: {e}")

    async def update_user(self, telegram_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update user record.

        Args:
            telegram_id: Telegram user ID
            updates: Dictionary of fields to update

        Returns:
            True if updated successfully

        Raises:
            RepositoryError: If update fails
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)

            # Validate and sanitize updates
            if "custom_name" in updates and updates["custom_name"]:
                updates["custom_name"] = sanitize_custom_name(updates["custom_name"])

            # Encrypt Spotify tokens if being updated
            if "spotify" in updates and updates["spotify"]:
                tokens = updates["spotify"]
                if "access_token" in tokens:
                    updates["spotify"]["access_token"] = (
                        self.encryption_service.encrypt_token(tokens["access_token"])
                    )
                if "refresh_token" in tokens:
                    updates["spotify"]["refresh_token"] = (
                        self.encryption_service.encrypt_token(tokens["refresh_token"])
                    )

            # Add updated_at timestamp
            updates["updated_at"] = datetime.utcnow()

            # Use upsert to create user if doesn't exist
            result = self.collection.update_one(
                {"telegram_id": telegram_id}, 
                {"$set": updates},
                upsert=True
            )

            logger.info(f"Updated user {telegram_id} (matched: {result.matched_count}, modified: {result.modified_count}, upserted: {result.upserted_id})")
            return True

        except ValidationError as e:
            logger.error(f"Validation error updating user: {e}")
            raise RepositoryError(f"Invalid update data: {e}")
        except Exception as e:
            logger.error(f"Error updating user {telegram_id}: {e}")
            raise RepositoryError(f"Failed to update user: {e}")

    async def delete_user(self, telegram_id: int) -> bool:
        """
        Delete user and all associated data (cascade delete).

        Args:
            telegram_id: Telegram user ID

        Returns:
            True if deleted successfully

        Raises:
            RepositoryError: If deletion fails
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)

            # Delete user record
            user_result = self.collection.delete_one({"telegram_id": telegram_id})

            if user_result.deleted_count == 0:
                logger.warning(
                    f"No user found to delete for telegram_id: {telegram_id}"
                )
                return False

            # Cascade delete from other collections
            self.db.usage_logs.delete_many({"telegram_id": telegram_id})

            logger.info(f"Deleted user {telegram_id} and all associated data")
            return True

        except ValidationError as e:
            logger.error(f"Validation error deleting user: {e}")
            raise RepositoryError(f"Invalid telegram_id: {e}")
        except Exception as e:
            logger.error(f"Error deleting user {telegram_id}: {e}")
            raise RepositoryError(f"Failed to delete user: {e}")

    async def user_exists(self, telegram_id: int) -> bool:
        """
        Check if user exists.

        Args:
            telegram_id: Telegram user ID

        Returns:
            True if user exists, False otherwise
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)
            return self.collection.count_documents({"telegram_id": telegram_id}) > 0
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False

    async def update_spotify_tokens(
        self,
        telegram_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """
        Update user's Spotify tokens.

        Args:
            telegram_id: Telegram user ID
            access_token: New Spotify access token
            refresh_token: New Spotify refresh token
            expires_at: Token expiration datetime

        Returns:
            True if updated successfully
        """
        spotify_data: dict[str, Any] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
        if expires_at:
            spotify_data["expires_at"] = expires_at

        return await self.update_user(telegram_id, {"spotify": spotify_data})

    async def get_user_count(self) -> int:
        """
        Get total number of users.

        Returns:
            Total user count
        """
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            return 0


class SearchCacheRepository:
    """Repository for search cache operations."""

    def __init__(self, database: Database):
        """
        Initialize search cache repository.

        Args:
            database: MongoDB database instance
        """
        self.db = database
        self.collection = database.search_cache

    async def get_cached_result(self, query: str) -> Optional[str]:
        """
        Get cached search result.

        Args:
            query: Search query string

        Returns:
            Cached Spotify track ID or None
        """
        try:
            result = self.collection.find_one({"query_string": query})
            if result:
                logger.debug(f"Cache hit for query: {query}")
                return cast(Optional[str], result.get("spotify_track_id"))
            return None
        except Exception as e:
            logger.error(f"Error getting cached result: {e}")
            return None

    async def cache_result(self, query: str, spotify_track_id: str) -> bool:
        """
        Cache search result with TTL.

        Args:
            query: Search query string
            spotify_track_id: Spotify track ID to cache

        Returns:
            True if cached successfully
        """
        try:
            cache_doc = {
                "query_string": query,
                "spotify_track_id": spotify_track_id,
                "created_at": datetime.utcnow(),
            }

            self.collection.replace_one({"query_string": query}, cache_doc, upsert=True)

            logger.debug(f"Cached result for query: {query}")
            return True
        except Exception as e:
            logger.error(f"Error caching result: {e}")
            return False

    async def clear_cache(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries deleted
        """
        try:
            result = self.collection.delete_many({})
            logger.info(f"Cleared {result.deleted_count} cache entries")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0


class UsageLogsRepository:
    """Repository for usage logs operations."""

    def __init__(self, database: Database):
        """
        Initialize usage logs repository.

        Args:
            database: MongoDB database instance
        """
        self.db = database
        self.collection = database.usage_logs

    async def log_command(
        self,
        telegram_id: int,
        command: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log user command usage.

        Args:
            telegram_id: Telegram user ID
            command: Command name
            extra_data: Optional additional data

        Returns:
            True if logged successfully
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)

            log_doc = {
                "telegram_id": telegram_id,
                "command": command,
                "timestamp": datetime.utcnow(),
            }

            if extra_data:
                log_doc.update(extra_data)

            self.collection.insert_one(log_doc)
            logger.debug(f"Logged command: {telegram_id} -> {command}")
            return True

        except Exception as e:
            logger.error(f"Error logging command: {e}")
            return False

    async def get_user_stats(self, telegram_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get user usage statistics.

        Args:
            telegram_id: Telegram user ID
            days: Number of days to look back

        Returns:
            Dictionary with usage statistics
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)
            since_date = datetime.utcnow() - timedelta(days=days)

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
                self.collection.aggregate(cast(list[dict[str, Any]], pipeline))
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
            logger.error(f"Error getting user stats: {e}")
            return {}

    async def delete_user_logs(self, telegram_id: int) -> int:
        """
        Delete all logs for a specific user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Number of logs deleted
        """
        try:
            telegram_id = validate_telegram_id(telegram_id)
            result = self.collection.delete_many({"telegram_id": telegram_id})
            logger.info(f"Deleted {result.deleted_count} logs for user {telegram_id}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting user logs: {e}")
            return 0

"""
Unit tests for repository layer.
Tests data access operations with mocked database.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from cryptography.fernet import Fernet

from rspotify_bot.services.repository import (
    UserRepository,
    SearchCacheRepository,
    UsageLogsRepository,
    RepositoryError,
)
from rspotify_bot.services.encryption import EncryptionService
from rspotify_bot.services.validation import ValidationError


class TestUserRepository:
    """Test suite for UserRepository."""

    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        db = Mock()
        db.users = Mock()
        db.search_cache = Mock()
        db.usage_logs = Mock()
        return db

    @pytest.fixture
    def encryption_key(self):
        """Generate test encryption key."""
        return Fernet.generate_key().decode("utf-8")

    @pytest.fixture
    def mock_encryption_service(self, encryption_key):
        """Create mock encryption service."""
        return EncryptionService(encryption_key=encryption_key)

    @pytest.fixture
    def user_repository(self, mock_database, mock_encryption_service):
        """Create UserRepository with mocked dependencies."""
        with patch(
            "rspotify_bot.services.repository.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            return UserRepository(mock_database)

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_repository, mock_database):
        """Test successful user creation."""
        telegram_id = 123456789
        custom_name = "Test User"

        mock_database.users.insert_one = Mock()

        result = await user_repository.create_user(telegram_id, custom_name)

        assert result is True
        mock_database.users.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_with_tokens(self, user_repository, mock_database):
        """Test user creation with Spotify tokens."""
        telegram_id = 123456789
        tokens = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": datetime.utcnow(),
        }

        mock_database.users.insert_one = Mock()

        result = await user_repository.create_user(telegram_id, spotify_tokens=tokens)

        assert result is True
        # Verify insert was called
        call_args = mock_database.users.insert_one.call_args[0][0]
        assert call_args["telegram_id"] == telegram_id
        assert "spotify" in call_args
        # Tokens should be encrypted (different from original)
        assert call_args["spotify"]["access_token"] != tokens["access_token"]

    @pytest.mark.asyncio
    async def test_create_user_invalid_telegram_id(self, user_repository):
        """Test user creation fails with invalid telegram_id."""
        with pytest.raises(RepositoryError, match="Invalid user data"):
            await user_repository.create_user(-123)

    @pytest.mark.asyncio
    async def test_create_user_duplicate(self, user_repository, mock_database):
        """Test user creation fails with duplicate telegram_id."""
        from pymongo.errors import DuplicateKeyError

        mock_database.users.insert_one = Mock(
            side_effect=DuplicateKeyError("duplicate")
        )

        with pytest.raises(RepositoryError, match="already exists"):
            await user_repository.create_user(123456789)

    @pytest.mark.asyncio
    async def test_get_user_success(
        self, user_repository, mock_database, mock_encryption_service
    ):
        """Test successful user retrieval."""
        telegram_id = 123456789

        # Create encrypted tokens
        encrypted_access = mock_encryption_service.encrypt_token("access_token")
        encrypted_refresh = mock_encryption_service.encrypt_token("refresh_token")

        mock_user = {
            "telegram_id": telegram_id,
            "custom_name": "Test",
            "spotify": {
                "access_token": encrypted_access,
                "refresh_token": encrypted_refresh,
            },
            "created_at": datetime.utcnow(),
        }

        mock_database.users.find_one = Mock(return_value=mock_user)

        result = await user_repository.get_user(telegram_id)

        assert result is not None
        assert result["telegram_id"] == telegram_id
        # Tokens should be decrypted
        assert result["spotify"]["access_token"] == "access_token"
        assert result["spotify"]["refresh_token"] == "refresh_token"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_repository, mock_database):
        """Test user retrieval returns None when not found."""
        mock_database.users.find_one = Mock(return_value=None)

        result = await user_repository.get_user(123456789)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_decryption_fails(self, user_repository, mock_database):
        """Test user retrieval handles decryption failures gracefully."""
        mock_user = {
            "telegram_id": 123456789,
            "spotify": {
                "access_token": "invalid_encrypted_data",
                "refresh_token": "invalid_encrypted_data",
            },
        }

        mock_database.users.find_one = Mock(return_value=mock_user)

        result = await user_repository.get_user(123456789)

        # Should return user but with None spotify data
        assert result is not None
        assert result["spotify"] is None

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_repository, mock_database):
        """Test successful user update."""
        telegram_id = 123456789
        updates = {"custom_name": "Updated Name"}

        mock_result = Mock()
        mock_result.modified_count = 1
        mock_database.users.update_one = Mock(return_value=mock_result)

        result = await user_repository.update_user(telegram_id, updates)

        assert result is True
        mock_database.users.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_repository, mock_database):
        """Test update returns False when user not found."""
        mock_result = Mock()
        mock_result.modified_count = 0
        mock_database.users.update_one = Mock(return_value=mock_result)

        result = await user_repository.update_user(123456789, {"custom_name": "Test"})

        assert result is False

    @pytest.mark.asyncio
    async def test_update_user_encrypts_tokens(self, user_repository, mock_database):
        """Test user update encrypts Spotify tokens."""
        telegram_id = 123456789
        updates = {
            "spotify": {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
            }
        }

        mock_result = Mock()
        mock_result.modified_count = 1
        mock_database.users.update_one = Mock(return_value=mock_result)

        result = await user_repository.update_user(telegram_id, updates)

        assert result is True
        # Verify tokens were encrypted
        call_args = mock_database.users.update_one.call_args[0][1]["$set"]
        assert call_args["spotify"]["access_token"] != "new_access"

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_repository, mock_database):
        """Test successful user deletion."""
        telegram_id = 123456789

        mock_result = Mock()
        mock_result.deleted_count = 1
        mock_database.users.delete_one = Mock(return_value=mock_result)
        mock_database.search_cache.delete_many = Mock()
        mock_database.usage_logs.delete_many = Mock()

        result = await user_repository.delete_user(telegram_id)

        assert result is True
        # Verify cascade delete
        mock_database.usage_logs.delete_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_repository, mock_database):
        """Test deletion returns False when user not found."""
        mock_result = Mock()
        mock_result.deleted_count = 0
        mock_database.users.delete_one = Mock(return_value=mock_result)

        result = await user_repository.delete_user(123456789)

        assert result is False

    @pytest.mark.asyncio
    async def test_user_exists_true(self, user_repository, mock_database):
        """Test user_exists returns True when user exists."""
        mock_database.users.count_documents = Mock(return_value=1)

        result = await user_repository.user_exists(123456789)

        assert result is True

    @pytest.mark.asyncio
    async def test_user_exists_false(self, user_repository, mock_database):
        """Test user_exists returns False when user doesn't exist."""
        mock_database.users.count_documents = Mock(return_value=0)

        result = await user_repository.user_exists(123456789)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_spotify_tokens(self, user_repository, mock_database):
        """Test updating Spotify tokens."""
        telegram_id = 123456789

        mock_result = Mock()
        mock_result.modified_count = 1
        mock_database.users.update_one = Mock(return_value=mock_result)

        result = await user_repository.update_spotify_tokens(
            telegram_id, "new_access", "new_refresh", datetime.utcnow()
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_get_user_count(self, user_repository, mock_database):
        """Test getting total user count."""
        mock_database.users.count_documents = Mock(return_value=42)

        result = await user_repository.get_user_count()

        assert result == 42


class TestSearchCacheRepository:
    """Test suite for SearchCacheRepository."""

    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        db = Mock()
        db.search_cache = Mock()
        return db

    @pytest.fixture
    def cache_repository(self, mock_database):
        """Create SearchCacheRepository."""
        return SearchCacheRepository(mock_database)

    @pytest.mark.asyncio
    async def test_get_cached_result_hit(self, cache_repository, mock_database):
        """Test cache hit."""
        query = "test query"
        track_id = "spotify:track:123"

        mock_database.search_cache.find_one = Mock(
            return_value={
                "query_string": query,
                "spotify_track_id": track_id,
            }
        )

        result = await cache_repository.get_cached_result(query)

        assert result == track_id

    @pytest.mark.asyncio
    async def test_get_cached_result_miss(self, cache_repository, mock_database):
        """Test cache miss."""
        mock_database.search_cache.find_one = Mock(return_value=None)

        result = await cache_repository.get_cached_result("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_result_success(self, cache_repository, mock_database):
        """Test successful result caching."""
        query = "test query"
        track_id = "spotify:track:123"

        mock_database.search_cache.replace_one = Mock()

        result = await cache_repository.cache_result(query, track_id)

        assert result is True
        mock_database.search_cache.replace_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_repository, mock_database):
        """Test cache clearing."""
        mock_result = Mock()
        mock_result.deleted_count = 10
        mock_database.search_cache.delete_many = Mock(return_value=mock_result)

        result = await cache_repository.clear_cache()

        assert result == 10


class TestUsageLogsRepository:
    """Test suite for UsageLogsRepository."""

    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        db = Mock()
        db.usage_logs = Mock()
        return db

    @pytest.fixture
    def logs_repository(self, mock_database):
        """Create UsageLogsRepository."""
        return UsageLogsRepository(mock_database)

    @pytest.mark.asyncio
    async def test_log_command_success(self, logs_repository, mock_database):
        """Test successful command logging."""
        telegram_id = 123456789
        command = "/play"

        mock_database.usage_logs.insert_one = Mock()

        result = await logs_repository.log_command(telegram_id, command)

        assert result is True
        mock_database.usage_logs.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_command_with_extra_data(self, logs_repository, mock_database):
        """Test logging with extra data."""
        telegram_id = 123456789
        command = "/search"
        extra_data = {"query": "test song"}

        mock_database.usage_logs.insert_one = Mock()

        result = await logs_repository.log_command(telegram_id, command, extra_data)

        assert result is True
        call_args = mock_database.usage_logs.insert_one.call_args[0][0]
        assert call_args["query"] == "test song"

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, logs_repository, mock_database):
        """Test getting user statistics."""
        telegram_id = 123456789

        mock_results = [
            {"_id": "/play", "count": 10},
            {"_id": "/search", "count": 5},
        ]
        mock_database.usage_logs.aggregate = Mock(return_value=mock_results)

        result = await logs_repository.get_user_stats(telegram_id, days=30)

        assert result["total_commands"] == 15
        assert result["most_used_command"] == "/play"
        assert result["command_breakdown"]["/play"] == 10

    @pytest.mark.asyncio
    async def test_get_user_stats_no_data(self, logs_repository, mock_database):
        """Test getting stats with no data."""
        mock_database.usage_logs.aggregate = Mock(return_value=[])

        result = await logs_repository.get_user_stats(123456789)

        assert result["total_commands"] == 0
        assert result["most_used_command"] is None

    @pytest.mark.asyncio
    async def test_delete_user_logs(self, logs_repository, mock_database):
        """Test deleting user logs."""
        telegram_id = 123456789

        mock_result = Mock()
        mock_result.deleted_count = 25
        mock_database.usage_logs.delete_many = Mock(return_value=mock_result)

        result = await logs_repository.delete_user_logs(telegram_id)

        assert result == 25


class TestRepositoryErrorHandling:
    """Test suite for repository error handling."""

    @pytest.fixture
    def mock_database(self):
        """Create mock database that raises errors."""
        db = Mock()
        db.users = Mock()
        return db

    @pytest.mark.asyncio
    async def test_create_user_database_error(self, mock_database):
        """Test user creation handles database errors."""
        from pymongo.errors import PyMongoError

        mock_database.users.insert_one = Mock(side_effect=PyMongoError("DB error"))

        with patch("rspotify_bot.services.repository.get_encryption_service"):
            repo = UserRepository(mock_database)

            with pytest.raises(RepositoryError, match="Failed to create user"):
                await repo.create_user(123456789)

    @pytest.mark.asyncio
    async def test_get_user_database_error(self, mock_database):
        """Test user retrieval handles database errors."""
        from pymongo.errors import PyMongoError

        mock_database.users.find_one = Mock(side_effect=PyMongoError("DB error"))

        with patch("rspotify_bot.services.repository.get_encryption_service"):
            repo = UserRepository(mock_database)

            with pytest.raises(RepositoryError, match="Failed to get user"):
                await repo.get_user(123456789)

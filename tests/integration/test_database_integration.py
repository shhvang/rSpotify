"""
Integration tests for database operations with real MongoDB connection.
Tests encryption, repository operations, and data integrity.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from rspotify_bot.services.database import DatabaseService
from rspotify_bot.services.encryption import EncryptionService
from rspotify_bot.services.repository import (
    UserRepository,
    SearchCacheRepository,
    UsageLogsRepository,
    RepositoryError,
)
from rspotify_bot.config import config


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def db_service():
    """Create and connect to database service."""
    service = DatabaseService()
    connected = await service.connect()

    if not connected:
        pytest.skip("Database connection not available")

    yield service

    # Cleanup: delete test data
    if service.database is not None:
        # Clean up test users
        service.database.users.delete_many({"telegram_id": {"$gte": 999000000}})
        service.database.search_cache.delete_many(
            {"query_string": {"$regex": "^test_"}}
        )
        service.database.usage_logs.delete_many({"telegram_id": {"$gte": 999000000}})

    await service.disconnect()


@pytest.fixture
def encryption_service():
    """Create encryption service."""
    return EncryptionService()


@pytest.fixture
def test_telegram_id():
    """Generate unique test telegram ID."""
    import random

    return 999000000 + random.randint(0, 999999)


class TestDatabaseConnection:
    """Test database connection and health checks."""

    @pytest.mark.asyncio
    async def test_database_connection(self, db_service):
        """Test database connects successfully."""
        assert db_service.database is not None
        assert db_service._connection_validated is True

    @pytest.mark.asyncio
    async def test_health_check(self, db_service):
        """Test database health check."""
        is_healthy = await db_service.health_check()
        assert is_healthy is True


class TestDatabaseIndexes:
    """Test database index creation and verification."""

    @pytest.mark.asyncio
    async def test_users_collection_indexes(self, db_service):
        """Test users collection has required indexes."""
        indexes = list(db_service.database.users.list_indexes())
        index_names = [idx["name"] for idx in indexes]

        # Should have telegram_id unique index
        assert any("telegram_id" in name for name in index_names)

    @pytest.mark.asyncio
    async def test_search_cache_ttl_index(self, db_service):
        """Test search_cache has TTL index."""
        indexes = list(db_service.database.search_cache.list_indexes())

        # Find TTL index
        ttl_index = None
        for idx in indexes:
            if "expireAfterSeconds" in idx:
                ttl_index = idx
                break

        assert ttl_index is not None, "TTL index not found on search_cache"
        assert ttl_index["expireAfterSeconds"] == 2592000  # 30 days

    @pytest.mark.asyncio
    async def test_usage_logs_indexes(self, db_service):
        """Test usage_logs collection has required indexes."""
        indexes = list(db_service.database.usage_logs.list_indexes())
        index_names = [idx["name"] for idx in indexes]

        # Should have telegram_id and timestamp indexes
        assert any("telegram_id" in name for name in index_names)
        assert any("timestamp" in name for name in index_names)


class TestUserRepositoryIntegration:
    """Integration tests for UserRepository with real database."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_user(self, db_service, test_telegram_id):
        """Test creating and retrieving a user."""
        repo = UserRepository(db_service.database)

        # Create user
        created = await repo.create_user(
            telegram_id=test_telegram_id, custom_name="Integration Test User"
        )
        assert created is True

        # Retrieve user
        user = await repo.get_user(test_telegram_id)
        assert user is not None
        assert user["telegram_id"] == test_telegram_id
        assert user["custom_name"] == "Integration Test User"
        assert "created_at" in user
        assert "updated_at" in user

        # Cleanup
        await repo.delete_user(test_telegram_id)

    @pytest.mark.asyncio
    async def test_create_user_with_encrypted_tokens(
        self, db_service, test_telegram_id
    ):
        """Test creating user with Spotify tokens (encrypted)."""
        repo = UserRepository(db_service.database)

        tokens = {
            "access_token": "test_access_token_12345",
            "refresh_token": "test_refresh_token_67890",
            "expires_at": datetime.utcnow(),
        }

        # Create user with tokens
        created = await repo.create_user(
            telegram_id=test_telegram_id,
            custom_name="Token Test User",
            spotify_tokens=tokens,
        )
        assert created is True

        # Retrieve and verify tokens are decrypted
        user = await repo.get_user(test_telegram_id)
        assert user is not None
        assert user["spotify"] is not None
        assert user["spotify"]["access_token"] == "test_access_token_12345"
        assert user["spotify"]["refresh_token"] == "test_refresh_token_67890"

        # Verify tokens are encrypted in database
        raw_user = db_service.database.users.find_one({"telegram_id": test_telegram_id})
        assert raw_user["spotify"]["access_token"] != "test_access_token_12345"
        assert raw_user["spotify"]["refresh_token"] != "test_refresh_token_67890"

        # Cleanup
        await repo.delete_user(test_telegram_id)

    @pytest.mark.asyncio
    async def test_update_user(self, db_service, test_telegram_id):
        """Test updating user data."""
        repo = UserRepository(db_service.database)

        # Create user
        await repo.create_user(test_telegram_id, "Original Name")

        # Update user
        updated = await repo.update_user(
            test_telegram_id, {"custom_name": "Updated Name"}
        )
        assert updated is True

        # Verify update
        user = await repo.get_user(test_telegram_id)
        assert user["custom_name"] == "Updated Name"

        # Cleanup
        await repo.delete_user(test_telegram_id)

    @pytest.mark.asyncio
    async def test_delete_user_cascade(self, db_service, test_telegram_id):
        """Test cascade deletion of user data."""
        repo = UserRepository(db_service.database)
        logs_repo = UsageLogsRepository(db_service.database)

        # Create user and logs
        await repo.create_user(test_telegram_id, "Delete Test User")
        await logs_repo.log_command(test_telegram_id, "/test1")
        await logs_repo.log_command(test_telegram_id, "/test2")

        # Verify user and logs exist
        user = await repo.get_user(test_telegram_id)
        assert user is not None

        log_count = db_service.database.usage_logs.count_documents(
            {"telegram_id": test_telegram_id}
        )
        assert log_count == 2

        # Delete user (cascade)
        deleted = await repo.delete_user(test_telegram_id)
        assert deleted is True

        # Verify user is gone
        user = await repo.get_user(test_telegram_id)
        assert user is None

        # Verify logs are deleted
        log_count = db_service.database.usage_logs.count_documents(
            {"telegram_id": test_telegram_id}
        )
        assert log_count == 0

    @pytest.mark.asyncio
    async def test_duplicate_user_creation_fails(self, db_service, test_telegram_id):
        """Test that creating duplicate user fails."""
        repo = UserRepository(db_service.database)

        # Create user
        await repo.create_user(test_telegram_id, "First User")

        # Try to create duplicate
        with pytest.raises(RepositoryError, match="already exists"):
            await repo.create_user(test_telegram_id, "Duplicate User")

        # Cleanup
        await repo.delete_user(test_telegram_id)

    @pytest.mark.asyncio
    async def test_user_exists_check(self, db_service, test_telegram_id):
        """Test checking if user exists."""
        repo = UserRepository(db_service.database)

        # User doesn't exist initially
        exists = await repo.user_exists(test_telegram_id)
        assert exists is False

        # Create user
        await repo.create_user(test_telegram_id)

        # User now exists
        exists = await repo.user_exists(test_telegram_id)
        assert exists is True

        # Cleanup
        await repo.delete_user(test_telegram_id)


class TestSearchCacheRepositoryIntegration:
    """Integration tests for SearchCacheRepository."""

    @pytest.mark.asyncio
    async def test_cache_and_retrieve(self, db_service):
        """Test caching and retrieving search results."""
        repo = SearchCacheRepository(db_service.database)

        query = "test_integration_query_unique"
        track_id = "spotify:track:test123456789012"

        # Cache result
        cached = await repo.cache_result(query, track_id)
        assert cached is True

        # Retrieve cached result
        result = await repo.get_cached_result(query)
        assert result == track_id

        # Cleanup
        db_service.database.search_cache.delete_one({"query_string": query})

    @pytest.mark.asyncio
    async def test_cache_miss(self, db_service):
        """Test cache miss returns None."""
        repo = SearchCacheRepository(db_service.database)

        result = await repo.get_cached_result("nonexistent_query_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_upsert(self, db_service):
        """Test caching same query twice updates the entry."""
        repo = SearchCacheRepository(db_service.database)

        query = "test_upsert_query"
        track_id_1 = "spotify:track:first12345678901"
        track_id_2 = "spotify:track:second1234567890"

        # Cache first result
        await repo.cache_result(query, track_id_1)

        # Cache second result (should update)
        await repo.cache_result(query, track_id_2)

        # Retrieve should return second result
        result = await repo.get_cached_result(query)
        assert result == track_id_2

        # Verify only one entry exists
        count = db_service.database.search_cache.count_documents(
            {"query_string": query}
        )
        assert count == 1

        # Cleanup
        db_service.database.search_cache.delete_one({"query_string": query})


class TestUsageLogsRepositoryIntegration:
    """Integration tests for UsageLogsRepository."""

    @pytest.mark.asyncio
    async def test_log_command(self, db_service, test_telegram_id):
        """Test logging command usage."""
        repo = UsageLogsRepository(db_service.database)

        # Log command
        logged = await repo.log_command(test_telegram_id, "/play")
        assert logged is True

        # Verify log exists
        log = db_service.database.usage_logs.find_one(
            {"telegram_id": test_telegram_id, "command": "/play"}
        )
        assert log is not None
        assert "timestamp" in log

        # Cleanup
        await repo.delete_user_logs(test_telegram_id)

    @pytest.mark.asyncio
    async def test_log_command_with_extra_data(self, db_service, test_telegram_id):
        """Test logging with extra data."""
        repo = UsageLogsRepository(db_service.database)

        extra = {"track_id": "spotify:track:123", "duration_ms": 5000}

        logged = await repo.log_command(test_telegram_id, "/play", extra)
        assert logged is True

        # Verify extra data is stored
        log = db_service.database.usage_logs.find_one(
            {"telegram_id": test_telegram_id, "command": "/play"}
        )
        assert log["track_id"] == "spotify:track:123"
        assert log["duration_ms"] == 5000

        # Cleanup
        await repo.delete_user_logs(test_telegram_id)

    @pytest.mark.asyncio
    async def test_get_user_stats(self, db_service, test_telegram_id):
        """Test getting user statistics."""
        repo = UsageLogsRepository(db_service.database)

        # Log multiple commands
        await repo.log_command(test_telegram_id, "/play")
        await repo.log_command(test_telegram_id, "/play")
        await repo.log_command(test_telegram_id, "/play")
        await repo.log_command(test_telegram_id, "/search")
        await repo.log_command(test_telegram_id, "/search")

        # Get stats
        stats = await repo.get_user_stats(test_telegram_id, days=30)

        assert stats["total_commands"] == 5
        assert stats["command_breakdown"]["/play"] == 3
        assert stats["command_breakdown"]["/search"] == 2
        assert stats["most_used_command"] == "/play"

        # Cleanup
        await repo.delete_user_logs(test_telegram_id)

    @pytest.mark.asyncio
    async def test_delete_user_logs(self, db_service, test_telegram_id):
        """Test deleting all user logs."""
        repo = UsageLogsRepository(db_service.database)

        # Create multiple logs
        await repo.log_command(test_telegram_id, "/play")
        await repo.log_command(test_telegram_id, "/search")
        await repo.log_command(test_telegram_id, "/help")

        # Verify logs exist
        count_before = db_service.database.usage_logs.count_documents(
            {"telegram_id": test_telegram_id}
        )
        assert count_before == 3

        # Delete logs
        deleted_count = await repo.delete_user_logs(test_telegram_id)
        assert deleted_count == 3

        # Verify logs are gone
        count_after = db_service.database.usage_logs.count_documents(
            {"telegram_id": test_telegram_id}
        )
        assert count_after == 0


class TestEncryptionIntegration:
    """Integration tests for encryption with database."""

    @pytest.mark.asyncio
    async def test_encryption_roundtrip_with_database(
        self, db_service, encryption_service, test_telegram_id
    ):
        """Test complete encryption roundtrip through database."""
        repo = UserRepository(db_service.database)

        original_access = "spotify_access_token_abc123"
        original_refresh = "spotify_refresh_token_xyz789"

        tokens = {
            "access_token": original_access,
            "refresh_token": original_refresh,
            "expires_at": datetime.utcnow(),
        }

        # Create user with tokens
        await repo.create_user(test_telegram_id, spotify_tokens=tokens)

        # Retrieve user (tokens should be decrypted)
        user = await repo.get_user(test_telegram_id)
        assert user["spotify"]["access_token"] == original_access
        assert user["spotify"]["refresh_token"] == original_refresh

        # Verify encryption in raw database
        raw_user = db_service.database.users.find_one({"telegram_id": test_telegram_id})
        encrypted_access = raw_user["spotify"]["access_token"]
        encrypted_refresh = raw_user["spotify"]["refresh_token"]

        # Encrypted values should differ from originals
        assert encrypted_access != original_access
        assert encrypted_refresh != original_refresh

        # Manually decrypt to verify encryption worked
        decrypted_access = encryption_service.decrypt_token(encrypted_access)
        decrypted_refresh = encryption_service.decrypt_token(encrypted_refresh)

        assert decrypted_access == original_access
        assert decrypted_refresh == original_refresh

        # Cleanup
        await repo.delete_user(test_telegram_id)


class TestDataIntegrity:
    """Integration tests for data integrity and constraints."""

    @pytest.mark.asyncio
    async def test_telegram_id_uniqueness(self, db_service, test_telegram_id):
        """Test telegram_id unique constraint."""
        repo = UserRepository(db_service.database)

        # Create user
        await repo.create_user(test_telegram_id, "First User")

        # Attempt duplicate creation should fail
        with pytest.raises(RepositoryError):
            await repo.create_user(test_telegram_id, "Duplicate User")

        # Cleanup
        await repo.delete_user(test_telegram_id)

    @pytest.mark.asyncio
    async def test_updated_at_timestamp_changes(self, db_service, test_telegram_id):
        """Test that updated_at timestamp changes on update."""
        repo = UserRepository(db_service.database)

        # Create user
        await repo.create_user(test_telegram_id, "Test User")

        # Get initial timestamps
        user1 = await repo.get_user(test_telegram_id)
        created_at = user1["created_at"]
        updated_at_1 = user1["updated_at"]

        # Wait a moment
        await asyncio.sleep(0.1)

        # Update user
        await repo.update_user(test_telegram_id, {"custom_name": "Updated Name"})

        # Get updated timestamps
        user2 = await repo.get_user(test_telegram_id)
        updated_at_2 = user2["updated_at"]

        # created_at should not change
        assert user2["created_at"] == created_at

        # updated_at should change
        assert updated_at_2 > updated_at_1

        # Cleanup
        await repo.delete_user(test_telegram_id)

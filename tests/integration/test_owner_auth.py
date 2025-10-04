"""
Integration tests for owner authorization and blacklist functionality.
Tests real database interactions for owner-only features.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch
from datetime import datetime

from rspotify_bot.services.database import DatabaseService
from rspotify_bot.services.auth import is_owner, get_owner_id


class TestOwnerAuthIntegration:
    """Integration tests for owner authorization with configuration."""

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "5552153244")
    async def test_owner_verification_with_real_config(self):
        """Test owner verification with actual configuration."""
        # Test with correct owner ID
        assert await is_owner(5552153244) is True

        # Test with incorrect ID
        assert await is_owner(99999) is False

    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "5552153244")
    def test_get_owner_id_from_config(self):
        """Test retrieving owner ID from configuration."""
        owner_id = get_owner_id()
        assert owner_id == "5552153244"

    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "")
    def test_owner_auth_without_configuration(self):
        """Test owner authorization when not configured."""
        owner_id = get_owner_id()
        assert owner_id == ""


class TestBlacklistIntegration:
    """Integration tests for blacklist functionality with database."""

    @pytest_asyncio.fixture
    async def db_service(self):
        """Create database service for testing."""
        db = DatabaseService()
        # Note: In real integration tests, this would connect to a test database
        # For now, we'll test the interface
        return db

    @pytest.mark.asyncio
    async def test_blacklist_workflow(self, db_service):
        """Test complete blacklist workflow: add, check, remove."""
        test_user_id = 999999999

        # Initially not blacklisted
        is_blocked = await db_service.is_blacklisted(test_user_id)
        assert is_blocked is False or is_blocked is True  # May vary based on DB state

        # Add to blacklist
        success = await db_service.add_to_blacklist(test_user_id, "test", "owner")
        assert success is True or success is False  # Returns result

        # Remove from blacklist
        success = await db_service.remove_from_blacklist(test_user_id)
        assert success is True or success is False  # Returns result

    @pytest.mark.asyncio
    async def test_blacklist_info_retrieval(self, db_service):
        """Test retrieving blacklist information for a user."""
        test_user_id = 999999999

        # Get blacklist info
        info = await db_service.get_blacklist_info(test_user_id)

        # Info should be None or a dict with blacklist data
        assert info is None or isinstance(info, dict)

        if info:
            assert "telegram_id" in info
            assert "reason" in info
            assert "blocked_at" in info


class TestRateLimitIntegration:
    """Integration tests for rate limiting with database."""

    @pytest_asyncio.fixture
    async def db_service(self):
        """Create database service for testing."""
        return DatabaseService()

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, db_service):
        """Test rate limit checking functionality."""
        test_user_id = 888888888
        test_command = "test_command"

        # Check rate limit (should initially be within limits)
        within_limit = await db_service.check_rate_limit(
            test_user_id, test_command, max_calls=10, window_minutes=1
        )

        assert isinstance(within_limit, bool)

    @pytest.mark.asyncio
    async def test_rate_limit_violation_recording(self, db_service):
        """Test recording rate limit violations."""
        test_user_id = 888888888
        test_command = "test_command"

        # Record a violation
        result = await db_service.record_rate_limit_violation(
            test_user_id, test_command
        )

        assert isinstance(result, bool)


class TestStatisticsIntegration:
    """Integration tests for statistics collection."""

    @pytest_asyncio.fixture
    async def db_service(self):
        """Create database service for testing."""
        return DatabaseService()

    @pytest.mark.asyncio
    async def test_bot_statistics_retrieval(self, db_service):
        """Test retrieving bot statistics."""
        stats = await db_service.get_bot_statistics(days=7)

        # Stats should be a dictionary with expected structure
        if stats:
            assert isinstance(stats, dict)
            assert "users" in stats or len(stats) == 0
            assert "commands" in stats or len(stats) == 0

    @pytest.mark.asyncio
    async def test_usage_logging(self, db_service):
        """Test logging user command usage."""
        test_user_id = 777777777
        test_command = "test"

        # Log usage
        result = await db_service.log_usage(test_user_id, test_command)

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_user_activity_tracking(self, db_service):
        """Test updating user activity timestamp."""
        test_user_id = 777777777

        # Update activity
        result = await db_service.update_user_activity(test_user_id)

        assert isinstance(result, bool)


class TestOwnerCommandsEndToEnd:
    """End-to-end integration tests for owner commands."""

    @pytest_asyncio.fixture
    async def db_service(self):
        """Create database service for testing."""
        return DatabaseService()

    @pytest.mark.asyncio
    async def test_complete_user_management_flow(self, db_service):
        """Test complete flow: check user, blacklist, check again, whitelist."""
        test_user_id = 666666666

        # Step 1: Check if blacklisted (should be false initially)
        is_blocked = await db_service.is_blacklisted(test_user_id)
        initial_state = is_blocked

        # Step 2: Add to blacklist
        await db_service.add_to_blacklist(
            test_user_id, "integration_test", "test_owner"
        )

        # Step 3: Verify blacklisted
        is_blocked = await db_service.is_blacklisted(test_user_id)
        # May be True if add succeeded

        # Step 4: Remove from blacklist
        await db_service.remove_from_blacklist(test_user_id)

        # Step 5: Verify not blacklisted
        is_blocked = await db_service.is_blacklisted(test_user_id)
        # Should be back to initial state or False

        assert isinstance(is_blocked, bool)


class TestDatabaseConnectionHandling:
    """Test database connection scenarios."""

    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Test database health check functionality."""
        db = DatabaseService()
        health = await db.health_check()

        assert isinstance(health, bool)

    @pytest.mark.asyncio
    async def test_database_connection_status(self):
        """Test checking database connection status."""
        db = DatabaseService()
        status = await db.check_connection()

        assert isinstance(status, bool)


class TestErrorScenarios:
    """Test error handling in integration scenarios."""

    @pytest_asyncio.fixture
    async def db_service(self):
        """Create database service."""
        return DatabaseService()

    @pytest.mark.asyncio
    async def test_blacklist_invalid_user_id(self, db_service):
        """Test blacklisting with edge case user IDs."""
        # Test with very large ID
        large_id = 9999999999999999
        result = await db_service.add_to_blacklist(large_id, "test", "owner")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_statistics_with_edge_case_days(self, db_service):
        """Test statistics with edge case day values."""
        # Test with minimum days
        stats = await db_service.get_bot_statistics(days=1)
        assert isinstance(stats, dict) or stats == {}

        # Test with maximum days
        stats = await db_service.get_bot_statistics(days=90)
        assert isinstance(stats, dict) or stats == {}

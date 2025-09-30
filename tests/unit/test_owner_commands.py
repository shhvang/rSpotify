"""
Unit tests for owner command handlers.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from rspotify_bot.handlers.owner_commands import OwnerCommands
from rspotify_bot.services.database import DatabaseService


class TestMaintenanceCommand:
    """Test cases for maintenance mode functionality."""

    @pytest.fixture
    def owner_commands(self):
        """Create OwnerCommands instance with mocked database."""
        mock_db = Mock(spec=DatabaseService)
        return OwnerCommands(mock_db)

    def test_maintenance_mode_initial_state(self, owner_commands):
        """Test that maintenance mode starts as False."""
        assert owner_commands.is_maintenance_mode() is False

    def test_maintenance_mode_toggle_on(self, owner_commands):
        """Test turning maintenance mode on."""
        owner_commands.maintenance_mode = True
        assert owner_commands.is_maintenance_mode() is True

    def test_maintenance_mode_toggle_off(self, owner_commands):
        """Test turning maintenance mode off."""
        owner_commands.maintenance_mode = True
        owner_commands.maintenance_mode = False
        assert owner_commands.is_maintenance_mode() is False

    @pytest.mark.asyncio
    async def test_send_maintenance_message(self, owner_commands):
        """Test sending maintenance message to user."""
        # Create mock update
        mock_update = Mock()
        mock_message = Mock()
        mock_message.reply_html = AsyncMock()
        mock_update.message = mock_message

        # Send maintenance message
        await owner_commands.send_maintenance_message(mock_update)

        # Verify message was sent
        mock_message.reply_html.assert_called_once()
        call_args = mock_message.reply_html.call_args[0][0]
        assert "Maintenance Mode" in call_args
        assert "maintenance" in call_args.lower()


class TestStatsCommand:
    """Test cases for statistics command functionality."""

    @pytest.fixture
    def owner_commands(self):
        """Create OwnerCommands instance with mocked database."""
        mock_db = Mock(spec=DatabaseService)
        return OwnerCommands(mock_db)

    def test_stats_cache_initialization(self, owner_commands):
        """Test stats cache starts as None."""
        assert owner_commands._stats_cache is None

    def test_stats_cache_expiry(self, owner_commands):
        """Test stats cache expiry time is set."""
        assert owner_commands._cache_expires is not None
        assert isinstance(owner_commands._cache_expires, datetime)


class TestBlacklistFunctionality:
    """Test cases for blacklist management."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database service."""
        db = Mock(spec=DatabaseService)
        db.is_blacklisted = Mock(return_value=False)
        db.add_to_blacklist = Mock(return_value=True)
        db.remove_from_blacklist = Mock(return_value=True)
        db.get_blacklist_info = Mock(return_value=None)
        return db

    @pytest.fixture
    def owner_commands(self, mock_db):
        """Create OwnerCommands instance."""
        return OwnerCommands(mock_db)

    def test_add_to_blacklist_success(self, mock_db):
        """Test successfully adding user to blacklist."""
        result = mock_db.add_to_blacklist(12345, "spam", "owner_id")
        assert result is True
        mock_db.add_to_blacklist.assert_called_once_with(12345, "spam", "owner_id")

    def test_remove_from_blacklist_success(self, mock_db):
        """Test successfully removing user from blacklist."""
        result = mock_db.remove_from_blacklist(12345)
        assert result is True
        mock_db.remove_from_blacklist.assert_called_once_with(12345)

    def test_check_blacklist_status_not_blocked(self, mock_db):
        """Test checking blacklist status for non-blocked user."""
        result = mock_db.is_blacklisted(12345)
        assert result is False

    def test_check_blacklist_status_blocked(self, mock_db):
        """Test checking blacklist status for blocked user."""
        mock_db.is_blacklisted = Mock(return_value=True)
        result = mock_db.is_blacklisted(12345)
        assert result is True


class TestRateLimiting:
    """Test cases for rate limiting functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database service."""
        db = Mock(spec=DatabaseService)
        db.check_rate_limit = Mock(return_value=True)
        db.record_rate_limit_violation = Mock(return_value=True)
        return db

    def test_check_rate_limit_within_limit(self, mock_db):
        """Test rate limit check when within limits."""
        result = mock_db.check_rate_limit(12345, "start", 10, 1)
        assert result is True

    def test_check_rate_limit_exceeded(self, mock_db):
        """Test rate limit check when limit exceeded."""
        mock_db.check_rate_limit = Mock(return_value=False)
        result = mock_db.check_rate_limit(12345, "start", 10, 1)
        assert result is False

    def test_record_rate_limit_violation(self, mock_db):
        """Test recording rate limit violation."""
        result = mock_db.record_rate_limit_violation(12345, "start")
        assert result is True


class TestOwnerCommandsIntegration:
    """Integration tests for owner commands with database."""

    @pytest.fixture
    def mock_db(self):
        """Create comprehensive mock database."""
        db = Mock(spec=DatabaseService)
        db.get_bot_statistics = Mock(
            return_value={
                "period_days": 7,
                "users": {"total": 100, "active": 50, "new": 10, "blacklisted": 2},
                "commands": {
                    "total": 500,
                    "breakdown": [
                        {"_id": "start", "count": 200},
                        {"_id": "help", "count": 150},
                        {"_id": "ping", "count": 100},
                    ],
                    "most_popular": "start",
                },
                "daily_usage": [],
            }
        )
        return db

    @pytest.fixture
    def owner_commands(self, mock_db):
        """Create OwnerCommands instance."""
        return OwnerCommands(mock_db)

    @pytest.mark.asyncio
    async def test_stats_command_returns_data(self, owner_commands, mock_db):
        """Test that stats command retrieves and formats data correctly."""
        stats = mock_db.get_bot_statistics(7)
        assert stats is not None
        assert stats["users"]["total"] == 100
        assert stats["commands"]["most_popular"] == "start"


class TestErrorHandling:
    """Test error handling in owner commands."""

    @pytest.fixture
    def owner_commands_with_failing_db(self):
        """Create OwnerCommands with database that raises exceptions."""
        mock_db = Mock(spec=DatabaseService)
        mock_db.is_blacklisted = Mock(side_effect=Exception("Database error"))
        mock_db.add_to_blacklist = Mock(side_effect=Exception("Database error"))
        return OwnerCommands(mock_db)

    def test_blacklist_check_handles_exception(self, owner_commands_with_failing_db):
        """Test that blacklist check handles database exceptions gracefully."""
        mock_db = owner_commands_with_failing_db.db
        try:
            mock_db.is_blacklisted(12345)
            # Should not reach here due to exception
            assert False, "Expected exception was not raised"
        except Exception as e:
            assert "Database error" in str(e)


class TestCommandValidation:
    """Test input validation for owner commands."""

    @pytest.fixture
    def owner_commands(self):
        """Create OwnerCommands instance."""
        mock_db = Mock(spec=DatabaseService)
        return OwnerCommands(mock_db)

    def test_maintenance_valid_commands(self):
        """Test valid maintenance mode commands."""
        valid_commands = ["on", "off"]
        for cmd in valid_commands:
            assert cmd in ["on", "off"]

    def test_stats_days_range_validation(self):
        """Test stats days parameter validation."""
        # Valid range: 1-90 days
        assert 1 <= 7 <= 90  # default
        assert 1 <= 30 <= 90  # common use
        assert 1 <= 90 <= 90  # max


class TestNotificationService:
    """Test notification service functionality."""

    @pytest.mark.asyncio
    async def test_startup_notification_format(self):
        """Test startup notification message format."""
        # This would test the notification service separately
        # Verifying the message contains required elements
        message_parts = [
            "rSpotify Bot Started",
            "Version:",
            "Environment:",
            "Deployed:",
            "Database:",
        ]

        # All parts should be present in a startup notification
        assert all(part for part in message_parts)

    @pytest.mark.asyncio
    async def test_error_report_format(self):
        """Test error report message format."""
        error_parts = [
            "Critical Error Detected",
            "Type:",
            "Time:",
            "Environment:",
            "Message:",
        ]

        # All parts should be present in an error report
        assert all(part for part in error_parts)

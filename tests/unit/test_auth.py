"""
Unit tests for owner authorization service.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

from rspotify_bot.services.auth import owner_only, is_owner, get_owner_id


class TestOwnerAuthorization:
    """Test cases for owner authorization functionality."""

    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    def test_get_owner_id(self):
        """Test getting owner ID from configuration."""
        owner_id = get_owner_id()
        assert owner_id == "12345"

    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "")
    def test_get_owner_id_not_configured(self):
        """Test getting owner ID when not configured."""
        owner_id = get_owner_id()
        assert owner_id == ""

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    async def test_is_owner_true(self):
        """Test is_owner returns True for owner."""
        result = await is_owner(12345)
        assert result is True

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    async def test_is_owner_false(self):
        """Test is_owner returns False for non-owner."""
        result = await is_owner(54321)
        assert result is False

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "")
    async def test_is_owner_not_configured(self):
        """Test is_owner returns False when owner not configured."""
        result = await is_owner(12345)
        assert result is False

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    async def test_owner_only_decorator_authorized(self):
        """Test owner_only decorator allows authorized access."""
        # Mock function to decorate
        mock_func = AsyncMock()
        decorated_func = owner_only(mock_func)

        # Create mock update with owner user
        user = User(id=12345, first_name="Owner", is_bot=False)
        chat = Chat(id=1, type="private")
        message = Message(
            message_id=1, date=None, chat=chat, from_user=user, text="/test"
        )
        update = Update(update_id=1, message=message)
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        # Call decorated function
        await decorated_func(update, context)

        # Verify original function was called
        mock_func.assert_called_once_with(update, context)

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    async def test_owner_only_decorator_unauthorized(self):
        """Test owner_only decorator blocks unauthorized access."""
        # Mock function to decorate
        mock_func = AsyncMock()
        decorated_func = owner_only(mock_func)

        # Create mock update with non-owner user
        user = User(id=54321, first_name="Regular", is_bot=False)
        chat = Chat(id=1, type="private")
        message_obj = Mock()
        message_obj.reply_html = AsyncMock()
        message_obj.from_user = user
        message_obj.chat = chat

        update = Mock(spec=Update)
        update.message = message_obj
        update.effective_user = user
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        # Call decorated function
        result = await decorated_func(update, context)

        # Verify original function was NOT called
        mock_func.assert_not_called()

        # Verify access denied message was sent
        message_obj.reply_html.assert_called_once()
        call_args = message_obj.reply_html.call_args[0][0]
        assert "Access Denied" in call_args

        # Verify function returned None
        assert result is None

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "")
    async def test_owner_only_decorator_not_configured(self):
        """Test owner_only decorator handles unconfigured owner."""
        # Mock function to decorate
        mock_func = AsyncMock()
        decorated_func = owner_only(mock_func)

        # Create mock update
        user = User(id=12345, first_name="User", is_bot=False)
        chat = Chat(id=1, type="private")
        message_obj = Mock()
        message_obj.reply_html = AsyncMock()
        message_obj.from_user = user
        message_obj.chat = chat

        update = Mock(spec=Update)
        update.message = message_obj
        update.effective_user = user
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        # Call decorated function
        result = await decorated_func(update, context)

        # Verify original function was NOT called
        mock_func.assert_not_called()

        # Verify configuration error message was sent
        message_obj.reply_html.assert_called_once()
        call_args = message_obj.reply_html.call_args[0][0]
        assert "Configuration Error" in call_args

        # Verify function returned None
        assert result is None

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.OWNER_TELEGRAM_ID", "12345")
    async def test_owner_only_decorator_no_user(self):
        """Test owner_only decorator handles update with no user."""
        # Mock function to decorate
        mock_func = AsyncMock()
        decorated_func = owner_only(mock_func)

        # Create mock update with no user
        chat = Chat(id=1, type="private")
        message_obj = Mock()
        message_obj.reply_html = AsyncMock()
        message_obj.from_user = None
        message_obj.chat = chat

        update = Mock(spec=Update)
        update.message = message_obj
        update.effective_user = None
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        # Call decorated function
        result = await decorated_func(update, context)

        # Verify original function was NOT called
        mock_func.assert_not_called()

        # Verify access denied message was sent
        message_obj.reply_html.assert_called_once()
        call_args = message_obj.reply_html.call_args[0][0]
        assert "Access Denied" in call_args

        # Verify function returned None
        assert result is None

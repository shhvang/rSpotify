"""
Unit tests for bot functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, User, Chat, Message

from rspotify_bot.bot import RSpotifyBot


class TestRSpotifyBot:
    """Test RSpotifyBot class functionality."""

    @pytest.fixture
    def bot(self):
        """Create bot instance for testing."""
        return RSpotifyBot("test_token")

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.effective_user.first_name = "TestUser"

        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 67890

        update.message = Mock(spec=Message)
        update.message.reply_html = AsyncMock()
        update.message.text = "/ping"

        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock bot context."""
        context = Mock()
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context

    def test_bot_initialization(self, bot):
        """Test bot initializes correctly."""
        assert bot.token == "test_token"
        assert bot.application is None
        assert bot.db_service is None

    @pytest.mark.asyncio
    async def test_ping_command_success(self, bot, mock_update, mock_context):
        """Test /ping command responds correctly."""
        # Mock database service
        bot.db_service = Mock()
        bot.db_service.health_check = AsyncMock(return_value=True)

        await bot.ping_command(mock_update, mock_context)

        # Verify response was sent
        mock_update.message.reply_html.assert_called_once()
        call_args = mock_update.message.reply_html.call_args

        # Check response content
        response_text = call_args[0][0]
        assert "🏓 Pong!" in response_text
        assert "TestUser" in response_text
        assert "✅ Connected" in response_text

    @pytest.mark.asyncio
    async def test_ping_command_db_disconnected(self, bot, mock_update, mock_context):
        """Test /ping command with database disconnected."""
        # Mock database service as disconnected
        bot.db_service = Mock()
        bot.db_service.health_check = AsyncMock(return_value=False)

        await bot.ping_command(mock_update, mock_context)

        # Verify response contains disconnected status
        call_args = mock_update.message.reply_html.call_args
        response_text = call_args[0][0]
        assert "❌ Disconnected" in response_text

    @pytest.mark.asyncio
    async def test_start_command(self, bot, mock_update, mock_context):
        """Test /start command responds correctly."""
        await bot.start_command(mock_update, mock_context)

        # Verify response was sent
        mock_update.message.reply_html.assert_called_once()
        call_args = mock_update.message.reply_html.call_args

        # Check response content
        response_text = call_args[0][0]
        assert "Welcome to rSpotify Bot!" in response_text
        assert "TestUser" in response_text

    @pytest.mark.asyncio
    async def test_help_command(self, bot, mock_update, mock_context):
        """Test /help command responds correctly."""
        await bot.help_command(mock_update, mock_context)

        # Verify response was sent
        mock_update.message.reply_html.assert_called_once()
        call_args = mock_update.message.reply_html.call_args

        # Check response content
        response_text = call_args[0][0]
        assert "rSpotify Bot" in response_text
        assert "/ping" in response_text

    @pytest.mark.asyncio
    async def test_unknown_command(self, bot, mock_update, mock_context):
        """Test unknown command handler."""
        mock_update.message.text = "/unknown"

        await bot.unknown_command(mock_update, mock_context)

        # Verify error response was sent
        call_args = mock_update.message.reply_html.call_args
        response_text = call_args[0][0]
        assert "Unknown Command" in response_text
        assert "/unknown" in response_text

    @pytest.mark.asyncio
    async def test_error_handler_with_user_message(
        self, bot, mock_update, mock_context
    ):
        """Test error handler sends message to user."""
        mock_context.error = Exception("Test error")

        await bot.error_handler(mock_update, mock_context)

        # Verify error message was sent to user
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        response_text = call_args[0][0]
        assert "❌ **Oops! Something went wrong.**" in response_text

    @pytest.mark.asyncio
    @patch("rspotify_bot.config.Config.OWNER_TELEGRAM_ID", "999")
    async def test_error_handler_notifies_owner(self, bot, mock_update, mock_context):
        """Test error handler notifies bot owner."""
        mock_context.error = Exception("Test error")
        mock_context.bot.send_message = AsyncMock()

        await bot.error_handler(mock_update, mock_context)

        # Verify owner notification was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]["chat_id"] == "999"
        assert "Bot Error Alert" in call_args[1]["text"]

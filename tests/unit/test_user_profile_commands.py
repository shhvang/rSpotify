"""
Unit tests for user profile commands (Story 1.5).
Tests /me and /rename commands.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestMeCommand:
    """Test suite for /me command."""

    @pytest.mark.asyncio
    async def test_me_command_with_spotify_connected(self):
        """Test /me command when user has Spotify connected."""
        from rspotify_bot.handlers.user_commands import handle_me
        
        # Mock update and context
        update = MagicMock()
        context = MagicMock()
        
        # Mock user
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        # Mock message
        message = AsyncMock()
        update.message = message
        
        # Mock database service
        db_service = MagicMock()
        db_service.database = MagicMock()
        context.bot_data = {"db_service": db_service}
        
        # Mock user data with Spotify connected
        user_data = {
            "telegram_id": 123456789,
            "custom_name": "TestUser",
            "spotify": {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
            },
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        
        # Mock Spotify profile
        spotify_profile = {
            "display_name": "Test User",
            "product": "premium",
            "email": "test@example.com",
        }
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_user = AsyncMock(return_value=user_data)
            
            with patch("rspotify_bot.handlers.user_commands.SpotifyAuthService") as MockAuth:
                mock_auth = MockAuth.return_value
                mock_auth.get_user_profile = AsyncMock(return_value=spotify_profile)
                
                await handle_me(update, context)
        
        # Verify reply was sent
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "TestUser" in call_args
        assert "Connected" in call_args
        assert "Premium" in call_args

    @pytest.mark.asyncio
    async def test_me_command_without_spotify(self):
        """Test /me command when user doesn't have Spotify connected."""
        from rspotify_bot.handlers.user_commands import handle_me
        
        update = MagicMock()
        context = MagicMock()
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        update.message = message
        
        db_service = MagicMock()
        db_service.database = MagicMock()
        context.bot_data = {"db_service": db_service}
        
        # User data without Spotify
        user_data = {
            "telegram_id": 123456789,
            "custom_name": "TestUser",
            "spotify": None,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_user = AsyncMock(return_value=user_data)
            
            await handle_me(update, context)
        
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "TestUser" in call_args
        assert "Disconnected" in call_args

    @pytest.mark.asyncio
    async def test_me_command_user_not_found(self):
        """Test /me command when user profile doesn't exist."""
        from rspotify_bot.handlers.user_commands import handle_me
        
        update = MagicMock()
        context = MagicMock()
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        update.message = message
        
        db_service = MagicMock()
        db_service.database = MagicMock()
        context.bot_data = {"db_service": db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_user = AsyncMock(return_value=None)
            
            await handle_me(update, context)
        
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "Not Found" in call_args


class TestRenameCommand:
    """Test suite for /rename command."""

    @pytest.mark.asyncio
    async def test_rename_command_initiates_flow(self):
        """Test /rename command initiates rename flow."""
        from rspotify_bot.handlers.user_commands import handle_rename
        
        update = MagicMock()
        context = MagicMock()
        context.user_data = {}
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        update.message = message
        
        await handle_rename(update, context)
        
        # Verify prompt was sent
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "new custom display name" in call_args.lower() or "display name" in call_args.lower()
        
        # Verify state was set
        assert context.user_data.get("awaiting_rename") is True

    @pytest.mark.asyncio
    async def test_rename_command_rate_limit(self):
        """Test /rename command respects rate limiting."""
        from rspotify_bot.handlers.user_commands import handle_rename
        from datetime import timedelta
        
        update = MagicMock()
        context = MagicMock()
        
        # Set up rename history with 3 recent renames
        current_time = datetime.now(timezone.utc)
        context.user_data = {
            "rename_history": [
                current_time - timedelta(minutes=5),
                current_time - timedelta(minutes=10),
                current_time - timedelta(minutes=15),
            ]
        }
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        update.message = message
        
        await handle_rename(update, context)
        
        # Verify rate limit message was sent
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "Rate Limit" in call_args or "too many times" in call_args.lower()

    @pytest.mark.asyncio
    async def test_rename_input_valid_name(self):
        """Test rename input handler with valid name."""
        from rspotify_bot.handlers.user_commands import handle_rename_input
        
        update = MagicMock()
        context = MagicMock()
        context.user_data = {"awaiting_rename": True, "rename_history": []}
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        message.text = "NewName"
        update.message = message
        
        db_service = MagicMock()
        db_service.database = MagicMock()
        context.bot_data = {"db_service": db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.update_user = AsyncMock(return_value=True)
            
            await handle_rename_input(update, context)
        
        # Verify success message
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "NewName" in call_args
        assert "Updated" in call_args or "changed" in call_args.lower()
        
        # Verify state was cleared
        assert context.user_data.get("awaiting_rename") is False

    @pytest.mark.asyncio
    async def test_rename_input_invalid_name(self):
        """Test rename input handler with invalid name."""
        from rspotify_bot.handlers.user_commands import handle_rename_input
        
        update = MagicMock()
        context = MagicMock()
        context.user_data = {"awaiting_rename": True}
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        message.text = "ThisNameIsTooLong"  # More than 12 characters
        update.message = message
        
        await handle_rename_input(update, context)
        
        # Verify error message
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "Invalid" in call_args or "too long" in call_args.lower()
        
        # Verify state is still active for retry
        assert context.user_data.get("awaiting_rename") is True

    @pytest.mark.asyncio
    async def test_rename_input_cancel(self):
        """Test rename input handler with cancel command."""
        from rspotify_bot.handlers.user_commands import handle_rename_input
        
        update = MagicMock()
        context = MagicMock()
        context.user_data = {"awaiting_rename": True}
        
        user = MagicMock()
        user.id = 123456789
        update.effective_user = user
        
        message = AsyncMock()
        message.text = "/cancel"
        update.message = message
        
        await handle_rename_input(update, context)
        
        # Verify cancelled message
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        
        assert "Cancel" in call_args
        
        # Verify state was cleared
        assert context.user_data.get("awaiting_rename") is False


class TestSpotifyProfileFetching:
    """Test suite for Spotify profile fetching."""

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self):
        """Test successful Spotify profile fetch."""
        from rspotify_bot.services.auth import SpotifyAuthService
        import httpx
        
        auth_service = SpotifyAuthService()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "display_name": "Test User",
            "email": "test@example.com",
            "product": "premium",
            "country": "US",
            "id": "spotify_user_123",
        }
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            profile = await auth_service.get_user_profile("test_token")
        
        assert profile["display_name"] == "Test User"
        assert profile["product"] == "premium"
        assert profile["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_profile_expired_token(self):
        """Test Spotify profile fetch with expired token."""
        from rspotify_bot.services.auth import SpotifyAuthService
        
        auth_service = SpotifyAuthService()
        
        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(Exception, match="expired or invalid"):
                await auth_service.get_user_profile("expired_token")

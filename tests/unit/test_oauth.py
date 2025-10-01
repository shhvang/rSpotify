"""
Unit tests for Spotify OAuth functionality.
Tests for OAuth flow, temporary storage, and middleware.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

from rspotify_bot.services.auth import SpotifyAuthService
from rspotify_bot.services.middleware import (
    TemporaryStorage,
    get_temporary_storage,
    require_spotify_auth,
)


class TestSpotifyAuthService:
    """Test cases for Spotify OAuth service."""

    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    def test_spotify_auth_service_init(self):
        """Test SpotifyAuthService initialization."""
        service = SpotifyAuthService()
        assert service.client_id == "test_client_id"
        assert service.client_secret == "test_secret"
        assert service.redirect_uri == "https://test.com/callback"

    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    def test_spotify_auth_service_init_missing_credentials(self):
        """Test SpotifyAuthService initialization fails without credentials."""
        with pytest.raises(ValueError, match="SPOTIFY_CLIENT_ID"):
            SpotifyAuthService()

    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI", "")
    def test_spotify_auth_service_init_missing_redirect_uri(self):
        """Test SpotifyAuthService initialization fails without redirect URI."""
        with pytest.raises(ValueError, match="SPOTIFY_REDIRECT_URI"):
            SpotifyAuthService()

    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    def test_get_authorization_url(self):
        """Test generating authorization URL."""
        service = SpotifyAuthService()
        state = "test_state_123"
        auth_url = service.get_authorization_url(state)

        # Verify URL components
        assert "https://accounts.spotify.com/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "redirect_uri=https://test.com/callback" in auth_url
        assert "state=test_state_123" in auth_url
        assert "scope=" in auth_url
        assert "user-read-currently-playing" in auth_url
        assert "user-modify-playback-state" in auth_url

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    async def test_exchange_code_for_tokens_success(self):
        """Test successful authorization code exchange."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch ClientSession
        with patch("rspotify_bot.services.auth.aiohttp.ClientSession", return_value=mock_session):
            service = SpotifyAuthService()
            result = await service.exchange_code_for_tokens("auth_code_123")

            # Verify tokens returned
            assert result["access_token"] == "test_access_token"
            assert result["refresh_token"] == "test_refresh_token"
            assert "expires_at" in result
            assert isinstance(result["expires_at"], datetime)

            # Verify API was called correctly
            assert mock_session.post.called

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    async def test_exchange_code_for_tokens_failure(self):
        """Test failed authorization code exchange."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid code")
        mock_response.json = AsyncMock(return_value={
            "error": "invalid_grant",
            "error_description": "Invalid authorization code",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch ClientSession
        with patch("rspotify_bot.services.auth.aiohttp.ClientSession", return_value=mock_session):
            service = SpotifyAuthService()

            with pytest.raises(Exception, match="Token exchange failed"):
                await service.exchange_code_for_tokens("invalid_code")

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    async def test_refresh_access_token_success(self):
        """Test successful token refresh."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch ClientSession
        with patch("rspotify_bot.services.auth.aiohttp.ClientSession", return_value=mock_session):
            service = SpotifyAuthService()
            result = await service.refresh_access_token("old_refresh_token")

            # Verify new tokens returned
            assert result["access_token"] == "new_access_token"
            assert result["refresh_token"] == "new_refresh_token"
            assert "expires_at" in result

            # Verify API was called correctly
            assert mock_session.post.called

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    async def test_refresh_access_token_invalid_grant(self):
        """Test token refresh with expired refresh token."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid refresh token")
        mock_response.json = AsyncMock(return_value={
            "error": "invalid_grant",
            "error_description": "Refresh token expired",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Patch ClientSession
        with patch("rspotify_bot.services.auth.aiohttp.ClientSession", return_value=mock_session):
            service = SpotifyAuthService()

            with pytest.raises(Exception, match="Refresh token expired"):
                await service.refresh_access_token("expired_refresh_token")

    @pytest.mark.asyncio
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_ID", "test_client_id")
    @patch("rspotify_bot.services.auth.Config.SPOTIFY_CLIENT_SECRET", "test_secret")
    @patch(
        "rspotify_bot.services.auth.Config.SPOTIFY_REDIRECT_URI",
        "https://test.com/callback",
    )
    async def test_revoke_token(self):
        """Test token revocation (placeholder implementation)."""
        service = SpotifyAuthService()
        result = await service.revoke_token("test_token")

        # Current implementation returns True (placeholder)
        assert result is True


class TestTemporaryStorage:
    """Test cases for temporary storage with TTL."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test storing and retrieving values."""
        storage = TemporaryStorage()
        await storage.set("test_key", "test_value", expiry_seconds=60)

        value = await storage.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test retrieving nonexistent key returns None."""
        storage = TemporaryStorage()
        value = await storage.get("nonexistent_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_expiry(self):
        """Test that values expire after TTL."""
        storage = TemporaryStorage()
        # Set with 1 second expiry
        await storage.set("test_key", "test_value", expiry_seconds=1)

        # Should be available immediately
        value = await storage.get("test_key")
        assert value == "test_value"

        # Wait for expiry
        await asyncio.sleep(1.1)

        # Should be expired now
        value = await storage.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a key."""
        storage = TemporaryStorage()
        await storage.set("test_key", "test_value")

        # Delete the key
        result = await storage.delete("test_key")
        assert result is True

        # Key should no longer exist
        value = await storage.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Test deleting nonexistent key returns False."""
        storage = TemporaryStorage()
        result = await storage.delete("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        """Test that cleanup task removes expired entries."""
        storage = TemporaryStorage()

        # Add multiple entries with short TTL
        await storage.set("key1", "value1", expiry_seconds=1)
        await storage.set("key2", "value2", expiry_seconds=1)
        await storage.set("key3", "value3", expiry_seconds=10)

        # Start cleanup task
        await storage.start_cleanup_task()

        # Wait for entries to expire
        await asyncio.sleep(1.5)

        # Trigger cleanup manually
        await storage._cleanup_expired()

        # Expired keys should be gone
        assert await storage.get("key1") is None
        assert await storage.get("key2") is None

        # Non-expired key should still exist
        assert await storage.get("key3") == "value3"

        # Stop cleanup task
        await storage.stop_cleanup_task()

    def test_get_temporary_storage_singleton(self):
        """Test that get_temporary_storage returns singleton instance."""
        storage1 = get_temporary_storage()
        storage2 = get_temporary_storage()
        assert storage1 is storage2


class TestLoginCommandHandler:
    """Test cases for /login command handler."""

    @pytest.mark.asyncio
    @patch("rspotify_bot.handlers.user_commands.get_temporary_storage")
    @patch("rspotify_bot.handlers.user_commands.SpotifyAuthService")
    @patch("rspotify_bot.handlers.user_commands.UserRepository")
    async def test_login_new_user(
        self, mock_repo_class, mock_auth_service_class, mock_temp_storage
    ):
        """Test /login for new user without Spotify connected."""
        from rspotify_bot.handlers.user_commands import handle_login

        # Mock user and update
        user = User(id=12345, first_name="Test", is_bot=False)
        chat = Chat(id=1, type="private")
        message = Mock()
        message.reply_html = AsyncMock()

        update = Mock(spec=Update)
        update.effective_user = user
        update.message = message

        # Mock database service
        mock_db = Mock()
        mock_db.database = Mock()
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {"db_service": mock_db}
        context.bot = Mock()

        # Mock repository - user doesn't exist
        mock_repo = Mock()
        mock_repo.get_user = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        # Mock temp storage
        mock_storage = Mock()
        mock_storage.set = AsyncMock()
        mock_temp_storage.return_value = mock_storage

        # Mock auth service
        mock_auth = Mock()
        mock_auth.get_authorization_url = Mock(return_value="https://spotify.com/auth")
        mock_auth_service_class.return_value = mock_auth

        # Execute
        await handle_login(update, context)

        # Verify authorization URL was sent
        message.reply_html.assert_called_once()
        call_args = message.reply_html.call_args[0][0]
        assert "Connect Your Spotify Account" in call_args
        assert "https://spotify.com/auth" in call_args

        # Verify state was stored
        mock_storage.set.assert_called_once()

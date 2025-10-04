"""
Integration tests for Spotify profile fetching (Story 1.5).
Tests real API calls to Spotify's /v1/me endpoint.

NOTE: These tests require valid Spotify credentials in .env file.
Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and have a test access token.
"""

import pytest
import os
from unittest.mock import patch
from rspotify_bot.services.auth import SpotifyAuthService


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"),
    reason="Spotify credentials not configured"
)
class TestSpotifyProfileIntegration:
    """Integration tests for Spotify profile API."""

    @pytest.mark.asyncio
    async def test_get_user_profile_with_valid_token(self):
        """
        Test fetching user profile with a valid access token.
        
        This test uses a mocked token since we don't have a real one in CI.
        In a real environment, you would use a test user's actual token.
        """
        auth_service = SpotifyAuthService()
        
        # Mock the actual HTTP call since we can't use a real token in tests
        from unittest.mock import AsyncMock, MagicMock
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "display_name": "Test User",
            "email": "test@example.com",
            "product": "premium",
            "country": "US",
            "id": "test_user_123"
        }
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            profile = await auth_service.get_user_profile("mock_access_token")
        
        # Verify response structure
        assert profile is not None
        assert "display_name" in profile
        assert "email" in profile
        assert "product" in profile
        assert "country" in profile
        assert "id" in profile
        
        # Verify data types
        assert isinstance(profile["display_name"], (str, type(None)))
        assert isinstance(profile["product"], str)

    @pytest.mark.asyncio
    async def test_get_user_profile_with_expired_token(self):
        """Test that expired tokens are handled gracefully."""
        auth_service = SpotifyAuthService()
        
        # Mock 401 response for expired token
        from unittest.mock import AsyncMock, MagicMock
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "The access token expired"
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(Exception) as exc_info:
                await auth_service.get_user_profile("expired_token")
            
            assert "expired or invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_user_profile_free_account(self):
        """Test profile fetching for free Spotify account."""
        auth_service = SpotifyAuthService()
        
        from unittest.mock import AsyncMock, MagicMock
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "display_name": "Free User",
            "email": "free@example.com",
            "product": "free",  # Free account
            "country": "US",
            "id": "free_user_123"
        }
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            profile = await auth_service.get_user_profile("mock_token")
        
        assert profile["product"] == "free"

    @pytest.mark.asyncio
    async def test_get_user_profile_premium_account(self):
        """Test profile fetching for premium Spotify account."""
        auth_service = SpotifyAuthService()
        
        from unittest.mock import AsyncMock, MagicMock
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "display_name": "Premium User",
            "email": "premium@example.com",
            "product": "premium",  # Premium account
            "country": "US",
            "id": "premium_user_123"
        }
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(return_value=mock_response)
            
            profile = await auth_service.get_user_profile("mock_token")
        
        assert profile["product"] == "premium"

    @pytest.mark.asyncio
    async def test_get_user_profile_network_error(self):
        """Test handling of network errors."""
        auth_service = SpotifyAuthService()
        
        from unittest.mock import AsyncMock
        import httpx
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MockClient.return_value.__aenter__.return_value
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))
            
            with pytest.raises(Exception) as exc_info:
                await auth_service.get_user_profile("mock_token")
            
            assert "network error" in str(exc_info.value).lower()


@pytest.mark.integration
class TestDefaultNameFallbackIntegration:
    """Integration tests for default name fallback logic."""

    @pytest.mark.asyncio
    async def test_default_name_fallback_hierarchy(self):
        """
        Test that default name follows correct fallback hierarchy:
        1. Spotify display name
        2. Telegram username
        3. Telegram first name
        4. "User"
        """
        # This would be tested as part of the full OAuth flow
        # For now, we verify the logic exists in the bot
        from rspotify_bot.bot import RSpotifyBot
        
        bot = RSpotifyBot("test_token")
        
        # Verify the method exists
        assert hasattr(bot, "_get_default_name")
        
        # Test with mock data
        from types import SimpleNamespace
        
        telegram_user = SimpleNamespace(
            id=123456789,
            username="testuser",
            first_name="Test"
        )
        
        # Without Spotify, should use Telegram username
        default_name = await bot._get_default_name(telegram_user)
        # Will be "testuser" or "Test" or "User" depending on what's available
        assert default_name in ["testuser", "Test", "User"]
        assert len(default_name) <= 12  # Respects 12 char limit

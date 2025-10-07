"""Integration tests for Spotify OAuth flow.

Tests OAuth callback endpoint, token exchange, and database integration.
These tests use mocked Spotify API responses but real database operations.
"""

import os
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime, timedelta

# Skip tests if Spotify credentials not configured (e.g., in CI/CD)
skip_if_no_credentials = pytest.mark.skipif(
    not os.getenv('SPOTIFY_CLIENT_ID') or not os.getenv('SPOTIFY_CLIENT_SECRET'),
    reason="Spotify credentials not configured"
)


class TestOAuthIntegration:
    """Integration tests for complete OAuth flow."""

    @skip_if_no_credentials
    @pytest.mark.asyncio
    async def test_oauth_callback_success_flow(self):
        """Test successful OAuth callback with token exchange."""
        from rspotify_bot.services.auth import SpotifyAuthService
        from rspotify_bot.services.middleware import get_temporary_storage
        
        # Setup
        temp_storage = get_temporary_storage()
        test_state = "test_state_123"
        test_telegram_id = 123456789
        
        # Store state
        await temp_storage.set(f"oauth_state_{test_state}", test_telegram_id, 300)
        
        # Mock Spotify API response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        })
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            auth_service = SpotifyAuthService()
            tokens = await auth_service.exchange_code_for_tokens("mock_code")
            
            assert tokens["access_token"] == "mock_access_token"
            assert tokens["refresh_token"] == "mock_refresh_token"
            assert "expires_at" in tokens  # Method returns expires_at, not expires_in

    @pytest.mark.asyncio
    async def test_temporary_storage_expiry(self):
        """Test temporary storage expiry in real-time scenario."""
        from rspotify_bot.services.middleware import get_temporary_storage
        
        temp_storage = get_temporary_storage()
        
        # Store with 1 second expiry
        await temp_storage.set("test_key", "test_value", expiry_seconds=1)
        
        # Should exist immediately
        value = await temp_storage.get("test_key")
        assert value == "test_value"
        
        # Wait for expiry
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await temp_storage.get("test_key")
        assert value is None

    @skip_if_no_credentials
    @pytest.mark.asyncio
    async def test_authorization_url_generation(self):
        """Test Spotify authorization URL contains required parameters."""
        from rspotify_bot.services.auth import SpotifyAuthService
        
        auth_service = SpotifyAuthService()
        state = "test_state_789"
        auth_url = auth_service.get_authorization_url(state)
        
        # Verify URL structure
        assert "accounts.spotify.com/authorize" in auth_url
        assert f"state={state}" in auth_url
        assert "scope=" in auth_url
        assert "user-read-currently-playing" in auth_url
        assert "response_type=code" in auth_url


class TestOAuthErrorHandling:
    """Integration tests for OAuth error scenarios."""

    @skip_if_no_credentials
    @pytest.mark.asyncio
    async def test_invalid_authorization_code(self):
        """Test handling of invalid authorization code."""
        from rspotify_bot.services.auth import SpotifyAuthService
        
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid authorization code"
        mock_response.json = Mock(return_value={
            "error": "invalid_grant",
            "error_description": "Invalid authorization code"
        })
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            auth_service = SpotifyAuthService()
            
            with pytest.raises(Exception):
                await auth_service.exchange_code_for_tokens("invalid_code")

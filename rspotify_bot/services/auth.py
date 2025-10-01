"""
Owner authorization and Spotify OAuth service for rSpotify Bot.
Provides decorators for owner-only commands and Spotify OAuth token management.
"""

import logging
import httpx
from functools import wraps
from typing import Callable, Any, Dict, Optional
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ContextTypes

from ..config import Config

logger = logging.getLogger(__name__)


def owner_only(func: Callable) -> Callable:
    """
    Decorator to restrict command access to bot owner only.

    Args:
        func: The command handler function to wrap

    Returns:
        Wrapped function that checks owner authorization
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """
        Wrapper function that checks if user is the bot owner.

        Args:
            update: Telegram update object
            context: Bot context

        Returns:
            Result of wrapped function if authorized, None otherwise
        """
        user = update.effective_user
        owner_id = Config.OWNER_TELEGRAM_ID

        if not update.message:
            logger.error("No message in update")
            return None

        if not owner_id:
            logger.error("OWNER_TELEGRAM_ID not configured")
            await update.message.reply_html(
                "<b>⚠️ Configuration Error</b>\n"
                "<i>Owner authentication not properly configured.</i>"
            )
            return None

        if not user or str(user.id) != owner_id:
            logger.warning(
                f"Unauthorized access attempt from user {user.id if user else 'Unknown'}"
            )
            await update.message.reply_html(
                "<b>🚫 Access Denied</b>\n"
                "<i>This command is restricted to the bot owner only.</i>"
            )
            return None

        logger.info(f"Owner command access granted to user {user.id}")
        return await func(update, context)

    return wrapper


async def is_owner(user_id: int) -> bool:
    """
    Check if a user ID matches the configured owner ID.

    Args:
        user_id: Telegram user ID to check

    Returns:
        True if user is owner, False otherwise
    """
    owner_id = Config.OWNER_TELEGRAM_ID
    if not owner_id:
        logger.error("OWNER_TELEGRAM_ID not configured")
        return False

    return str(user_id) == owner_id


def get_owner_id() -> str:
    """
    Get the configured owner Telegram ID.

    Returns:
        Owner Telegram ID as string, empty if not configured
    """
    return Config.OWNER_TELEGRAM_ID


class SpotifyAuthService:
    """Service for Spotify OAuth token management."""

    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
    SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"

    # Required Spotify scopes for the bot
    REQUIRED_SCOPES = [
        "user-read-currently-playing",
        "user-modify-playback-state",
        "user-read-playback-state",
        "playlist-modify-public",
        "playlist-modify-private",
    ]

    def __init__(self):
        """Initialize Spotify auth service."""
        self.client_id = Config.SPOTIFY_CLIENT_ID
        self.client_secret = Config.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = Config.SPOTIFY_REDIRECT_URI

        if not self.client_id or not self.client_secret:
            logger.error("Spotify credentials not configured")
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")

        if not self.redirect_uri:
            logger.error("Spotify redirect URI not configured")
            raise ValueError("SPOTIFY_REDIRECT_URI must be set")

    def get_authorization_url(self, state: str) -> str:
        """
        Build Spotify authorization URL.

        Args:
            state: Security state parameter

        Returns:
            Full authorization URL for user to click
        """
        scope = " ".join(self.REQUIRED_SCOPES)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": scope,
        }

        # Build query string
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{self.SPOTIFY_AUTHORIZE_URL}?{query_params}"

        logger.debug(f"Generated authorization URL with state: {state}")
        return auth_url

    async def exchange_code_for_tokens(
        self, authorization_code: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            authorization_code: Authorization code from Spotify callback

        Returns:
            Dict with access_token, refresh_token, and expires_at

        Raises:
            Exception: If token exchange fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.SPOTIFY_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self.redirect_uri,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    error_data = await response.json() if response.text else {}
                    error_msg = error_data.get("error_description", response.text)
                    logger.error(
                        f"Token exchange failed: {response.status_code} - {error_msg}"
                    )
                    raise Exception(f"Token exchange failed: {error_msg}")

                data = await response.json()

                # Calculate expiration timestamp
                expires_in = data.get("expires_in", 3600)  # Default 1 hour
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                logger.info("Successfully exchanged authorization code for tokens")

                return {
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                    "expires_at": expires_at,
                }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token exchange: {e}")
            raise Exception(f"Network error during token exchange: {e}")

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            Dict with new access_token, refresh_token, and expires_at

        Raises:
            Exception: If token refresh fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.SPOTIFY_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    error_data = await response.json() if response.text else {}
                    error_msg = error_data.get("error_description", response.text)
                    logger.error(
                        f"Token refresh failed: {response.status_code} - {error_msg}"
                    )

                    # Check for invalid_grant error (refresh token expired)
                    if error_data.get("error") == "invalid_grant":
                        raise Exception(
                            "Refresh token expired. User needs to re-authenticate."
                        )

                    raise Exception(f"Token refresh failed: {error_msg}")

                data = await response.json()

                # Calculate expiration timestamp
                expires_in = data.get("expires_in", 3600)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                # Spotify may or may not return a new refresh token
                new_refresh_token = data.get("refresh_token", refresh_token)

                logger.info("Successfully refreshed access token")

                return {
                    "access_token": data["access_token"],
                    "refresh_token": new_refresh_token,
                    "expires_at": expires_at,
                }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token refresh: {e}")
            raise Exception(f"Network error during token refresh: {e}")

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a Spotify token (best effort - Spotify doesn't officially support revocation).

        Args:
            token: Token to revoke (access or refresh token)

        Returns:
            True if successful or endpoint not available, False on error
        """
        # Note: Spotify doesn't officially support token revocation via API
        # Tokens expire naturally after 1 hour (access) or are invalidated when user revokes permissions
        # This is a placeholder for future implementation if Spotify adds official revocation
        logger.info("Token revocation requested (Spotify doesn't officially support revocation)")
        return True

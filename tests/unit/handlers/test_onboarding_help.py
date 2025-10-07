"""
Unit tests for onboarding and help command handlers.
Tests /start, /help, /privacy commands and related callbacks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from telegram import Update, User, Message, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from rspotify_bot.handlers.user_commands import (
    handle_start,
    handle_help,
    handle_help_category,
    handle_privacy,
    handle_start_login_callback,
    get_user_capabilities,
)


class TestHandleStart:
    """Tests for handle_start command."""
    
    @pytest.mark.asyncio
    async def test_start_new_user(self):
        """Test /start for new user without authentication."""
        # Setup mocks
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456789
        update.effective_user.first_name = "TestUser"
        update.message = MagicMock(spec=Message)
        update.message.reply_html = AsyncMock()
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_user.return_value = None
            mock_repo.create_user = AsyncMock()
            mock_repo.log_command = AsyncMock()
            
            await handle_start(update, context)
            
            # Verify user was created
            mock_repo.create_user.assert_called_once()
            
            # Verify message was sent
            update.message.reply_html.assert_called_once()
            call_args = update.message.reply_html.call_args
            message_text = call_args[0][0]
            
            assert "Welcome to rSpotify Bot" in message_text
            assert "reply_markup" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_start_authenticated_user(self):
        """Test /start for authenticated user."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456789
        update.effective_user.first_name = "TestUser"
        update.message = MagicMock(spec=Message)
        update.message.reply_html = AsyncMock()
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_user.return_value = {
                "telegram_id": 123456789,
                "spotify": {"access_token": "test_token"}
            }
            mock_repo.log_command = AsyncMock()
            
            await handle_start(update, context)
            
            # Verify message mentions connection
            update.message.reply_html.assert_called_once()
            call_args = update.message.reply_html.call_args
            message_text = call_args[0][0]
            
            assert "Welcome Back" in message_text or "connected" in message_text.lower()


class TestHandleHelp:
    """Tests for handle_help command."""
    
    @pytest.mark.asyncio
    async def test_help_shows_main_menu(self):
        """Test /help displays main menu."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456789
        update.message = MagicMock(spec=Message)
        update.message.reply_html = AsyncMock()
        update.callback_query = None
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.log_command = AsyncMock()
            
            with patch("rspotify_bot.handlers.user_commands.get_user_capabilities") as mock_caps:
                mock_caps.return_value = {"authenticated": False, "premium": False}
                
                await handle_help(update, context)
                
                update.message.reply_html.assert_called_once()
                call_args = update.message.reply_html.call_args
                message_text = call_args[0][0]
                
                assert "Help" in message_text
                assert "reply_markup" in call_args[1]


class TestHandlePrivacy:
    """Tests for handle_privacy command."""
    
    @pytest.mark.asyncio
    async def test_privacy_displays_policy(self):
        """Test /privacy displays privacy policy."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456789
        update.message = MagicMock(spec=Message)
        update.message.reply_html = AsyncMock()
        update.callback_query = None
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.log_command = AsyncMock()
            
            await handle_privacy(update, context)
            
            update.message.reply_html.assert_called_once()
            call_args = update.message.reply_html.call_args
            message_text = call_args[0][0]
            
            assert "Privacy Policy" in message_text
            assert "Data We Collect" in message_text


class TestGetUserCapabilities:
    """Tests for get_user_capabilities helper."""
    
    @pytest.mark.asyncio
    async def test_capabilities_unauthenticated(self):
        """Test capabilities for unauthenticated user."""
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_user.return_value = None
            
            caps = await get_user_capabilities(123456789, mock_db_service)
            
            assert caps["authenticated"] is False
            assert caps["premium"] is False
    
    @pytest.mark.asyncio
    async def test_capabilities_authenticated_premium(self):
        """Test capabilities for authenticated Premium user."""
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_user.return_value = {
                "telegram_id": 123456789,
                "spotify": {"access_token": "test_token"}
            }
            
            with patch("rspotify_bot.handlers.user_commands.SpotifyAuthService") as mock_auth_class:
                mock_auth = AsyncMock()
                mock_auth_class.return_value = mock_auth
                mock_auth.get_user_profile.return_value = {"product": "premium"}
                
                caps = await get_user_capabilities(123456789, mock_db_service)
                
                assert caps["authenticated"] is True
                assert caps["premium"] is True

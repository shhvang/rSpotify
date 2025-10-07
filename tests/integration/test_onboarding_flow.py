"""
Integration tests for onboarding and help flow.
Tests complete user journeys through the help system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from rspotify_bot.handlers.user_commands import (
    handle_start,
    handle_help,
    handle_help_category,
    handle_privacy,
)


@pytest.mark.integration
class TestOnboardingIntegration:
    """Integration tests for onboarding flow."""
    
    @pytest.mark.asyncio
    async def test_complete_onboarding_flow(self):
        """Test complete onboarding flow from start to help."""
        # Step 1: New user sends /start
        update = MagicMock()
        context = MagicMock()
        
        update.effective_user = MagicMock()
        update.effective_user.id = 999999999
        update.effective_user.first_name = "NewUser"
        update.message = MagicMock()
        update.message.reply_html = AsyncMock()
        update.callback_query = None
        
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_user.return_value = None
            mock_repo.create_user = AsyncMock()
            mock_repo.log_command = AsyncMock()
            
            # Execute /start
            await handle_start(update, context)
            
            # Verify new user was created
            mock_repo.create_user.assert_called_once_with(999999999, "NewUser")
            
            # Verify welcome message sent
            assert update.message.reply_html.called
            
        # Step 2: User clicks Help button
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.log_command = AsyncMock()
            
            with patch("rspotify_bot.handlers.user_commands.get_user_capabilities") as mock_caps:
                mock_caps.return_value = {"authenticated": False, "premium": False}
                
                # Reset mock
                update.message.reply_html.reset_mock()
                
                await handle_help(update, context)
                
                # Verify help menu shown
                assert update.message.reply_html.called
    
    @pytest.mark.asyncio
    async def test_help_navigation_flow(self):
        """Test navigating through help categories."""
        update = MagicMock()
        context = MagicMock()
        
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.message = MagicMock()
        update.callback_query.message.edit_text = AsyncMock()
        update.callback_query.data = "help_category_getting_started"
        update.message = None
        
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.get_user_capabilities") as mock_caps:
            mock_caps.return_value = {"authenticated": False, "premium": False}
            
            # Navigate to category
            await handle_help_category(update, context)
            
            # Verify category content shown
            update.callback_query.message.edit_text.assert_called_once()
            call_args = update.callback_query.message.edit_text.call_args
            message_text = call_args[0][0]
            
            assert "Getting Started" in message_text
            assert "reply_markup" in call_args[1]


@pytest.mark.integration
class TestPrivacyIntegration:
    """Integration tests for privacy policy access."""
    
    @pytest.mark.asyncio
    async def test_privacy_access_flow(self):
        """Test accessing privacy policy from multiple entry points."""
        update = MagicMock()
        context = MagicMock()
        
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_html = AsyncMock()
        update.callback_query = None
        
        mock_db_service = MagicMock()
        mock_db_service.database = MagicMock()
        context.bot_data = {"db_service": mock_db_service}
        
        with patch("rspotify_bot.handlers.user_commands.UserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.log_command = AsyncMock()
            
            # Access privacy policy
            await handle_privacy(update, context)
            
            # Verify policy displayed
            update.message.reply_html.assert_called_once()
            call_args = update.message.reply_html.call_args
            message_text = call_args[0][0]
            
            assert "Privacy Policy" in message_text
            assert "Data We Collect" in message_text
            assert "/logout" in message_text

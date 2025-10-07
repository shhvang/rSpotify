"""
User command handlers for rSpotify Bot.
Handles user-facing commands like /login, /logout for Spotify authentication and data privacy.
"""

import logging
import secrets
from typing import Any, Optional, cast
from telegram import Message, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from ..services.database import DatabaseService
from ..services.repository import UserRepository, RepositoryError
from ..services.validation import escape_html
from ..services.auth import SpotifyAuthService
from ..services.middleware import get_temporary_storage

logger = logging.getLogger(__name__)


async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /login command to initiate Spotify OAuth flow.

    Generates a secure state parameter, stores it with the user's telegram_id,
    and sends the Spotify authorization URL to the user.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user

    if not user:
        return

    telegram_id = user.id
    user_name = escape_html(user.first_name or "User")

    logger.info(f"User {telegram_id} initiated Spotify login flow")

    if not update.message:
        return

    try:
        # Check if user already has Spotify connected
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        if db_service is None or db_service.database is None:
            await update.message.reply_html(
                "<b>❌ Error</b>\n\n"
                "Service temporarily unavailable. Please try again later."
            )
            return

        user_repo = UserRepository(db_service.database)
        existing_user = await user_repo.get_user(telegram_id)

        if existing_user and existing_user.get("spotify", {}).get("access_token"):
            await update.message.reply_html(
                f"<b>ℹ️ Already Connected</b>\n\n"
                f"Hello <b>{user_name}</b>!\n\n"
                f"Your Spotify account is already connected.\n"
                f"Use /logout to disconnect and connect a different account."
            )
            return

        # Generate secure state parameter
        state = secrets.token_urlsafe(16)

        # Store state with telegram_id in temporary storage (5 minutes expiry)
        temp_storage = get_temporary_storage()
        await temp_storage.set(f"oauth_state_{state}", telegram_id, expiry_seconds=300)

        # Create Spotify auth service and get authorization URL
        auth_service = SpotifyAuthService()
        auth_url = auth_service.get_authorization_url(state)

        # Send authorization URL to user with inline button
        message = (
            f"<b>🎵 Connect Your Spotify Account</b>\n\n"
            f"Hi <b>{user_name}</b>! To use rSpotify Bot, please authorize access to your Spotify account.\n\n"
            f"<b>Permissions needed:</b>\n"
            f"• 🎧 View currently playing\n"
            f"• ⏯️ Control playback\n"
            f"• 📋 Manage playlists\n\n"
            f"<i>⚠️ Link expires in 5 minutes</i>"
        )

        # Create inline keyboard with authorization button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Authorize Spotify", url=auth_url)]
        ])

        await update.message.reply_html(message, reply_markup=keyboard)

        logger.info(f"Sent authorization URL to user {telegram_id} with state: {state}")

    except ValueError as e:
        logger.error(f"Configuration error in /login: {e}")
        await update.message.reply_html(
            "<b>❌ Configuration Error</b>\n\n"
            "Spotify OAuth is not properly configured. Please contact the bot administrator."
        )
    except Exception as e:
        logger.error(f"Error in /login handler: {e}")
        await update.message.reply_html(
            "<b>❌ Error</b>\n\n"
            "An unexpected error occurred. Please try again later."
        )

        # Notify owner of error
        try:
            from ..config import config

            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=f"<b>⚠️ Error in /login</b>\n\n"
                f"User: {telegram_id}\n"
                f"Error: {escape_html(str(e))}",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def handle_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /logout command for data deletion and privacy compliance.

    This command allows users to:
    - Delete all personal data from the database
    - Revoke Spotify OAuth tokens
    - Clear usage logs and cached data

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user

    if not user:
        return

    telegram_id = user.id
    user_name = escape_html(user.first_name or "User")

    logger.info(f"User {telegram_id} requested data deletion via /logout")

    # Create confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Yes, Delete My Data", callback_data=f"logout_confirm_{telegram_id}"
            ),
            InlineKeyboardButton(
                "❌ Cancel", callback_data=f"logout_cancel_{telegram_id}"
            ),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if not update.message:
        return

    # Send confirmation message
    message = (
        f"<b>🔐 Data Deletion Request</b>\n\n"
        f"Hello <b>{user_name}</b>!\n\n"
        f"You have requested to delete all your data from rSpotify Bot. "
        f"This action will:\n\n"
        f"• Delete your user profile\n"
        f"• Remove all Spotify OAuth tokens\n"
        f"• Clear your usage history and logs\n"
        f"• Remove cached search results\n\n"
        f"<b>⚠️ This action cannot be undone!</b>\n\n"
        f"Are you sure you want to proceed?"
    )

    await update.message.reply_text(
        message, parse_mode="HTML", reply_markup=reply_markup
    )


async def handle_logout_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle logout confirmation callback.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = update.effective_user
    if not user:
        return

    telegram_id = user.id
    callback_data = query.data

    if not callback_data or not isinstance(callback_data, str):
        return

    # Parse callback data
    if callback_data.startswith("logout_confirm_"):
        # User confirmed deletion
        requested_id = int(callback_data.split("_")[-1])

        # Security check: ensure user is deleting their own data
        if requested_id != telegram_id:
            await query.edit_message_text(
                "<b>❌ Error</b>\n\nYou can only delete your own data.",
                parse_mode="HTML",
            )
            return

        # Perform data deletion
        try:
            db_service = cast(DatabaseService, context.bot_data.get("db_service"))

            if db_service is None or db_service.database is None:
                await query.edit_message_text(
                    "<b>❌ Error</b>\n\nDatabase service unavailable. Please try again later.",
                    parse_mode="HTML",
                )
                return

            # Create repository instance
            user_repo = UserRepository(db_service.database)

            # Get user data to retrieve Spotify tokens for revocation
            user_data = await user_repo.get_user(telegram_id)

            # Revoke Spotify tokens if present
            if user_data and user_data.get("spotify"):
                try:
                    auth_service = SpotifyAuthService()
                    access_token = user_data["spotify"].get("access_token")
                    if access_token:
                        await auth_service.revoke_token(access_token)
                        logger.info(f"Revoked Spotify tokens for user {telegram_id}")
                except Exception as e:
                    # Continue with deletion even if revocation fails
                    logger.warning(f"Failed to revoke tokens for user {telegram_id}: {e}")

            # Delete user data (cascade delete handles all associated data)
            success = await user_repo.delete_user(telegram_id)

            if success:
                logger.info(f"Successfully deleted all data for user {telegram_id}")

                message = (
                    "<b>✅ Data Deleted Successfully</b>\n\n"
                    "All your data has been permanently removed from rSpotify Bot:\n\n"
                    "• User profile deleted\n"
                    "• Spotify tokens revoked\n"
                    "• Usage history cleared\n"
                    "• Cached data removed\n\n"
                    "Thank you for using rSpotify Bot. "
                    "You can start fresh anytime by using /start command."
                )

                await query.edit_message_text(message, parse_mode="HTML")
            else:
                logger.warning(f"No data found to delete for user {telegram_id}")

                await query.edit_message_text(
                    "<b>ℹ️ No Data Found</b>\n\n"
                    "You don't have any data stored in our system.",
                    parse_mode="HTML",
                )

        except RepositoryError as e:
            logger.error(f"Repository error during logout: {e}")
            await query.edit_message_text(
                f"<b>❌ Error</b>\n\nFailed to delete data: {escape_html(str(e))}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Unexpected error during logout: {e}")

            # Notify owner of error
            try:
                from ..config import config

                await context.bot.send_message(
                    chat_id=config.OWNER_TELEGRAM_ID,
                    text=f"<b>⚠️ Error in /logout</b>\n\n"
                    f"User: {telegram_id}\n"
                    f"Error: {escape_html(str(e))}",
                    parse_mode="HTML",
                )
            except Exception:
                pass  # Don't fail if owner notification fails

            await query.edit_message_text(
                "<b>❌ Error</b>\n\n"
                "An unexpected error occurred. Please try again later or contact support.",
                parse_mode="HTML",
            )

    elif callback_data.startswith("logout_cancel_"):
        # User cancelled deletion
        logger.info(f"User {telegram_id} cancelled data deletion")

        await query.edit_message_text(
            "<b>🔒 Data Deletion Cancelled</b>\n\n"
            "Your data is safe and has not been deleted.\n"
            "You can continue using rSpotify Bot normally.",
            parse_mode="HTML",
        )


async def handle_export_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle /exportdata command for GDPR compliance.
    Allows users to export their personal data.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user

    if not user:
        return

    telegram_id = user.id

    logger.info(f"User {telegram_id} requested data export")

    if not update.message:
        return

    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))

        if db_service is None or db_service.database is None:
            await update.message.reply_text(
                "<b>❌ Error</b>\n\nDatabase service unavailable.", parse_mode="HTML"
            )
            return

        # Get user data
        user_repo = UserRepository(db_service.database)
        user_data = await user_repo.get_user(telegram_id)

        if not user_data:
            await update.message.reply_text(
                "<b>ℹ️ No Data Found</b>\n\n"
                "You don't have any data stored in our system.",
                parse_mode="HTML",
            )
            return

        # Format user data (excluding sensitive tokens)
        export_text = (
            f"<b>📊 Your Data Export</b>\n\n"
            f"<b>Telegram ID:</b> <code>{user_data.get('telegram_id')}</code>\n"
            f"<b>Custom Name:</b> {escape_html(user_data.get('custom_name', 'Not set'))}\n"
            f"<b>Account Created:</b> {user_data.get('created_at', 'Unknown')}\n"
            f"<b>Last Updated:</b> {user_data.get('updated_at', 'Unknown')}\n"
            f"<b>Spotify Connected:</b> {'Yes' if user_data.get('spotify') else 'No'}\n\n"
            f"<i>Note: Sensitive data like OAuth tokens are not included in exports.</i>\n\n"
            f"To delete your data, use /logout command."
        )

        await update.message.reply_text(export_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error exporting data for user {telegram_id}: {e}")

        # Notify owner of error
        try:
            from ..config import config

            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=f"<b>⚠️ Error in /exportdata</b>\n\n"
                f"User: {telegram_id}\n"
                f"Error: {escape_html(str(e))}",
                parse_mode="HTML",
            )
        except Exception:
            pass  # Don't fail if owner notification fails

        await update.message.reply_text(
            "<b>❌ Error</b>\n\nFailed to export data. Please try again later.",
            parse_mode="HTML",
        )


async def handle_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /me command to display user profile information.
    
    Shows:
    - Custom display name
    - Spotify connection status
    - Spotify account type (Free/Premium)
    - Member since date
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user:
        return
    
    telegram_id = user.id
    logger.info(f"User {telegram_id} requested profile via /me")
    
    if not update.message:
        return
    
    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        
        if db_service is None or db_service.database is None:
            await update.message.reply_html(
                "<b>❌ Error</b>\n\nDatabase service unavailable."
            )
            return
        
        # Get user data
        user_repo = UserRepository(db_service.database)
        user_data = await user_repo.get_user(telegram_id)
        
        if not user_data:
            await update.message.reply_html(
                "<b>ℹ️ Profile Not Found</b>\n\n"
                "Use /start to create your profile."
            )
            return
        
        # Get custom name
        custom_name = user_data.get("custom_name", "Not set")
        
        # Check Spotify connection
        spotify_data = user_data.get("spotify") or {}
        spotify_connected = bool(spotify_data.get("access_token"))
        spotify_status = "✅ Connected" if spotify_connected else "❌ Disconnected"
        
        # Get Spotify account type if connected
        account_type = "Unknown"
        if spotify_connected:
            try:
                auth_service = SpotifyAuthService()
                profile = await auth_service.get_user_profile(
                    spotify_data["access_token"]
                )
                
                if profile:
                    product = profile.get("product")
                    if product == "premium":
                        account_type = "Premium ⭐"
                    elif product == "free" or product == "open":
                        account_type = "Free"
                    elif product == "trial":
                        account_type = "Premium Trial"
                    elif product in ["family", "duo"]:
                        account_type = f"Premium {product.capitalize()}"
                    elif product is None:
                        account_type = "Unknown"
                    else:
                        account_type = product.capitalize()
            except Exception as e:
                logger.warning(f"Could not fetch Spotify account type: {e}")
                account_type = "Unknown"
        
        # Format created_at date
        created_at = user_data.get("created_at", "Unknown")
        if hasattr(created_at, "strftime"):
            created_at = created_at.strftime("%Y-%m-%d")
        
        # Build profile message
        profile_message = (
            f"<b>👤 Your Profile</b>\n\n"
            f"<b>Display Name:</b> {escape_html(str(custom_name))}\n"
            f"<b>Spotify Status:</b> {spotify_status}\n"
        )
        
        if spotify_connected:
            profile_message += f"<b>Account Type:</b> {account_type}\n"
        
        profile_message += (
            f"<b>Member Since:</b> {created_at}\n\n"
        )
        
        if not spotify_connected:
            profile_message += "<i>Connect Spotify with /login to unlock all features!</i>"
        else:
            profile_message += "<i>Use /rename to change your display name.</i>"
        
        await update.message.reply_html(profile_message)
    
    except Exception as e:
        logger.error(f"Error in /me command for user {telegram_id}: {e}")
        await update.message.reply_html(
            "<b>❌ Error</b>\n\nFailed to retrieve profile. Please try again later."
        )


async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /rename command to change custom display name.
    
    Validates new name and updates database with rate limiting.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user:
        return
    
    telegram_id = user.id
    logger.info(f"User {telegram_id} initiated /rename")
    
    if not update.message:
        return
    
    # Check rate limiting (3 renames per hour)
    from datetime import datetime, timedelta, timezone
    
    if context.user_data is None:
        context.user_data = {}
    
    rename_history = context.user_data.get("rename_history", [])
    current_time = datetime.now(timezone.utc)
    
    # Filter out old entries (older than 1 hour)
    recent_renames = [
        timestamp for timestamp in rename_history
        if current_time - timestamp < timedelta(hours=1)
    ]
    
    if len(recent_renames) >= 3:
        next_allowed = recent_renames[0] + timedelta(hours=1)
        minutes_left = int((next_allowed - current_time).total_seconds() / 60)
        
        await update.message.reply_html(
            f"<b>⏰ Rate Limit Exceeded</b>\n\n"
            f"You've renamed too many times. Please wait <b>{minutes_left} minutes</b> before trying again.\n\n"
            f"<i>Limit: 3 renames per hour</i>"
        )
        return
    
    # Prompt for new name
    await update.message.reply_html(
        "<b>✏️ Change Display Name</b>\n\n"
        "Please enter your new custom display name (maximum 12 characters):\n\n"
        "<i>Type /cancel to abort.</i>"
    )
    
    # Set conversation state
    context.user_data["awaiting_rename"] = True
    context.user_data["rename_history"] = recent_renames


async def handle_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle name input during /rename flow.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user or not update.message:
        return
    
    # Check if in rename flow
    if not context.user_data or not context.user_data.get("awaiting_rename"):
        return
    
    from ..services.validation import validate_custom_name
    from datetime import datetime, timezone
    
    name_input = update.message.text.strip()
    telegram_id = user.id
    
    # Check for cancel
    if name_input.lower() == "/cancel":
        context.user_data["awaiting_rename"] = False
        await update.message.reply_html(
            "<b>🚫 Rename Cancelled</b>\n\n"
            "Your display name has not been changed."
        )
        return
    
    # Validate name
    is_valid, error_message = validate_custom_name(name_input)
    
    if not is_valid:
        await update.message.reply_html(
            f"❌ <b>Invalid Name</b>\n\n"
            f"{error_message}\n\n"
            f"Please try again or type <b>/cancel</b> to abort."
        )
        return
    
    # Update name in database
    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        
        if db_service is None or db_service.database is None:
            await update.message.reply_html(
                "<b>❌ Error</b>\n\nDatabase service unavailable."
            )
            return
        
        user_repo = UserRepository(db_service.database)
        await user_repo.update_user(telegram_id, {"custom_name": name_input})
        
        # Update rename history
        rename_history = context.user_data.get("rename_history", [])
        rename_history.append(datetime.now(timezone.utc))
        context.user_data["rename_history"] = rename_history
        
        # Clear state
        context.user_data["awaiting_rename"] = False
        
        logger.info(f"User {telegram_id} renamed to '{name_input}'")
        
        await update.message.reply_html(
            f"✅ <b>Name Updated!</b>\n\n"
            f"Your display name has been changed to: <b>{escape_html(name_input)}</b>\n\n"
            f"<i>Use /me to view your profile.</i>"
        )
    
    except Exception as e:
        logger.error(f"Error updating name for user {telegram_id}: {e}")
        await update.message.reply_html(
            "<b>❌ Error</b>\n\nFailed to update name. Please try again later."
        )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command with onboarding flow.
    
    Provides welcome message with bot overview, key features, and action buttons.
    Differentiates between new and returning users, and authenticated vs unauthenticated.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user:
        return
    
    telegram_id = user.id
    user_name = escape_html(user.first_name or "there")
    logger.info(f"User {telegram_id} executed /start command")
    
    if not update.message:
        return
    
    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        
        if db_service is None or db_service.database is None:
            await update.message.reply_html(
                "<b>❌ Error</b>\n\nService temporarily unavailable. Please try again later."
            )
            return
        
        user_repo = UserRepository(db_service.database)
        existing_user = await user_repo.get_user(telegram_id)
        
        # Check if user is authenticated
        is_authenticated = False
        if existing_user and existing_user.get("spotify", {}).get("access_token"):
            is_authenticated = True
        
        # Determine if this is a new user
        is_new_user = existing_user is None
        
        if is_new_user:
            # Create user record
            await user_repo.create_user(telegram_id, user.first_name or "User")
        
        # Build welcome message based on user state
        if is_authenticated:
            # Returning authenticated user
            message = (
                f"<b>🎵 Welcome Back to rSpotify Bot!</b>\n\n"
                f"Hello <b>{user_name}</b>! 👋\n\n"
                f"Your Spotify account is connected and ready to use.\n\n"
                f"<b>🎯 What would you like to do?</b>\n"
                f"• 🎧 Check what's playing with /now\n"
                f"• 🔍 Search for music with /search\n"
                f"• 👤 View your profile with /me\n"
                f"• 📚 See all commands with /help\n\n"
                f"<i>Let's make some music together!</i> 🎶"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Help & Commands", callback_data="help_main")],
                [InlineKeyboardButton("🔒 Privacy Policy", callback_data="help_privacy")]
            ])
        
        elif is_new_user:
            # New user onboarding
            message = (
                f"<b>🎵 Welcome to rSpotify Bot!</b>\n\n"
                f"Hello <b>{user_name}</b>! 👋\n\n"
                f"I'm your personal Spotify companion for Telegram. Here's what I can do:\n\n"
                f"<b>🎯 Key Features:</b>\n"
                f"• 🔐 Secure Spotify authentication\n"
                f"• 🎧 View currently playing tracks\n"
                f"• 🔍 Search Spotify's entire catalog\n"
                f"• 📊 Get detailed track information\n"
                f"• 💬 Send feedback and suggestions\n\n"
                f"<b>🚀 Let's Get Started!</b>\n"
                f"Connect your Spotify account to unlock all features.\n\n"
                f"<i>Your privacy matters: </i><a href=\"https://github.com/shhvang/rSpotify/blob/main/PRIVACY.md\">Read our Privacy Policy</a>"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 Connect Spotify", callback_data="start_login")],
                [InlineKeyboardButton("📚 Help & Commands", callback_data="help_main")],
                [InlineKeyboardButton("🔒 Privacy Policy", callback_data="help_privacy")]
            ])
        
        else:
            # Returning user, not authenticated
            message = (
                f"<b>🎵 Welcome Back to rSpotify Bot!</b>\n\n"
                f"Hello <b>{user_name}</b>! 👋\n\n"
                f"Great to see you again! To use all features, please connect your Spotify account.\n\n"
                f"<b>🎯 Available Features:</b>\n"
                f"• 🔐 Secure Spotify authentication\n"
                f"• 🎧 View currently playing tracks\n"
                f"• 🔍 Search Spotify's entire catalog\n"
                f"• 📊 Get detailed track information\n\n"
                f"<b>🚀 Ready to Continue?</b>\n"
                f"Connect your Spotify account to get started.\n\n"
                f"<i>Your privacy matters: </i><a href=\"https://github.com/shhvang/rSpotify/blob/main/PRIVACY.md\">Read our Privacy Policy</a>"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 Connect Spotify", callback_data="start_login")],
                [InlineKeyboardButton("📚 Help & Commands", callback_data="help_main")],
                [InlineKeyboardButton("🔒 Privacy Policy", callback_data="help_privacy")]
            ])
        
        await update.message.reply_html(message, reply_markup=keyboard, disable_web_page_preview=True)
        
        # Log command usage
        await user_repo.log_command(telegram_id, "/start", success=True)
    
    except Exception as e:
        logger.error(f"Error in /start command for user {telegram_id}: {e}")
        await update.message.reply_html(
            "<b>❌ Error</b>\n\n"
            "An unexpected error occurred. Please try again later."
        )


async def handle_start_login_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle 'Connect Spotify' button callback from /start command.
    
    Triggers the /login flow.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Trigger login flow
    await handle_login(update, context)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command with interactive category selection.
    
    Displays main help menu with inline buttons for different categories.
    Dynamically shows features based on user's authentication and Premium status.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user:
        return
    
    telegram_id = user.id
    logger.info(f"User {telegram_id} requested help")
    
    # Determine the source (message or callback query)
    if update.message:
        send_method = update.message.reply_html
    elif update.callback_query:
        await update.callback_query.answer()
        send_method = update.callback_query.message.edit_text
    else:
        return
    
    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        
        if db_service is None or db_service.database is None:
            await send_method(
                "<b>❌ Error</b>\n\nService temporarily unavailable.",
                parse_mode="HTML"
            )
            return
        
        # Get user capabilities
        user_repo = UserRepository(db_service.database)
        capabilities = await get_user_capabilities(telegram_id, db_service)
        
        # Build help message
        message = (
            "<b>📚 rSpotify Bot - Help Center</b>\n\n"
            "Welcome to rSpotify Bot! Select a category below to learn more:\n\n"
        )
        
        # Add status indicators
        if capabilities["authenticated"]:
            message += f"✅ <b>Status:</b> Connected\n"
            if capabilities["premium"]:
                message += f"💎 <b>Account:</b> Spotify Premium\n"
            else:
                message += f"🆓 <b>Account:</b> Spotify Free\n"
        else:
            message += "⚠️ <b>Status:</b> Not connected\n"
        
        message += "\n<i>Select a category to explore:</i>"
        
        # Build inline keyboard with categories
        keyboard = [
            [InlineKeyboardButton("🚀 Getting Started", callback_data="help_category_getting_started")],
            [InlineKeyboardButton("🔐 Authentication", callback_data="help_category_authentication")],
            [InlineKeyboardButton("🔍 Search & Discovery", callback_data="help_category_search")],
        ]
        
        # Add Premium features if authenticated
        if capabilities["authenticated"]:
            if capabilities["premium"]:
                keyboard.append([InlineKeyboardButton("⏯️ Playback Control", callback_data="help_category_playback")])
                keyboard.append([InlineKeyboardButton("📊 Advanced Features", callback_data="help_category_advanced")])
            else:
                keyboard.append([InlineKeyboardButton("💎 Premium Features", callback_data="help_category_premium_info")])
        
        keyboard.append([InlineKeyboardButton("💬 Feedback", callback_data="help_category_feedback")])
        keyboard.append([InlineKeyboardButton("🔒 Privacy Policy", callback_data="help_privacy")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await send_method(message, parse_mode="HTML", reply_markup=reply_markup)
        
        # Log command usage
        if update.message:
            await user_repo.log_command(telegram_id, "/help", success=True)
    
    except Exception as e:
        logger.error(f"Error in /help command for user {telegram_id}: {e}")
        await send_method(
            "<b>❌ Error</b>\n\nFailed to load help menu. Please try again later.",
            parse_mode="HTML"
        )


async def handle_help_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle help category selection callbacks.
    
    Displays detailed help content for the selected category with usage examples.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    user = update.effective_user
    if not user:
        return
    
    telegram_id = user.id
    category = query.data.replace("help_category_", "")
    
    logger.info(f"User {telegram_id} selected help category: {category}")
    
    try:
        db_service = cast(DatabaseService, context.bot_data.get("db_service"))
        
        if db_service is None or db_service.database is None:
            await query.message.edit_text(
                "<b>❌ Error</b>\n\nService temporarily unavailable.",
                parse_mode="HTML"
            )
            return
        
        # Get user capabilities
        capabilities = await get_user_capabilities(telegram_id, db_service)
        
        # Generate content based on category
        message = ""
        
        if category == "getting_started":
            message = (
                "<b>🚀 Getting Started</b>\n\n"
                "Welcome to rSpotify Bot! Here's how to get started:\n\n"
                "<b>Step 1: Connect Spotify</b>\n"
                "Use <code>/login</code> to connect your Spotify account securely via OAuth.\n\n"
                "<b>Step 2: Set Your Display Name</b>\n"
                "After connecting, you'll be prompted to set a custom name for 'Now Playing' images.\n\n"
                "<b>Step 3: Explore Features</b>\n"
                "• <code>/now</code> - See what's currently playing\n"
                "• <code>/search</code> - Find tracks, artists, albums\n"
                "• <code>/me</code> - View your profile\n\n"
                "<b>🔓 Available to All Users:</b>\n"
                "• Search Spotify catalog\n"
                "• Get track information\n"
                "• Send feedback\n\n"
                f"<b>{'💎' if capabilities['premium'] else '🔐'} Requires Authentication:</b>\n"
                "• View currently playing\n"
                "• Control playback (Premium only)\n\n"
                "<i>Use /help to return to the main menu.</i>"
            )
        
        elif category == "authentication":
            message = (
                "<b>🔐 Authentication Commands</b>\n\n"
                "<b>/login</b> - Connect Your Spotify Account\n"
                "Initiates secure OAuth flow. You'll receive a link to authorize rSpotify Bot.\n\n"
                "<b>/logout</b> - Disconnect & Delete Data\n"
                "Removes all your data from our database and revokes Spotify access. This action cannot be undone.\n\n"
                "<b>/me</b> - View Your Profile\n"
                "Displays your custom name, Spotify connection status, and account type (Free/Premium).\n\n"
                "<b>/rename</b> - Change Display Name\n"
                "Update your custom display name (max 12 characters). Rate limited to 3 changes per hour.\n\n"
                "<b>🔒 Security Features:</b>\n"
                "• OAuth 2.0 authentication\n"
                "• Encrypted token storage\n"
                "• Automatic token refresh\n"
                "• SSL/TLS protected callbacks\n\n"
                "<i>Your credentials are never stored in plain text.</i>"
            )
        
        elif category == "search":
            message = (
                "<b>🔍 Search & Discovery</b>\n\n"
                "<b>/search [query]</b> - Search Spotify Catalog\n"
                "Search for tracks, artists, albums, or playlists.\n\n"
                "<b>Examples:</b>\n"
                "• <code>/search Bohemian Rhapsody</code>\n"
                "• <code>/search The Beatles - Hey Jude</code>\n"
                "• <code>/search artist:Drake</code>\n\n"
                "<b>/info [spotify_url]</b> - Get Track Information\n"
                "Extract detailed information from Spotify URLs.\n\n"
                "<b>Examples:</b>\n"
                "• <code>/info https://open.spotify.com/track/...</code>\n"
                "• <code>/info spotify:track:...</code>\n\n"
                "<b>📊 Results Include:</b>\n"
                "• Track name and artists\n"
                "• Album and release date\n"
                "• Duration and popularity\n"
                "• Direct Spotify link\n\n"
                "🔓 <i>Available to all users, no authentication required!</i>"
            )
        
        elif category == "playback":
            if not capabilities["authenticated"]:
                message = (
                    "<b>⏯️ Playback Control</b>\n\n"
                    "⚠️ <b>Authentication Required</b>\n\n"
                    "To use playback features, please connect your Spotify account with <code>/login</code>.\n\n"
                    "Once connected, you'll be able to:\n"
                    "• View currently playing tracks\n"
                    "• Control playback (Premium accounts)\n\n"
                    "<i>Premium subscription required for playback control.</i>"
                )
            elif not capabilities["premium"]:
                message = (
                    "<b>⏯️ Playback Control</b>\n\n"
                    "💎 <b>Premium Required</b>\n\n"
                    "Playback control features require a Spotify Premium subscription.\n\n"
                    "<b>Available with Premium:</b>\n"
                    "• <code>/play</code> - Resume playback\n"
                    "• <code>/pause</code> - Pause playback\n"
                    "• <code>/next</code> - Skip to next track\n"
                    "• <code>/prev</code> - Go to previous track\n\n"
                    "<b>Currently Available:</b>\n"
                    "• <code>/now</code> - View currently playing track\n\n"
                    "<i>Upgrade to Spotify Premium to unlock all features!</i>"
                )
            else:
                message = (
                    "<b>⏯️ Playback Control</b>\n\n"
                    "💎 <b>Premium Features Unlocked!</b>\n\n"
                    "<b>/now</b> - Currently Playing\n"
                    "Shows what's playing with playback progress, device info, and shuffle/repeat status.\n\n"
                    "<b>/play</b> - Resume Playback\n"
                    "Starts or resumes playback on your active device.\n\n"
                    "<b>/pause</b> - Pause Playback\n"
                    "Pauses the current track.\n\n"
                    "<b>/next</b> - Skip Track\n"
                    "Skips to the next track in queue.\n\n"
                    "<b>/prev</b> - Previous Track\n"
                    "Goes back to the previous track.\n\n"
                    "<i>Make sure you have an active Spotify device to use these commands.</i>"
                )
        
        elif category == "advanced":
            if not capabilities["premium"]:
                message = (
                    "<b>📊 Advanced Features</b>\n\n"
                    "💎 <b>Premium Required</b>\n\n"
                    "Advanced features require a Spotify Premium subscription.\n\n"
                    "<b>Available with Premium:</b>\n"
                    "• Volume control\n"
                    "• Shuffle toggle\n"
                    "• Repeat mode\n"
                    "• Queue management\n\n"
                    "<i>Upgrade to Spotify Premium to access these features!</i>"
                )
            else:
                message = (
                    "<b>📊 Advanced Features</b>\n\n"
                    "💎 <b>Premium Features</b>\n\n"
                    "<b>/volume [level]</b> - Adjust Volume\n"
                    "Set volume level (0-100) or use relative changes.\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>/volume 75</code> - Set to 75%\n"
                    "• <code>/volume +10</code> - Increase by 10%\n"
                    "• <code>/volume -20</code> - Decrease by 20%\n\n"
                    "<b>/shuffle [on|off]</b> - Toggle Shuffle\n"
                    "Enable or disable shuffle mode.\n\n"
                    "<b>/repeat [off|track|context]</b> - Repeat Mode\n"
                    "• <code>off</code> - No repeat\n"
                    "• <code>track</code> - Repeat current track\n"
                    "• <code>context</code> - Repeat playlist/album\n\n"
                    "<b>/queue</b> - View Queue\n"
                    "See what's coming up next in your playback queue.\n\n"
                    "<i>These features require an active Spotify device.</i>"
                )
        
        elif category == "feedback":
            message = (
                "<b>💬 User Feedback</b>\n\n"
                "<b>/feedback [message]</b> - Send Feedback\n"
                "Share your thoughts, report bugs, or request features.\n\n"
                "<b>Examples:</b>\n"
                "• <code>/feedback The bot is amazing!</code>\n"
                "• <code>/feedback Bug: Search not working</code>\n"
                "• <code>/feedback Feature request: Add playlist support</code>\n\n"
                "<b>📋 Feedback Categories:</b>\n"
                "• 🐛 Bug Report\n"
                "• ✨ Feature Request\n"
                "• 💭 General Feedback\n\n"
                "<b>⏰ Rate Limits:</b>\n"
                "• Maximum 3 feedback messages per hour\n"
                "• Helps prevent spam and ensures quality\n\n"
                "<i>Your feedback helps improve rSpotify Bot for everyone!</i>"
            )
        
        elif category == "premium_info":
            message = (
                "<b>💎 Premium Features</b>\n\n"
                "You're currently using a <b>Spotify Free</b> account.\n\n"
                "<b>🎵 Current Features:</b>\n"
                "• ✅ Search Spotify catalog\n"
                "• ✅ View currently playing\n"
                "• ✅ Get track information\n"
                "• ✅ User feedback\n\n"
                "<b>💎 Unlock with Premium:</b>\n"
                "• ⏯️ Full playback control (play, pause, skip)\n"
                "• 🔊 Volume control\n"
                "• 🔀 Shuffle and repeat modes\n"
                "• 📋 Queue management\n"
                "• 🚀 And more features coming soon!\n\n"
                "<i>Upgrade to Spotify Premium to unlock all features.</i>\n"
                "<a href=\"https://www.spotify.com/premium/\">Learn More About Premium</a>"
            )
        
        else:
            message = "<b>❌ Unknown Category</b>\n\nPlease select a valid category from the help menu."
        
        # Add back button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back to Help Menu", callback_data="help_main")]
        ])
        
        await query.message.edit_text(
            message,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    
    except Exception as e:
        logger.error(f"Error in help category handler for user {telegram_id}: {e}")
        await query.message.edit_text(
            "<b>❌ Error</b>\n\nFailed to load help content. Please try again.",
            parse_mode="HTML"
        )


async def handle_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /privacy command to display privacy policy.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    
    if not user:
        return
    
    telegram_id = user.id
    logger.info(f"User {telegram_id} requested privacy policy")
    
    # Determine the source (message or callback query)
    if update.message:
        send_method = update.message.reply_html
    elif update.callback_query:
        await update.callback_query.answer()
        send_method = update.callback_query.message.edit_text
    else:
        return
    
    try:
        message = (
            "<b>🔒 Privacy Policy</b>\n\n"
            "<b>Data We Collect:</b>\n"
            "• Telegram ID (for identification)\n"
            "• Custom display name (optional)\n"
            "• Spotify OAuth tokens (encrypted)\n"
            "• Command usage statistics\n\n"
            "<b>How We Use Your Data:</b>\n"
            "• Provide bot functionality\n"
            "• Connect to your Spotify account\n"
            "• Generate personalized content\n"
            "• Improve user experience\n\n"
            "<b>Data Storage:</b>\n"
            "• Stored in MongoDB Atlas (secure cloud database)\n"
            "• Spotify tokens are encrypted using industry-standard encryption\n"
            "• Automatic cleanup with TTL indexes (30 days for cache)\n\n"
            "<b>Data Retention:</b>\n"
            "• User data: Until you use <code>/logout</code>\n"
            "• Search cache: 30 days (automatic deletion)\n"
            "• Usage logs: Retained for analytics\n\n"
            "<b>Your Rights:</b>\n"
            "• ✅ Access your data with <code>/me</code>\n"
            "• ✅ Export your data with <code>/exportdata</code>\n"
            "• ✅ Delete all data with <code>/logout</code>\n\n"
            "<b>Third-Party Services:</b>\n"
            "• Spotify API (for music data and playback)\n"
            "• Telegram API (for bot functionality)\n\n"
            "<b>Security:</b>\n"
            "• HTTPS with SSL/TLS encryption\n"
            "• OAuth 2.0 authentication\n"
            "• Encrypted token storage\n"
            "• No plain-text credential storage\n\n"
            "<b>Contact:</b>\n"
            "• Use <code>/feedback</code> for privacy concerns\n"
            "• GitHub: <a href=\"https://github.com/shhvang/rSpotify\">shhvang/rSpotify</a>\n\n"
            "<i>Last updated: October 2025</i>\n\n"
            "For the full privacy policy, visit:\n"
            "<a href=\"https://github.com/shhvang/rSpotify/blob/main/PRIVACY.md\">GitHub Privacy Policy</a>"
        )
        
        # Add back button if called from help menu
        if update.callback_query:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back to Help Menu", callback_data="help_main")],
                [InlineKeyboardButton("🗑️ Delete My Data", callback_data="logout_confirm_start")]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Help Menu", callback_data="help_main")],
                [InlineKeyboardButton("🗑️ Delete My Data", callback_data="logout_confirm_start")]
            ])
        
        await send_method(message, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        
        # Log command usage
        if update.message:
            db_service = cast(DatabaseService, context.bot_data.get("db_service"))
            if db_service and db_service.database:
                user_repo = UserRepository(db_service.database)
                await user_repo.log_command(telegram_id, "/privacy", success=True)
    
    except Exception as e:
        logger.error(f"Error in /privacy command for user {telegram_id}: {e}")
        await send_method(
            "<b>❌ Error</b>\n\nFailed to load privacy policy. Please try again.",
            parse_mode="HTML"
        )


async def get_user_capabilities(telegram_id: int, db_service: DatabaseService) -> dict:
    """
    Get user's capabilities (authenticated, premium, etc.).
    
    Args:
        telegram_id: Telegram user ID
        db_service: Database service instance
    
    Returns:
        Dictionary with capability flags:
        - authenticated: bool
        - premium: bool
    """
    user_repo = UserRepository(db_service.database)
    user = await user_repo.get_user(telegram_id)
    
    capabilities = {
        "authenticated": False,
        "premium": False
    }
    
    if not user or not user.get("spotify"):
        return capabilities
    
    spotify_data = user.get("spotify", {})
    if not spotify_data.get("access_token"):
        return capabilities
    
    capabilities["authenticated"] = True
    
    # Query Spotify API for account type
    try:
        auth_service = SpotifyAuthService()
        profile = await auth_service.get_user_profile(spotify_data["access_token"])
        
        if profile:
            product = profile.get("product")
            capabilities["premium"] = product == "premium"
    except Exception as e:
        logger.error(f"Error checking Premium status for user {telegram_id}: {e}")
    
    return capabilities


def register_user_command_handlers(application: Any) -> None:
    """
    Register all user command handlers.

    Args:
        application: Telegram application instance
    """
    from telegram.ext import CommandHandler

    # Register command handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("privacy", handle_privacy))
    application.add_handler(CommandHandler("login", handle_login))
    application.add_handler(CommandHandler("logout", handle_logout))
    application.add_handler(CommandHandler("exportdata", handle_export_data))
    application.add_handler(CommandHandler("me", handle_me))
    application.add_handler(CommandHandler("rename", handle_rename))

    # Register callback handlers
    application.add_handler(
        CallbackQueryHandler(
            handle_logout_callback, pattern=r"^logout_(confirm|cancel)_\d+$"
        )
    )
    
    # Register help system callbacks
    application.add_handler(
        CallbackQueryHandler(handle_help, pattern="^help_main$")
    )
    
    application.add_handler(
        CallbackQueryHandler(handle_help_category, pattern="^help_category_")
    )
    
    application.add_handler(
        CallbackQueryHandler(handle_privacy, pattern="^help_privacy$")
    )
    
    application.add_handler(
        CallbackQueryHandler(handle_start_login_callback, pattern="^start_login$")
    )

    logger.info("User command handlers registered")

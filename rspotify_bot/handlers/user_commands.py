"""
User command handlers for rSpotify Bot.
Handles user-facing commands like /login, /logout for Spotify authentication and data privacy.
"""

import logging
import secrets
from typing import Any, cast
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


def register_user_command_handlers(application: Any) -> None:
    """
    Register all user command handlers.

    Args:
        application: Telegram application instance
    """
    from telegram.ext import CommandHandler

    # Register command handlers
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

    logger.info("User command handlers registered")

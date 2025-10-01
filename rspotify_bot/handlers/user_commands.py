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
        if not db_service or db_service.database is None:
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

            if not db_service or db_service.database is None:
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

        if not db_service or db_service.database is None:
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

    # Register callback handlers
    application.add_handler(
        CallbackQueryHandler(
            handle_logout_callback, pattern=r"^logout_(confirm|cancel)_\d+$"
        )
    )

    logger.info("User command handlers registered")

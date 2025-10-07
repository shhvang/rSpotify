"""
Core bot implementation for rSpotify Bot.
Handles Telegram integration and command routing.
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Config
from .services.database import DatabaseService
from .services.notifications import NotificationService
from .services.middleware import create_protection_wrapper, get_temporary_storage
from .handlers.owner_commands import register_owner_commands
from .handlers.user_commands import register_user_command_handlers

logger = logging.getLogger(__name__)


class RSpotifyBot:
    """Main bot class that handles Telegram integration."""

    def __init__(self, token: str) -> None:
        """
        Initialize the rSpotify bot.

        Args:
            token: Telegram bot token
        """
        self.token = token
        self.application: Optional[Application] = None
        self.db_service: Optional[DatabaseService] = None
        self.notification_service: Optional[NotificationService] = None
        self.owner_handler: Any = None
        self.protection_wrapper: Optional[Callable[[str], Callable]] = None

    async def start(self) -> None:
        """Start the bot and begin polling for updates."""
        logger.info("Initializing rSpotify bot...")

        # Initialize database service
        self.db_service = DatabaseService()
        if not await self.db_service.connect():
            logger.error("Failed to connect to database. Exiting.")
            return

        # Initialize temporary storage for OAuth state parameters
        # Use MongoDB backend for cross-process sharing with web callback
        temp_storage = get_temporary_storage()
        temp_storage.configure_backend(self.db_service.database)

        if temp_storage.uses_mongodb:
            logger.info("Temporary storage ready with MongoDB backend")
        else:
            logger.info("Temporary storage using in-memory backend")
        
        await temp_storage.start_cleanup_task()
        logger.info("Temporary storage cleanup task started")

        # Build application
        self.application = ApplicationBuilder().token(self.token).build()

        # Initialize notification service
        self.notification_service = NotificationService(self.application.bot)

        # Initialize protection middleware
        self.protection_wrapper = create_protection_wrapper(self.db_service)

        # Store db_service in bot_data for access by handlers
        self.application.bot_data["db_service"] = self.db_service

        # Register handlers
        self._register_handlers()
        
        # Register commands with Telegram for autocomplete
        await self._register_bot_commands()

        # Start bot
        logger.info("Starting bot polling...")
        async with self.application:
            await self.application.start()

            # Send startup notification
            await self.notification_service.send_startup_notification("1.2.0")

            logger.info("✅ Bot started successfully! Send /ping to test.")

            # Start polling and run until interrupted
            if not self.application.updater:
                logger.error("Updater not available")
                return

            await self.application.updater.start_polling(drop_pending_updates=True)

            # Keep running until stopped
            import asyncio

            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
                logger.info("Received shutdown signal...")

            # Clean shutdown sequence - stop updater and application before context exit
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()

            # Stop temporary storage cleanup task
            await temp_storage.stop_cleanup_task()
            logger.info("Temporary storage cleanup task stopped")

            logger.info("Bot stopped gracefully")
    
    async def _register_bot_commands(self) -> None:
        """Register bot commands with Telegram for autocomplete."""
        if not self.application:
            return
        
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "Start using rSpotify Bot"),
            BotCommand("help", "Get help and command reference"),
            BotCommand("login", "Connect your Spotify account"),
            BotCommand("logout", "Disconnect and delete your data"),
            BotCommand("me", "View your profile"),
            BotCommand("rename", "Change your display name"),
            BotCommand("privacy", "View privacy policy"),
            BotCommand("ping", "Test bot connectivity"),
            BotCommand("exportdata", "Export your personal data"),
        ]
        
        try:
            await self.application.bot.set_my_commands(commands)
            logger.info(f"Registered {len(commands)} commands with Telegram")
        except Exception as e:
            logger.error(f"Failed to register commands with Telegram: {e}")

    def _register_handlers(self) -> None:
        """Register command and message handlers."""
        if not self.application or not self.db_service:
            return

        # Register owner commands
        self.owner_handler = register_owner_commands(self.application, self.db_service)

        # Register user commands (includes start, help, privacy, login, logout, etc.)
        register_user_command_handlers(self.application)

        # Get protection wrapper
        protect = self.protection_wrapper
        if not protect:
            logger.error("Protection wrapper not initialized")
            return

        # Command handlers with protection
        self.application.add_handler(
            CommandHandler("ping", protect("ping")(self.ping_command))
        )
        
        # Message handler for custom name input during onboarding
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                protect("custom_name_input")(self.handle_custom_name_input)
            )
        )

        # Message handlers for unknown commands
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self.unknown_command)
        )

        # Error handler
        self.application.add_error_handler(self.error_handler)

        logger.info("Registered bot handlers")

    async def ping_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /ping command - provides immediate testable functionality.

        Args:
            update: Telegram update object
            context: Bot context
        """
        import time

        user = update.effective_user
        chat = update.effective_chat

        if not user or not chat:
            return

        # Start timing
        start_time = time.time()

        # Check maintenance mode
        if self.owner_handler and self.owner_handler.is_maintenance_mode():
            from .services.auth import is_owner

            if not await is_owner(user.id):
                await self.owner_handler.send_maintenance_message(update)
                return

        logger.info(f"Ping command from user {user.id} in chat {chat.id}")

        # Test database connection with timing
        db_start = time.time()
        db_connected = False
        db_time_ms = 0

        if self.db_service:
            db_connected = await self.db_service.health_check()
            db_time_ms = (time.time() - db_start) * 1000

        db_status = "✅ Connected" if db_connected else "❌ Disconnected"

        if not update.message:
            return

        # Calculate total time (will update after sending)
        total_time_ms = (time.time() - start_time) * 1000
        
        # Create single complete response message with all information
        response = (
            f"<b>🏓 Pong!</b>\n\n"
            f"👋 Hello <b>{user.first_name or 'there'}</b>!\n"
            f"🤖 Bot is running and responsive\n"
            f"🗄️ Database: {db_status}\n"
            f"⚡ Environment: <code>{Config.ENVIRONMENT}</code>\n\n"
            f"<b>⏱️ Response Timings:</b>\n"
            f"• Database: <code>{db_time_ms:.2f}ms</code>\n"
            f"• <b>Total:</b> <code>{total_time_ms:.2f}ms</code>\n\n"
            f"<i>Use /help for available commands.</i>"
        )
        
        # Send single response with all information
        await update.message.reply_html(response)

    async def _handle_oauth_code(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, code_id: str, telegram_id: int
    ) -> None:
        """
        Handle OAuth code retrieval and token exchange (Spotipie-style flow).
        
        Args:
            update: Telegram update object
            context: Bot context
            code_id: MongoDB ObjectId of the stored auth code
            telegram_id: Telegram user ID
        """
        from bson import ObjectId
        from bson.errors import InvalidId
        from .services.auth import SpotifyAuthService
        from .services.repository import UserRepository
        
        try:
            # Validate code_id format
            try:
                obj_id = ObjectId(code_id)
            except (InvalidId, TypeError):
                await update.message.reply_text(
                    "❌ Invalid authorization link. Please use /login to start the OAuth flow."
                )
                return
            
            # Retrieve auth code from database
            code_doc = await asyncio.to_thread(
                self.db_service.database.oauth_codes.find_one, {"_id": obj_id}
            )

            if not code_doc:
                logger.warning(f"Authorization code not found for telegram_id {telegram_id}")
                await update.message.reply_text(
                    "❌ Authorization code not found or expired. Please use /login to try again."
                )
                return

            auth_code = code_doc.get("auth_code")
            if not auth_code:
                await update.message.reply_text(
                    "❌ Invalid authorization code. Please use /login to try again."
                )
                return

            # Send processing message
            status_message = await update.message.reply_text(
                "🔄 Exchanging authorization code for tokens..."
            )

            # Exchange code for tokens
            logger.info(f"Exchanging auth code for telegram_id {telegram_id}")
            auth_service = SpotifyAuthService()
            
            try:
                tokens = await auth_service.exchange_code_for_tokens(auth_code)
            except Exception as token_error:
                logger.error(f"Token exchange exception for telegram_id {telegram_id}: {token_error}", exc_info=True)
                await status_message.edit_text(
                    f"❌ Failed to exchange authorization code: {type(token_error).__name__}\n\n"
                    f"Please try /login again."
                )
                # Delete used code
                await asyncio.to_thread(
                    self.db_service.database.oauth_codes.delete_one, {"_id": obj_id}
                )
                return

            if not tokens:
                logger.error(f"Token exchange returned None for telegram_id {telegram_id}")
                await status_message.edit_text(
                    "❌ Failed to exchange authorization code for tokens. Please try /login again."
                )
                # Delete used code
                await asyncio.to_thread(
                    self.db_service.database.oauth_codes.delete_one, {"_id": obj_id}
                )
                return

            # Store tokens in database
            user_repo = UserRepository(self.db_service.database)
            success = await user_repo.update_spotify_tokens(
                telegram_id,
                tokens["access_token"],
                tokens["refresh_token"],
                tokens.get("expires_at"),
            )

            # Delete used code from database
            await asyncio.to_thread(
                self.db_service.database.oauth_codes.delete_one, {"_id": obj_id}
            )

            if success:
                # Check if user needs to set up custom name
                user = await user_repo.get_user(telegram_id)
                if user and not user.get("custom_name"):
                    # Prompt for custom name setup
                    await status_message.edit_text(
                        "✅ <b>Spotify account connected successfully!</b>\n\n"
                        "🎵 <b>Let's personalize your experience!</b>\n\n"
                        "Please set a custom display name for your 'Now Playing' images "
                        "(maximum 12 characters).\n\n"
                        "<i>You can use /rename anytime to change it later.</i>",
                        parse_mode="HTML"
                    )
                    
                    # Set conversation state for name input
                    if context.user_data is not None:
                        context.user_data["awaiting_custom_name"] = True
                else:
                    await status_message.edit_text(
                        "✅ <b>Spotify account connected successfully!</b>\n\n"
                        "You can now use all Spotify features:\n"
                        "• <code>/nowplaying</code> - Share what you're listening to\n"
                        "• <code>/me</code> - View your profile\n"
                        "• <code>/rename</code> - Change your display name\n"
                        "• <code>/logout</code> - Disconnect your Spotify account\n\n"
                        "<i>Enjoy the music! 🎶</i>",
                        parse_mode="HTML"
                    )
            else:
                await status_message.edit_text(
                    "❌ Failed to store tokens. Please try /login again."
                )
                
        except Exception as e:
            import uuid
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"[{error_id}] Error handling OAuth code for user {telegram_id}: {e}", exc_info=True)
            logger.error(f"[{error_id}] Error type: {type(e).__name__}")
            
            await update.message.reply_text(
                f"❌ An error occurred while processing your authorization.\n"
                f"Error ID: <code>{error_id}</code>\n\n"
                f"Please try /login again.",
                parse_mode="HTML"
            )

    async def handle_custom_name_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle custom name input during post-authentication setup or rename flow.
        
        Args:
            update: Telegram update object
            context: Bot context
        """
        from .handlers.user_commands import handle_rename_input
        
        user = update.effective_user
        
        if not user or not update.message:
            return
        
        # Check if user is in rename flow (higher priority)
        if context.user_data and context.user_data.get("awaiting_rename"):
            await handle_rename_input(update, context)
            return
        
        # Check if user is in custom name setup flow
        if not context.user_data or not context.user_data.get("awaiting_custom_name"):
            # Not in setup flow, ignore
            return
        
        from .services.validation import validate_custom_name
        from .services.repository import UserRepository
        from .services.auth import SpotifyAuthService
        
        name_input = update.message.text.strip()
        
        # Allow user to skip with specific keywords
        if name_input.lower() in ["skip", "default", "later"]:
            # Apply default name fallback
            logger.info(f"User {user.id} skipped custom name setup")
            
            # Get default name
            default_name = await self._get_default_name(user)
            
            # Save default name
            user_repo = UserRepository(self.db_service.database)
            await user_repo.update_user(user.id, {"custom_name": default_name})
            
            # Clear state
            context.user_data["awaiting_custom_name"] = False
            
            await update.message.reply_html(
                f"✅ <b>Setup Complete!</b>\n\n"
                f"Your display name has been set to: <b>{default_name}</b>\n\n"
                f"You can change it anytime with <code>/rename</code>.\n\n"
                f"<i>Use /help to see available commands.</i>"
            )
            return
        
        # Validate custom name
        is_valid, error_message = validate_custom_name(name_input)
        
        if not is_valid:
            # Send error and prompt again
            await update.message.reply_html(
                f"❌ <b>Invalid Name</b>\n\n"
                f"{error_message}\n\n"
                f"Please try again or type <b>skip</b> to use a default name."
            )
            return
        
        # Save validated name
        logger.info(f"Setting custom name '{name_input}' for user {user.id}")
        user_repo = UserRepository(self.db_service.database)
        await user_repo.update_user(user.id, {"custom_name": name_input})
        
        # Clear state
        context.user_data["awaiting_custom_name"] = False
        
        # Send confirmation
        await update.message.reply_html(
            f"✅ <b>Perfect!</b>\n\n"
            f"Your display name has been set to: <b>{name_input}</b>\n\n"
            f"You can now use:\n"
            f"• <code>/me</code> - View your profile\n"
            f"• <code>/rename</code> - Change your display name\n"
            f"• <code>/nowplaying</code> - Share what you're listening to\n\n"
            f"<i>Enjoy the music! 🎶</i>"
        )

    async def _get_default_name(self, telegram_user) -> str:
        """
        Get default name fallback for user.
        
        Priority:
        1. Spotify display name (if available)
        2. Telegram username
        3. Telegram first name
        4. "User" as last resort
        
        Args:
            telegram_user: Telegram user object
        
        Returns:
            Default name string (max 12 characters)
        """
        from .services.auth import SpotifyAuthService
        from .services.repository import UserRepository
        
        # Try to get Spotify display name
        try:
            user_repo = UserRepository(self.db_service.database)
            user_data = await user_repo.get_user(telegram_user.id)
            
            if user_data and user_data.get("spotify", {}).get("access_token"):
                auth_service = SpotifyAuthService()
                profile = await auth_service.get_user_profile(
                    user_data["spotify"]["access_token"]
                )
                
                if profile and profile.get("display_name"):
                    return profile["display_name"][:12]
        except Exception as e:
            logger.warning(f"Could not fetch Spotify display name: {e}")
        
        # Try Telegram username
        if telegram_user.username:
            return telegram_user.username[:12]
        
        # Try Telegram first name
        if telegram_user.first_name:
            return telegram_user.first_name[:12]
        
        # Last resort
        return "User"

    async def unknown_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle unknown commands.

        Args:
            update: Telegram update object
            context: Bot context
        """
        user = update.effective_user

        if not user or not update.message:
            return

        # Check maintenance mode
        if self.owner_handler and self.owner_handler.is_maintenance_mode():
            from .services.auth import is_owner

            if not await is_owner(user.id):
                await self.owner_handler.send_maintenance_message(update)
                return

        command = update.message.text or "unknown"
        logger.info(f"Unknown command '{command}' from user {user.id}")

        # HTML escape the command to prevent injection
        import html

        escaped_command = html.escape(command)

        response = (
            "<b>❓ Unknown Command</b>\n\n"
            f"I don't recognize the command: <code>{escaped_command}</code>\n\n"
            "<i>Use /help to see available commands.</i>"
        )

        await update.message.reply_html(response)

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle errors that occur during message processing.

        Args:
            update: Telegram update object
            context: Bot context containing error information
        """
        logger.error(
            f"Exception while handling update: {context.error}", exc_info=context.error
        )

        # Try to send error message to user if possible
        if isinstance(update, Update) and update.effective_message:
            try:
                error_message = (
                    "❌ **Oops! Something went wrong.**\n\n"
                    "An error occurred while processing your request. "
                    "Please try again later or contact support if the issue persists."
                )

                await update.effective_message.reply_text(
                    error_message, parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")

        # Send critical error report to owner
        if (
            hasattr(self, "notification_service")
            and self.notification_service
            and context.error
        ):
            try:
                await self.notification_service.send_error_report(
                    context.error, {"update": str(update)[:300] if update else None}
                )
            except Exception as e:
                logger.error(f"Failed to send error report to owner: {e}")

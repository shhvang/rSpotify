"""
Core bot implementation for rSpotify Bot.
Handles Telegram integration and command routing.
"""

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

        # Initialize temporary storage for OAuth state parameters with MongoDB
        # This allows state sharing between bot and OAuth service processes
        temp_storage = get_temporary_storage()
        # Reinitialize with MongoDB database for cross-process sharing
        temp_storage._database = self.db_service.database
        temp_storage._use_mongodb = True
        logger.info("Temporary storage initialized with MongoDB for cross-process state sharing")
        
        # Create TTL index on temp_storage collection (Motor is async)
        try:
            await self.db_service.database.temp_storage.create_index(
                "expires_at",
                expireAfterSeconds=0
            )
            logger.info("Created TTL index on temp_storage collection")
        except Exception as e:
            logger.warning(f"Failed to create TTL index (may already exist): {e}")
        
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

    def _register_handlers(self) -> None:
        """Register command and message handlers."""
        if not self.application or not self.db_service:
            return

        # Register owner commands
        self.owner_handler = register_owner_commands(self.application, self.db_service)

        # Register user commands (logout, exportdata)
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
        self.application.add_handler(
            CommandHandler("start", protect("start")(self.start_command))
        )
        self.application.add_handler(
            CommandHandler("help", protect("help")(self.help_command))
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

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /start command.
        Also handles OAuth deep links with code IDs (Spotipie-style flow).

        Args:
            update: Telegram update object
            context: Bot context
        """
        user = update.effective_user

        if not user:
            return

        # Check maintenance mode
        if self.owner_handler and self.owner_handler.is_maintenance_mode():
            from .services.auth import is_owner

            if not await is_owner(user.id):
                await self.owner_handler.send_maintenance_message(update)
                return

        logger.info(f"Start command from user {user.id}")

        if not update.message:
            return

        # Check if this is an OAuth callback with code ID
        # Format: /start CODE_ID (from Telegram deep link)
        message_text = update.message.text
        if message_text and len(message_text.split()) > 1:
            code_id = message_text.split()[1]
            
            # Handle OAuth code retrieval and token exchange
            await self._handle_oauth_code(update, code_id, user.id)
            return

        # Create or update user record
        if self.db_service:
            existing_user = await self.db_service.get_user(user.id)
            if not existing_user:
                await self.db_service.create_user(user.id, user.first_name)

        welcome_message = (
            f"<b>🎵 Welcome to rSpotify Bot!</b>\n\n"
            f"Hello <b>{user.first_name or 'there'}</b>! I'm here to help you share "
            f"and discover amazing music through Spotify integration.\n\n"
            f"<b>Quick Start:</b>\n"
            f"• Use <code>/login</code> to connect your Spotify account\n"
            f"• Use <code>/ping</code> to test bot connectivity\n"
            f"• Use <code>/help</code> to see all available commands\n\n"
            f"<i>Let's make some music together!</i> 🎶"
        )

        await update.message.reply_html(welcome_message)

    async def _handle_oauth_code(
        self, update: Update, code_id: str, telegram_id: int
    ) -> None:
        """
        Handle OAuth code retrieval and token exchange (Spotipie-style flow).
        
        Args:
            update: Telegram update object
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
            code_doc = await self.db_service.database.oauth_codes.find_one({"_id": obj_id})
            
            if not code_doc:
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
            auth_service = SpotifyAuthService()
            tokens = await auth_service.exchange_code_for_tokens(auth_code)
            
            if not tokens:
                await status_message.edit_text(
                    "❌ Failed to exchange authorization code for tokens. Please try /login again."
                )
                # Delete used code
                await self.db_service.database.oauth_codes.delete_one({"_id": obj_id})
                return
            
            # Store tokens in database
            user_repo = UserRepository(self.db_service.database)
            success = await user_repo.update_spotify_tokens(
                telegram_id,
                tokens["access_token"],
                tokens["refresh_token"],
                tokens["expires_at"]
            )
            
            # Delete used code from database
            await self.db_service.database.oauth_codes.delete_one({"_id": obj_id})
            
            if success:
                await status_message.edit_text(
                    "✅ <b>Spotify account connected successfully!</b>\n\n"
                    "You can now use all Spotify features:\n"
                    "• <code>/nowplaying</code> - Share what you're listening to\n"
                    "• <code>/logout</code> - Disconnect your Spotify account\n\n"
                    "<i>Enjoy the music! 🎶</i>",
                    parse_mode="HTML"
                )
            else:
                await status_message.edit_text(
                    "❌ Failed to store tokens. Please try /login again."
                )
                
        except Exception as e:
            logger.error(f"Error handling OAuth code: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ An error occurred while processing your authorization. Please try /login again."
            )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /help command.

        Args:
            update: Telegram update object
            context: Bot context
        """
        user = update.effective_user

        if not user:
            return

        # Check maintenance mode
        if self.owner_handler and self.owner_handler.is_maintenance_mode():
            from .services.auth import is_owner

            if not await is_owner(user.id):
                await self.owner_handler.send_maintenance_message(update)
                return

        logger.info(f"Help command from user {user.id}")

        if not update.message:
            return

        # Check if user is owner to show owner commands
        from .services.auth import is_owner

        is_bot_owner = await is_owner(user.id)

        help_message = (
            "<b>🤖 rSpotify Bot - Available Commands</b>\n\n"
            "<b>Basic Commands:</b>\n"
            "• <code>/start</code> - Welcome message and bot introduction\n"
            "• <code>/ping</code> - Test bot connectivity and health\n"
            "• <code>/help</code> - Show this help message\n\n"
            "<b>Privacy & Data:</b>\n"
            "• <code>/exportdata</code> - Export your personal data (GDPR)\n"
            "• <code>/logout</code> - Delete all your data and disconnect\n\n"
        )

        if is_bot_owner:
            help_message += (
                "<b>👑 Owner Commands:</b>\n"
                "• <code>/maintenance [on|off]</code> - Toggle maintenance mode\n"
                "• <code>/stats [days]</code> - Show bot usage statistics\n"
                "• <code>/blacklist &lt;user_id&gt; [reason]</code> - Block user\n"
                "• <code>/whitelist &lt;user_id&gt;</code> - Unblock user\n"
                "• <code>/logs [lines]</code> - Get bot output logs\n"
                "• <code>/errorlogs [lines]</code> - Get bot error logs\n\n"
            )

        help_message += (
            "<b>Coming Soon:</b>\n"
            "• Spotify track sharing\n"
            "• Music recommendations\n"
            "• Now playing images\n"
            "• Playlist management\n\n"
            "<i>🚀 This bot is currently in development. More features will be added soon!</i>"
        )

        await update.message.reply_html(help_message)

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

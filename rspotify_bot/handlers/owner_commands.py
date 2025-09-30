"""
Owner command handlers for rSpotify Bot.
Provides administrative commands exclusively for the bot owner.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, Application
from telegram.error import TelegramError

from ..services.auth import is_owner
from ..services.database import DatabaseService

logger = logging.getLogger(__name__)


class OwnerCommands:
    """Handler class for owner-only commands."""

    def __init__(self, database_service: DatabaseService):
        """
        Initialize owner commands handler.

        Args:
            database_service: Database service instance
        """
        self.db = database_service
        self.maintenance_mode = False
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._cache_expires = datetime.now()

    async def maintenance_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Toggle bot maintenance mode.
        Usage: /maintenance [on|off]
        """
        if not update.message:
            return

        # Check owner authorization
        user = update.effective_user
        if not user or not await is_owner(user.id):
            await update.message.reply_html(
                "<b>⛔ Unauthorized</b>\n"
                "<i>This command is only available to the bot owner.</i>"
            )
            return

        try:
            args = context.args

            if not args:
                # Show current status
                status = "🔧 <b>ON</b>" if self.maintenance_mode else "✅ <b>OFF</b>"
                await update.message.reply_html(
                    f"<b>🛠 Maintenance Mode</b>\n\n"
                    f"<b>Status:</b> {status}\n\n"
                    f"<i>Usage:</i> <code>/maintenance [on|off]</code>"
                )
                return

            command = args[0].lower()

            if command == "on":
                self.maintenance_mode = True
                await update.message.reply_html(
                    "<b>🔧 Maintenance Mode Activated</b>\n\n"
                    "<i>Bot is now in maintenance mode. Regular users will receive maintenance messages.</i>"
                )
                logger.info("Maintenance mode activated by owner")

            elif command == "off":
                self.maintenance_mode = False
                await update.message.reply_html(
                    "<b>✅ Maintenance Mode Deactivated</b>\n\n"
                    "<i>Bot is now fully operational for all users.</i>"
                )
                logger.info("Maintenance mode deactivated by owner")

            else:
                await update.message.reply_html(
                    "<b>❌ Invalid Command</b>\n\n"
                    "<i>Usage:</i> <code>/maintenance [on|off]</code>"
                )

        except Exception as e:
            logger.error(f"Error in maintenance command: {e}")
            await update.message.reply_html(
                "<b>⚠️ Error</b>\n" "<i>Failed to toggle maintenance mode.</i>"
            )

    async def stats_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Display bot usage statistics.
        Usage: /stats [days]
        """
        if not update.message:
            return

        # Check owner authorization
        user = update.effective_user
        if not user or not await is_owner(user.id):
            await update.message.reply_html(
                "<b>⛔ Unauthorized</b>\n"
                "<i>This command is only available to the bot owner.</i>"
            )
            return

        try:
            # Parse days parameter
            days = 7  # default
            if context.args:
                try:
                    days = max(1, min(90, int(context.args[0])))  # Limit to 1-90 days
                except ValueError:
                    await update.message.reply_html(
                        "<b>❌ Invalid Parameter</b>\n\n"
                        "<i>Usage:</i> <code>/stats [days]</code>\n"
                        "<i>Days must be a number between 1 and 90.</i>"
                    )
                    return

            # Check cache validity (cache for 5 minutes)
            now = datetime.now()
            if (
                self._stats_cache is None
                or now > self._cache_expires
                or self._stats_cache.get("period_days") != days
            ):

                # Send "calculating" message for long operations
                calculating_msg = None
                if days > 30:
                    calculating_msg = await update.message.reply_html(
                        "<b>�� Calculating Statistics...</b>\n"
                        "<i>This may take a moment for large datasets.</i>"
                    )

                # Get fresh stats
                stats = await self.db.get_bot_statistics(days)

                if not stats:
                    await update.message.reply_html(
                        "<b>⚠️ Statistics Unavailable</b>\n"
                        "<i>Unable to retrieve bot statistics at this time.</i>"
                    )
                    return

                # Cache the results
                self._stats_cache = stats
                self._cache_expires = now.replace(second=0, microsecond=0).replace(
                    minute=now.minute + 5
                )

                # Delete calculating message if sent
                if calculating_msg:
                    try:
                        await calculating_msg.delete()
                    except Exception:
                        pass
            else:
                stats = self._stats_cache

            # Format statistics message
            users = stats.get("users", {})
            commands = stats.get("commands", {})

            # Top commands
            top_commands = ""
            for i, cmd_stat in enumerate(commands.get("breakdown", [])[:5]):
                top_commands += (
                    f"{i+1}. <code>{cmd_stat['_id']}</code>: {cmd_stat['count']} uses\n"
                )

            if not top_commands:
                top_commands = "<i>No command usage data</i>"

            # Activity rate
            activity_rate = 0
            if users.get("total", 0) > 0:
                activity_rate = (users.get("active", 0) / users.get("total", 1)) * 100

            message = (
                f"<b>📊 Bot Statistics ({days} days)</b>\n\n"
                f"<b>👥 Users</b>\n"
                f"• Total: <code>{users.get('total', 0)}</code>\n"
                f"• Active: <code>{users.get('active', 0)}</code> ({activity_rate:.1f}%)\n"
                f"• New: <code>{users.get('new', 0)}</code>\n"
                f"• Blacklisted: <code>{users.get('blacklisted', 0)}</code>\n\n"
                f"<b>⚡ Commands</b>\n"
                f"• Total Executed: <code>{commands.get('total', 0)}</code>\n"
                f"• Most Popular: <code>{commands.get('most_popular', 'N/A')}</code>\n\n"
                f"<b>🏆 Top Commands</b>\n{top_commands}\n"
                f"<i>Generated: {datetime.now().strftime('%H:%M:%S')}</i>"
            )

            await update.message.reply_html(message)

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_html(
                "<b>⚠️ Error</b>\n" "<i>Failed to retrieve statistics.</i>"
            )

    async def blacklist_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Manage user blacklist.
        Usage:
            /blacklist <user_id> <reason> - Add user to blacklist
            /blacklist info <user_id> - Get blacklist info for user
            /blacklist list - List all blacklisted users
        """
        if not update.message:
            return
        # Check owner authorization
        user = update.effective_user
        if not user or not await is_owner(user.id):
            await update.message.reply_html(
                "<b>⛔ Unauthorized</b>\n"
                "<i>This command is only available to the bot owner.</i>"
            )
            return

        try:
            args = context.args

            if not args:
                await update.message.reply_html(
                    "<b>❌ Missing Parameter</b>\n\n"
                    "<i>Usage:</i> <code>/blacklist &lt;user_id&gt; [reason]</code>"
                )
                return

            # Parse user ID
            try:
                user_id = int(args[0])
            except ValueError:
                await update.message.reply_html(
                    "<b>❌ Invalid User ID</b>\n\n" "<i>User ID must be a number.</i>"
                )
                return

            # Check if trying to blacklist owner
            if await is_owner(user_id):
                await update.message.reply_html(
                    "<b>❌ Cannot Blacklist Owner</b>\n\n"
                    "<i>You cannot blacklist yourself!</i>"
                )
                return

            # Get reason (optional)
            reason = " ".join(args[1:]) if len(args) > 1 else "Admin decision"

            # Check if already blacklisted
            if await self.db.is_blacklisted(user_id):
                blacklist_info = await self.db.get_blacklist_info(user_id)
                blocked_date = "Unknown"
                if blacklist_info and "blocked_at" in blacklist_info:
                    blocked_date = blacklist_info["blocked_at"].strftime("%Y-%m-%d")

                await update.message.reply_html(
                    f"<b>ℹ️ Already Blacklisted</b>\n\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Since:</b> <code>{blocked_date}</code>\n"
                    f"<b>Reason:</b> <i>{blacklist_info.get('reason', 'Unknown') if blacklist_info else 'Unknown'}</i>"
                )
                return

            # Add to blacklist
            blocked_by_user = update.effective_user
            blocked_by_id = str(blocked_by_user.id) if blocked_by_user else None
            success = await self.db.add_to_blacklist(user_id, reason, blocked_by_id)

            if success:
                await update.message.reply_html(
                    f"<b>🚫 User Blacklisted</b>\n\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Reason:</b> <i>{reason}</i>\n"
                    f"<b>Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M')}</code>"
                )
            else:
                await update.message.reply_html(
                    "<b>⚠️ Blacklist Failed</b>\n"
                    "<i>Unable to add user to blacklist.</i>"
                )

        except Exception as e:
            logger.error(f"Error in blacklist command: {e}")
            await update.message.reply_html(
                "<b>⚠️ Error</b>\n" "<i>Failed to process blacklist command.</i>"
            )

    async def whitelist_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Remove user from blacklist.
        Usage: /whitelist <user_id>
        """
        if not update.message:
            return

        # Check owner authorization
        user = update.effective_user
        if not user or not await is_owner(user.id):
            await update.message.reply_html(
                "<b>⛔ Unauthorized</b>\n"
                "<i>This command is only available to the bot owner.</i>"
            )
            return

        try:
            args = context.args

            if not args:
                await update.message.reply_html(
                    "<b>❌ Missing Parameter</b>\n\n"
                    "<i>Usage:</i> <code>/whitelist &lt;user_id&gt;</code>"
                )
                return

            # Parse user ID
            try:
                user_id = int(args[0])
            except ValueError:
                await update.message.reply_html(
                    "<b>❌ Invalid User ID</b>\n\n" "<i>User ID must be a number.</i>"
                )
                return

            # Check if blacklisted
            if not await self.db.is_blacklisted(user_id):
                await update.message.reply_html(
                    f"<b>ℹ️ User Not Blacklisted</b>\n\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<i>This user is not currently blacklisted.</i>"
                )
                return

            # Remove from blacklist
            success = await self.db.remove_from_blacklist(user_id)

            if success:
                await update.message.reply_html(
                    f"<b>✅ User Whitelisted</b>\n\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M')}</code>\n"
                    f"<i>User can now use the bot again.</i>"
                )
            else:
                await update.message.reply_html(
                    "<b>⚠️ Whitelist Failed</b>\n"
                    "<i>Unable to remove user from blacklist.</i>"
                )

        except Exception as e:
            logger.error(f"Error in whitelist command: {e}")
            await update.message.reply_html(
                "<b>⚠️ Error</b>\n" "<i>Failed to process whitelist command.</i>"
            )

    def is_maintenance_mode(self) -> bool:
        """
        Check if bot is in maintenance mode.

        Returns:
            True if in maintenance mode, False otherwise
        """
        return self.maintenance_mode

    async def send_maintenance_message(self, update: Update) -> None:
        """
        Send maintenance mode message to user.
        """
        if not update.message:
            return

        try:
            await update.message.reply_html(
                "<b>🛠️ Maintenance Mode</b>\n\n"
                "<i>The bot is currently undergoing maintenance. Please try again later.</i>\n\n"
                "<b>Expected Duration:</b> <i>A few minutes</i>\n"
                "<b>Status Updates:</b> <i>Check back shortly</i>"
            )
        except TelegramError as e:
            logger.error(f"Failed to send maintenance message: {e}")


def register_owner_commands(
    application: Application, database_service: DatabaseService
) -> OwnerCommands:
    """
    Register owner command handlers with the bot application.

    Args:
        application: Telegram bot application
        database_service: Database service instance

    Returns:
        OwnerCommands instance for maintenance mode checking
    """
    owner_handler = OwnerCommands(database_service)

    from telegram.ext import CommandHandler

    # Register command handlers
    application.add_handler(
        CommandHandler("maintenance", owner_handler.maintenance_command)
    )
    application.add_handler(CommandHandler("stats", owner_handler.stats_command))
    application.add_handler(
        CommandHandler("blacklist", owner_handler.blacklist_command)
    )
    application.add_handler(
        CommandHandler("whitelist", owner_handler.whitelist_command)
    )

    logger.info("Owner command handlers registered")
    return owner_handler

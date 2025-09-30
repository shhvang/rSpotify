"""
Notification service for rSpotify Bot.
Handles startup notifications and critical error reporting to bot owner.
"""

import logging
import traceback
from typing import cast
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError

from ..config import Config
from .auth import get_owner_id

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications to bot owner."""

    def __init__(self, bot: Bot):
        """
        Initialize notification service.

        Args:
            bot: Telegram bot instance
        """
        self.bot = bot
        self.owner_id = get_owner_id()

    async def send_startup_notification(self, version: str = "1.2.0") -> bool:
        """
        Send startup notification to bot owner.

        Args:
            version: Bot version string

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.owner_id:
            logger.error(
                "Cannot send startup notification: OWNER_TELEGRAM_ID not configured"
            )
            return False

        try:
            # Get deployment timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            # Check database connection
            from .database import DatabaseService

            db_service = DatabaseService()
            db_status = await db_service.check_connection()
            db_emoji = "✅" if db_status else "❌"

            message = (
                f"<b>🚀 rSpotify Bot Started</b>\n\n"
                f"<b>Version:</b> <code>{version}</code>\n"
                f"<b>Environment:</b> <code>{Config.ENVIRONMENT}</code>\n"
                f"<b>Deployed:</b> <code>{timestamp}</code>\n"
                f"<b>Database:</b> {db_emoji} {'Connected' if db_status else 'Disconnected'}\n"
                f"<b>Debug Mode:</b> {'✅ Enabled' if Config.DEBUG else '❌ Disabled'}\n\n"
                f"<i>Bot is ready to serve users!</i>"
            )

            await self.bot.send_message(
                chat_id=self.owner_id, text=message, parse_mode="HTML"
            )

            logger.info("Startup notification sent to owner")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send startup notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending startup notification: {e}")
            return False

    async def send_error_report(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send critical error report to bot owner via pastebin.

        Args:
            error: The exception that occurred
            context: Additional context information

        Returns:
            True if error report sent successfully, False otherwise
        """
        if not self.owner_id:
            logger.error("Cannot send error report: OWNER_TELEGRAM_ID not configured")
            return False

        try:
            # Format error report
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            error_type = type(error).__name__
            error_message = str(error)
            stack_trace = traceback.format_exc()

            report_content = f"""rSpotify Bot - Critical Error Report
Timestamp: {timestamp}
Environment: {Config.ENVIRONMENT}
Error Type: {error_type}
Error Message: {error_message}

Stack Trace:
{stack_trace}

Context Information:
{context or "No additional context provided"}

Bot Configuration:
- Environment: {Config.ENVIRONMENT}
- Debug Mode: {Config.DEBUG}
- Log Level: {Config.LOG_LEVEL}
"""

            # Upload to pastebin
            pastebin_url = await self._upload_to_pastebin(report_content)

            if pastebin_url:
                message = (
                    f"<b>🚨 Critical Error Detected</b>\n\n"
                    f"<b>Type:</b> <code>{error_type}</code>\n"
                    f"<b>Time:</b> <code>{timestamp}</code>\n"
                    f"<b>Environment:</b> <code>{Config.ENVIRONMENT}</code>\n\n"
                    f"<b>Message:</b>\n<code>{error_message}</code>\n\n"
                    f"<a href='{pastebin_url}'>📋 View Full Error Report</a>"
                )
            else:
                # Fallback if pastebin fails
                message = (
                    f"<b>🚨 Critical Error Detected</b>\n\n"
                    f"<b>Type:</b> <code>{error_type}</code>\n"
                    f"<b>Time:</b> <code>{timestamp}</code>\n"
                    f"<b>Environment:</b> <code>{Config.ENVIRONMENT}</code>\n\n"
                    f"<b>Message:</b>\n<code>{error_message[:500]}{'...' if len(error_message) > 500 else ''}</code>\n\n"
                    f"<i>⚠️ Failed to upload full report to pastebin</i>"
                )

            await self.bot.send_message(
                chat_id=self.owner_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

            logger.info("Error report sent to owner")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send error report: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending error report: {e}")
            return False

    async def _upload_to_pastebin(self, content: str) -> Optional[str]:
        """
        Upload content to a public pastebin service.

        Args:
            content: Content to upload

        Returns:
            URL of uploaded paste, None if failed
        """
        try:
            # Using dpaste.org as a simple pastebin service
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://dpaste.org/api/v2/",
                    data={
                        "content": content,
                        "syntax": "text",
                        "title": f"rSpotify Bot Error Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    },
                )

                if response.status_code == 201:
                    return cast(Optional[str], response.headers.get("Location"))
                else:
                    logger.error(
                        f"Pastebin upload failed with status {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Failed to upload to pastebin: {e}")
            return None

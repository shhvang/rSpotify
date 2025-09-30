#!/usr/bin/env python3
"""Better Than Very Bot - Find stronger word alternatives"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BETTERTHANVERY_BOT_TOKEN')
WEB_APP_URL = os.getenv('BETTERTHANVERY_WEB_URL', 'https://betterthanvery.netlify.app')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with inline web app button."""
    user = update.effective_user
    
    keyboard = [[
        InlineKeyboardButton(
            text="Open App",
            url=WEB_APP_URL
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"Hi {user.first_name}! 👋\n\n"
        "Replace weak phrases with stronger words.\n"
        "Example: 'very good' → 'excellent'"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup)
    logger.info(f"User {user.id} started Better Than Very Bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    keyboard = [[
        InlineKeyboardButton(text="Open App", url=WEB_APP_URL)
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_text = (
        "Find stronger alternatives for 'very + word' phrases.\n\n"
        "Examples:\n"
        "• very cold → freezing\n"
        "• very important → crucial\n"
        "• very bad → terrible"
    )
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BETTERTHANVERY_BOT_TOKEN not found")
        return
    
    logger.info("Starting Better Than Very Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    logger.info("✅ Better Than Very Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Perfect Circle Bot - Test your circle drawing skills"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('PERFECTCIRCLE_BOT_TOKEN')
WEB_APP_URL = os.getenv('PERFECTCIRCLE_WEB_URL', 'https://perfectcircle.netlify.app')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with inline web app button."""
    user = update.effective_user
    
    keyboard = [[
        InlineKeyboardButton(
            text="Open App",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"Hi {user.first_name}! 👋\n\n"
        "Draw a circle and see how perfect it is.\n"
        "Can you score 100%?"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup)
    logger.info(f"User {user.id} started Perfect Circle Bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    keyboard = [[
        InlineKeyboardButton(text="Open App", web_app=WebAppInfo(url=WEB_APP_URL))
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_text = (
        "Test your circle drawing accuracy!\n\n"
        "Tips:\n"
        "• Draw slowly and steadily\n"
        "• Keep consistent speed\n"
        "• Close the circle smoothly"
    )
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("PERFECTCIRCLE_BOT_TOKEN not found")
        return
    
    logger.info("Starting Perfect Circle Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    logger.info("✅ Perfect Circle Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

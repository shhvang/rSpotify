"""
Flask web service for Spotify OAuth callback handling.
Handles the redirect from Spotify after user authorization.
"""

import os
import sys
import logging
import asyncio
from flask import Flask, request, render_template_string, abort
from datetime import datetime

# Add parent directory to path to import bot modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rspotify_bot.config import Config
from rspotify_bot.services.auth import SpotifyAuthService
from rspotify_bot.services.repository import UserRepository, RepositoryError
from rspotify_bot.services.database import DatabaseService
from rspotify_bot.services.middleware import get_temporary_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY or "default-secret-key-change-me"

# Initialize services
db_service = None
temp_storage = None


def init_services():
    """Initialize database and temporary storage services."""
    global db_service, temp_storage

    try:
        # Initialize database service
        db_service = DatabaseService(Config.MONGODB_URI, Config.MONGODB_DATABASE)
        logger.info("Database service initialized")

        # Get temporary storage instance
        temp_storage = get_temporary_storage()
        logger.info("Temporary storage initialized")

        return True
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return False


# Success page HTML template
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spotify Connected - rSpotify Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            text-align: center;
        }
        .success-icon {
            font-size: 80px;
            margin-bottom: 20px;
        }
        h1 {
            color: #1DB954;
            margin-bottom: 10px;
            font-size: 32px;
        }
        p {
            color: #333;
            font-size: 18px;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        .telegram-link {
            display: inline-block;
            background: #0088cc;
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 16px;
            transition: background 0.3s;
        }
        .telegram-link:hover {
            background: #006699;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✅</div>
        <h1>Success!</h1>
        <p>Your Spotify account has been connected to rSpotify Bot.</p>
        <p>You can now return to Telegram and start using the bot's features.</p>
        <a href="https://t.me/{{ bot_username }}" class="telegram-link">Return to Telegram</a>
    </div>
</body>
</html>
"""

# Error page HTML template
ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Error - rSpotify Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            text-align: center;
        }
        .error-icon {
            font-size: 80px;
            margin-bottom: 20px;
        }
        h1 {
            color: #FF6B6B;
            margin-bottom: 10px;
            font-size: 32px;
        }
        p {
            color: #333;
            font-size: 18px;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        .telegram-link {
            display: inline-block;
            background: #0088cc;
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 16px;
            transition: background 0.3s;
        }
        .telegram-link:hover {
            background: #006699;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">❌</div>
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>
        <a href="https://t.me/{{ bot_username }}" class="telegram-link">Return to Telegram</a>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    """Root endpoint."""
    return "rSpotify Bot OAuth Callback Service", 200


@app.route("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "oauth-callback"}, 200


@app.route("/spotify/callback")
def spotify_callback():
    """
    Handle Spotify OAuth callback.

    Validates state parameter, exchanges authorization code for tokens,
    and stores encrypted tokens in database.
    """
    logger.info("Received Spotify OAuth callback")

    # Get parameters from callback
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    # Check for user denial
    if error:
        logger.warning(f"User denied authorization: {error}")
        return render_template_string(
            ERROR_TEMPLATE,
            title="Authorization Denied",
            message="You denied authorization to access your Spotify account. "
            "If this was a mistake, please try /login again in Telegram.",
            bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
        )

    # Validate required parameters
    if not code or not state:
        logger.error("Missing code or state parameter in callback")
        return render_template_string(
            ERROR_TEMPLATE,
            title="Invalid Request",
            message="Missing required parameters. Please try /login again in Telegram.",
            bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
        ), 400

    try:
        # Validate state parameter and get telegram_id
        state_key = f"oauth_state_{state}"

        # Run async operation in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        telegram_id = loop.run_until_complete(temp_storage.get(state_key))

        if not telegram_id:
            logger.error(f"Invalid or expired state parameter: {state}")
            return render_template_string(
                ERROR_TEMPLATE,
                title="Session Expired",
                message="Your login session has expired. Please try /login again in Telegram.",
                bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
            ), 400

        logger.info(f"Valid state parameter for user {telegram_id}")

        # Exchange authorization code for tokens
        auth_service = SpotifyAuthService()
        tokens = loop.run_until_complete(auth_service.exchange_code_for_tokens(code))

        logger.info(f"Successfully exchanged code for tokens for user {telegram_id}")

        # Store tokens in database
        user_repo = UserRepository(db_service.database)

        # Check if user exists, create if not
        user_exists = loop.run_until_complete(user_repo.user_exists(telegram_id))

        if user_exists:
            # Update existing user
            loop.run_until_complete(
                user_repo.update_spotify_tokens(
                    telegram_id,
                    tokens["access_token"],
                    tokens["refresh_token"],
                    tokens["expires_at"],
                )
            )
            logger.info(f"Updated Spotify tokens for existing user {telegram_id}")
        else:
            # Create new user with tokens
            loop.run_until_complete(
                user_repo.create_user(
                    telegram_id,
                    spotify_tokens={
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "expires_at": tokens["expires_at"],
                    },
                )
            )
            logger.info(f"Created new user {telegram_id} with Spotify tokens")

        # Remove used state parameter
        loop.run_until_complete(temp_storage.delete(state_key))

        # Close event loop
        loop.close()

        # Return success page
        return render_template_string(
            SUCCESS_TEMPLATE,
            bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
        )

    except RepositoryError as e:
        logger.error(f"Database error in callback: {e}")
        return render_template_string(
            ERROR_TEMPLATE,
            title="Database Error",
            message="Failed to save your Spotify connection. Please try /login again.",
            bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
        ), 500

    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return render_template_string(
            ERROR_TEMPLATE,
            title="Error",
            message="An unexpected error occurred. Please try /login again in Telegram.",
            bot_username=os.getenv("BOT_USERNAME", "rspotify_bot"),
        ), 500


if __name__ == "__main__":
    # Initialize services
    if not init_services():
        logger.error("Failed to initialize services, exiting")
        sys.exit(1)

    # Start cleanup task for temporary storage
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(temp_storage.start_cleanup_task())

    # Run Flask app
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    logger.info(f"Starting OAuth callback service on {host}:{port}")

    try:
        app.run(host=host, port=port, debug=Config.DEBUG)
    finally:
        # Cleanup
        loop.run_until_complete(temp_storage.stop_cleanup_task())
        loop.close()

"""
Flask web service for Spotify OAuth callback handling (Spotipie-style).
Stores auth code in MongoDB and redirects to Telegram bot deep link.
Bot retrieves the code and exchanges it for tokens.
"""

import os
import sys
import logging
import asyncio
from flask import Flask, request, redirect

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rspotify_bot.config import Config
from rspotify_bot.services.database import DatabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.FLASK_SECRET_KEY or 'default-secret-key-change-me'

# Initialize services
db_service = None


async def init_services():
    '''Initialize database service.'''
    global db_service

    try:
        db_service = DatabaseService()
        if not await db_service.connect():
            logger.error('Failed to connect to database')
            return False
        logger.info('Database service initialized and connected')
        return True
    except Exception as e:
        logger.error(f'Failed to initialize services: {e}')
        return False


@app.route('/')
def index():
    '''Root endpoint.'''
    return 'rSpotify Bot OAuth Callback Service', 200


@app.route('/health')
def health():
    '''Health check endpoint.'''
    return {'status': 'healthy', 'service': 'oauth-callback'}, 200


@app.route('/spotify/callback')
def spotify_callback():
    '''
    Handle Spotify OAuth callback.
    Stores auth code in MongoDB and redirects to Telegram bot.
    '''
    try:
        # Check for OAuth errors
        error = request.args.get('error')
        if error:
            logger.warning(f'OAuth error: {error}')
            return f'OAuth cancelled: {error}', 400

        # Get authorization code
        auth_code = request.args.get('code')
        if not auth_code:
            logger.error('No authorization code received')
            return 'No authorization code received', 400

        # Get user IP for tracking
        user_ip = request.remote_addr or 'unknown'

        logger.info(f'Received OAuth callback from {user_ip}')

        # Store code in MongoDB
        code_doc = {
            'authCode': auth_code,
            'ip': user_ip,
            'createdAt': asyncio.run(get_current_time())
        }

        # Insert code into database
        result = db_service.database.oauth_codes.insert_one(code_doc)
        code_id = str(result.inserted_id)

        logger.info(f'Stored auth code with ID: {code_id}')

        # Redirect to Telegram bot with code ID
        bot_username = Config.BOT_USERNAME
        telegram_url = f'https://t.me/{bot_username}?start={code_id}'

        logger.info(f'Redirecting to Telegram: {telegram_url}')
        return redirect(telegram_url)

    except Exception as e:
        logger.error(f'Error handling callback: {e}', exc_info=True)
        return 'Internal server error', 500


async def get_current_time():
    '''Helper to get current time asynchronously.'''
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


if __name__ == '__main__':
    # Initialize event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize services
    if not loop.run_until_complete(init_services()):
        logger.error('Failed to initialize services, exiting')
        sys.exit(1)

    # Run Flask app
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    logger.info(f'Starting OAuth callback service on {host}:{port}')

    try:
        app.run(host=host, port=port, debug=Config.DEBUG)
    finally:
        # Cleanup
        if db_service:
            loop.run_until_complete(db_service.disconnect())
        loop.close()

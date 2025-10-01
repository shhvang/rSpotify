"""
aiohttp web service for Spotify OAuth callback handling with automatic SSL via certbot.
Stores auth code in MongoDB and redirects to Telegram bot deep link.
Bot retrieves the code and exchanges it for tokens.

Architecture v2.0: Self-contained SSL automation with certbot integration.
"""

import os
import sys
import ssl
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from aiohttp import web
import certbot.main

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rspotify_bot.config import Config
from rspotify_bot.services.database import DatabaseService
from rspotify_bot.services.middleware import get_temporary_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Global services
db_service: Optional[DatabaseService] = None
temp_storage = None


async def init_services():
    """Initialize database service and temporary storage."""
    global db_service, temp_storage

    try:
        # Initialize database
        db_service = DatabaseService()
        if not await db_service.connect():
            logger.error('Failed to connect to database')
            return False
        logger.info('Database service initialized and connected')

        # Initialize temporary storage
        temp_storage = get_temporary_storage()
        await temp_storage.start_cleanup_task()
        logger.info('Temporary storage initialized')

        return True
    except Exception as e:
        logger.error(f'Failed to initialize services: {e}')
        return False


async def cleanup_services():
    """Cleanup services on shutdown."""
    global db_service, temp_storage

    if temp_storage:
        await temp_storage.stop_cleanup_task()
        logger.info('Temporary storage cleanup stopped')

    if db_service:
        await db_service.disconnect()
        logger.info('Database disconnected')


async def health_check(request: web.Request) -> web.Response:
    """
    Health check endpoint.
    
    Args:
        request: aiohttp request object
        
    Returns:
        JSON response with service status
    """
    db_status = 'connected' if db_service and await db_service.health_check() else 'disconnected'
    
    return web.json_response({
        'status': 'healthy',
        'service': 'oauth-callback',
        'database': db_status,
        'ssl': 'enabled' if request.scheme == 'https' else 'disabled'
    })


async def index(request: web.Request) -> web.Response:
    """
    Root endpoint.
    
    Args:
        request: aiohttp request object
        
    Returns:
        Simple text response
    """
    return web.Response(text='rSpotify Bot OAuth Callback Service (aiohttp + certbot SSL)', status=200)


async def acme_challenge(request: web.Request) -> web.Response:
    """
    Serve ACME challenge for Let's Encrypt validation.
    This endpoint is called by Let's Encrypt during certificate provisioning.
    
    Args:
        request: aiohttp request object
        
    Returns:
        Challenge response file content
    """
    token = request.match_info['token']
    challenge_dir = Path('web_callback/certs/.well-known/acme-challenge')
    challenge_file = challenge_dir / token
    
    try:
        if challenge_file.exists():
            with open(challenge_file, 'r') as f:
                content = f.read()
            logger.info(f'Served ACME challenge: {token}')
            return web.Response(text=content, content_type='text/plain')
        else:
            logger.warning(f'ACME challenge file not found: {token}')
            return web.Response(text='Challenge not found', status=404)
    except Exception as e:
        logger.error(f'Error serving ACME challenge: {e}')
        return web.Response(text='Internal error', status=500)


async def spotify_callback(request: web.Request) -> web.Response:
    """
    Handle Spotify OAuth callback.
    Validates state, stores auth code in MongoDB, and redirects to Telegram bot deep link.
    
    Args:
        request: aiohttp request object
        
    Returns:
        HTTP redirect to Telegram bot or error response
    """
    try:
        # Check for OAuth errors first
        error = request.query.get('error')
        if error:
            error_description = request.query.get('error_description', 'Unknown error')
            logger.warning(f'OAuth error: {error} - {error_description}')
            return web.Response(
                text=f'<html><body><h1>Authorization Cancelled</h1>'
                     f'<p>You cancelled the Spotify authorization: {error}</p>'
                     f'<p>Please return to Telegram and use /login to try again.</p></body></html>',
                content_type='text/html',
                status=400
            )

        # Get authorization code and state
        auth_code = request.query.get('code')
        state = request.query.get('state')

        if not auth_code:
            logger.error('No authorization code received')
            return web.Response(
                text='<html><body><h1>Error</h1><p>No authorization code received.</p></body></html>',
                content_type='text/html',
                status=400
            )

        if not state:
            logger.error('No state parameter received')
            return web.Response(
                text='<html><body><h1>Error</h1><p>No state parameter received.</p></body></html>',
                content_type='text/html',
                status=400
            )

        # Get user IP for logging
        user_ip = request.remote or 'unknown'
        logger.info(f'Received OAuth callback from {user_ip} with state: {state}')

        # Validate state parameter against temporary storage
        state_key = f"oauth_state_{state}"
        telegram_id = await temp_storage.get(state_key)

        if not telegram_id:
            logger.warning(f'Invalid or expired state parameter: {state}')
            return web.Response(
                text='<html><body><h1>Session Expired</h1>'
                     '<p>Your authorization session has expired (5 minute limit).</p>'
                     '<p>Please return to Telegram and use /login to start a new authorization.</p></body></html>',
                content_type='text/html',
                status=400
            )

        # Delete state parameter (one-time use)
        await temp_storage.delete(state_key)
        logger.info(f'State validated for telegram_id: {telegram_id}')

        # Store auth code in MongoDB with TTL (10 minutes)
        code_doc = {
            'telegram_id': telegram_id,
            'auth_code': auth_code,
            'state': state,
            'ip': user_ip,
            'created_at': datetime.now(timezone.utc),
            'expires_at': datetime.now(timezone.utc) + timedelta(minutes=10)
        }

        result = await db_service.database.oauth_codes.insert_one(code_doc)
        code_id = str(result.inserted_id)

        logger.info(f'Stored auth code with ID: {code_id} for telegram_id: {telegram_id}')

        # Redirect to Telegram bot with code ID via deep link
        bot_username = Config.BOT_USERNAME
        if not bot_username:
            logger.error('BOT_USERNAME not configured')
            return web.Response(
                text='<html><body><h1>Configuration Error</h1><p>Bot username not configured.</p></body></html>',
                content_type='text/html',
                status=500
            )

        telegram_url = f'https://t.me/{bot_username}?start={code_id}'
        logger.info(f'Redirecting to Telegram: {telegram_url}')

        # Return redirect with user-friendly message
        return web.Response(
            status=302,
            headers={'Location': telegram_url},
            text=f'<html><body><h1>Authorization Successful!</h1>'
                 f'<p>Redirecting you to Telegram...</p>'
                 f'<p>If you are not redirected automatically, <a href="{telegram_url}">click here</a>.</p></body></html>',
            content_type='text/html'
        )

    except Exception as e:
        logger.error(f'Error handling Spotify callback: {e}', exc_info=True)
        return web.Response(
            text='<html><body><h1>Internal Server Error</h1>'
                 '<p>An error occurred processing your authorization.</p>'
                 '<p>Please return to Telegram and try /login again.</p></body></html>',
            content_type='text/html',
            status=500
        )


async def setup_ssl_certificates():
    """
    Setup SSL certificates using certbot.
    Requests new certificate if not exists, or checks for renewal if exists.
    
    Returns:
        tuple: (cert_path, key_path) or (None, None) if SSL setup fails
    """
    domain = Config.DOMAIN
    email = Config.CERTBOT_EMAIL

    if not domain:
        logger.error('DOMAIN not configured - SSL certificates cannot be provisioned')
        return None, None

    if not email:
        logger.error('CERTBOT_EMAIL not configured - SSL certificates cannot be provisioned')
        return None, None

    # Certificate paths
    cert_dir = Path('web_callback/certs')
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    cert_path = cert_dir / 'live' / domain / 'fullchain.pem'
    key_path = cert_dir / 'live' / domain / 'privkey.pem'

    # Check if certificates already exist
    if cert_path.exists() and key_path.exists():
        logger.info(f'SSL certificates already exist for {domain}')
        
        # Check if renewal is needed (< 30 days remaining)
        try:
            # Run certbot renew in dry-run mode to check
            certbot_args = [
                'renew',
                '--dry-run',
                '--config-dir', str(cert_dir),
                '--work-dir', str(cert_dir / 'work'),
                '--logs-dir', str(cert_dir / 'logs'),
                '--quiet'
            ]
            
            # Note: In production, you'd schedule this to run daily
            logger.info('Certificate renewal check skipped (implement scheduled renewal)')
            
        except Exception as e:
            logger.warning(f'Certificate renewal check failed: {e}')
        
        return str(cert_path), str(key_path)

    # Certificates don't exist - request new ones
    logger.info(f'Requesting new SSL certificate for {domain} from Let\'s Encrypt...')
    logger.info('This requires port 80 to be accessible from the internet for ACME validation')
    
    try:
        # Run certbot to obtain certificate
        certbot_args = [
            'certonly',
            '--standalone',
            '--non-interactive',
            '--agree-tos',
            '--email', email,
            '-d', domain,
            '--config-dir', str(cert_dir),
            '--work-dir', str(cert_dir / 'work'),
            '--logs-dir', str(cert_dir / 'logs'),
            '--http-01-port', '80'
        ]
        
        # Run certbot
        exit_code = certbot.main.main(certbot_args)
        
        if exit_code == 0:
            logger.info(f'✅ SSL certificate obtained successfully for {domain}')
            return str(cert_path), str(key_path)
        else:
            logger.error(f'Certbot exited with code {exit_code}')
            return None, None
            
    except Exception as e:
        logger.error(f'Failed to obtain SSL certificate: {e}', exc_info=True)
        return None, None


def create_app() -> web.Application:
    """
    Create and configure the aiohttp application.
    
    Returns:
        Configured aiohttp Application instance
    """
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', index)
    app.router.add_get('/health', health_check)
    app.router.add_get('/.well-known/acme-challenge/{token}', acme_challenge)
    app.router.add_get('/spotify/callback', spotify_callback)
    
    # Add startup and cleanup handlers
    app.on_startup.append(lambda app: init_services())
    app.on_cleanup.append(lambda app: cleanup_services())
    
    logger.info('aiohttp application created with routes')
    return app


async def run_http_server(app: web.Application, port: int = 80):
    """
    Run HTTP server for ACME challenges.
    
    Args:
        app: aiohttp application
        port: Port to listen on (default: 80)
    """
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'HTTP server started on port {port} for ACME challenges')
    return runner


async def run_https_server(app: web.Application, cert_path: str, key_path: str, port: int = 443):
    """
    Run HTTPS server for OAuth callbacks.
    
    Args:
        app: aiohttp application
        cert_path: Path to SSL certificate
        key_path: Path to SSL private key
        port: Port to listen on (default: 443)
    """
    # Create SSL context
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(cert_path, key_path)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port, ssl_context=ssl_context)
    await site.start()
    logger.info(f'HTTPS server started on port {port} with SSL')
    return runner


async def main():
    """Main entry point for the OAuth callback service."""
    logger.info('Starting rSpotify OAuth Callback Service (aiohttp + certbot)')
    
    # Create application
    app = create_app()
    
    # Initialize services
    if not await init_services():
        logger.error('Failed to initialize services, exiting')
        sys.exit(1)
    
    # Setup SSL certificates
    cert_path, key_path = await setup_ssl_certificates()
    
    runners = []
    
    try:
        if cert_path and key_path:
            # Run HTTPS server on port 443
            https_runner = await run_https_server(app, cert_path, key_path, port=443)
            runners.append(https_runner)
            logger.info('✅ HTTPS server running on port 443')
        else:
            logger.warning('SSL certificates not available - running HTTP only for ACME challenges')
        
        # Always run HTTP server on port 80 for ACME challenges and redirects
        http_runner = await run_http_server(app, port=80)
        runners.append(http_runner)
        logger.info('✅ HTTP server running on port 80')
        
        logger.info('🚀 OAuth callback service is ready!')
        logger.info(f'   HTTPS: https://{Config.DOMAIN}/spotify/callback')
        logger.info(f'   HTTP:  http://{Config.DOMAIN} (ACME challenges)')
        
        # Keep running until interrupted
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info('Received shutdown signal...')
    finally:
        # Cleanup
        for runner in runners:
            await runner.cleanup()
        await cleanup_services()
        logger.info('OAuth callback service stopped gracefully')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Shutdown complete')

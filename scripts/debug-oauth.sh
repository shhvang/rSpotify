#!/bin/bash
# Debug script to test OAuth service manually
# Run this on the server to see the actual error

echo '================================'
echo 'OAuth Service Debug Script'
echo '================================'
echo ''

echo '1. Checking Python executable...'
ls -l /opt/rspotify-bot/venv/bin/python
echo ''

echo '2. Checking Python version...'
/opt/rspotify-bot/venv/bin/python --version
echo ''

echo '3. Checking script file...'
ls -l /opt/rspotify-bot/repo/web_callback/app.py
echo ''

echo '4. Checking working directory...'
ls -ld /opt/rspotify-bot/repo
echo ''

echo '5. Checking .env file...'
ls -l /opt/rspotify-bot/repo/.env
echo ''

echo '6. Testing Python imports...'
/opt/rspotify-bot/venv/bin/python -c 'import sys; print(\"Python Path:\"); [print(p) for p in sys.path]'
echo ''

echo '7. Testing certbot import...'
/opt/rspotify-bot/venv/bin/python -c 'import certbot; print(f\"Certbot version: {certbot.__version__}\")'
echo ''

echo '8. Testing josepy import...'
/opt/rspotify-bot/venv/bin/python -c 'import josepy; print(f\"Josepy version: {josepy.__version__}\"); print(f\"Has ComparableX509: {hasattr(josepy, \"ComparableX509\")}\")'
echo ''

echo '9. Checking supervisor config...'
cat /etc/supervisor/conf.d/rspotify-oauth.conf
echo ''

echo '10. Now attempting to run the OAuth service...'
echo 'Press Ctrl+C to stop after seeing the error'
echo '================================'
cd /opt/rspotify-bot/repo
export PYTHONPATH=/opt/rspotify-bot/repo
/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/web_callback/app.py
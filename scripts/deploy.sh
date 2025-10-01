#!/bin/bash
set -e

echo "🚀 Starting rSpotify Bot deployment..."

# Update system
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3-pip git supervisor libcap2-bin

# Create app user
useradd -m -s /bin/bash rspotify || true

# Create directories
mkdir -p /opt/rspotify-bot/{logs,backups,letsencrypt}

# Fix git ownership issue
git config --global --add safe.directory /opt/rspotify-bot/repo

# Clone/update repository
if [ -d "/opt/rspotify-bot/repo" ]; then
    cd /opt/rspotify-bot/repo
    git pull origin main
else
    git clone https://github.com/shhvang/rSpotify.git /opt/rspotify-bot/repo
    git config --global --add safe.directory /opt/rspotify-bot/repo
fi

chown -R rspotify:rspotify /opt/rspotify-bot

# Remove and recreate virtual environment to fix dependency issues
cd /opt/rspotify-bot/repo
rm -rf /opt/rspotify-bot/venv
python3.11 -m venv /opt/rspotify-bot/venv
source /opt/rspotify-bot/venv/bin/activate
pip install --upgrade pip

# Install dependencies with no cache to ensure fresh versions
pip install --no-cache-dir -r requirements.txt
pip install -e .

# Grant Python capability to bind to privileged ports (80, 443) without root
# The venv python is a symlink, so we need to apply setcap to the real binary
PYTHON_VENV=/opt/rspotify-bot/venv/bin/python3.11
if [ -L "$PYTHON_VENV" ]; then
    PYTHON_BIN=$(readlink -f "$PYTHON_VENV")
else
    PYTHON_BIN="$PYTHON_VENV"
fi

echo "Setting CAP_NET_BIND_SERVICE capability on $PYTHON_BIN"
setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"

# Verify
if getcap "$PYTHON_BIN" | grep -q cap_net_bind_service; then
    echo "✅ Successfully granted CAP_NET_BIND_SERVICE to Python"
else
    echo "❌ Failed to set capabilities"
    exit 1
fi

# Create .env file in repo directory (where the bot loads from)
cat > /opt/rspotify-bot/repo/.env << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
OWNER_TELEGRAM_ID=${OWNER_TELEGRAM_ID}
SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MONGODB_URI=${MONGODB_URI}
MONGODB_DATABASE=rspotify_bot_production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
PASTEBIN_API_KEY=${PASTEBIN_API_KEY}
PASTEBIN_USER_KEY=${PASTEBIN_USER_KEY}
DOMAIN=rspotify.shhvang.space
BOT_USERNAME=${BOT_USERNAME}
CERTBOT_EMAIL=${CERTBOT_EMAIL}
SPOTIFY_REDIRECT_URI=https://rspotify.shhvang.space/spotify/callback
EOF

chown rspotify:rspotify /opt/rspotify-bot/repo/.env
chmod 600 /opt/rspotify-bot/repo/.env

# Setup supervisor for rSpotify bot
cat > /etc/supervisor/conf.d/rspotify-bot.conf << 'EOF'
[program:rspotify-bot]
command=/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/rspotify.py
directory=/opt/rspotify-bot/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/bot_error.log
stdout_logfile=/opt/rspotify-bot/logs/bot_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin"
EOF

# Setup supervisor for aiohttp OAuth callback service (Story 1.4)
# This service handles SSL automatically via certbot - no Nginx needed
# Python has CAP_NET_BIND_SERVICE capability, so rspotify user can bind to ports 80/443
cat > /etc/supervisor/conf.d/rspotify-oauth.conf << 'EOF'
[program:rspotify-oauth]
command=/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/web_callback/app.py
directory=/opt/rspotify-bot/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/oauth_error.log
stdout_logfile=/opt/rspotify-bot/logs/oauth_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin",PYTHONPATH="/opt/rspotify-bot/repo"
EOF

# Setup web app bots if tokens are provided
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    echo "📱 Setting up Better Than Very bot..."
    
    # Add to .env
    cat >> /opt/rspotify-bot/repo/.env << EOF
BETTERTHANVERY_BOT_TOKEN=${BETTERTHANVERY_BOT_TOKEN}
BETTERTHANVERY_WEB_URL=https://shhvang.github.io/betterthanvery
EOF
    
    # Supervisor config
    cat > /etc/supervisor/conf.d/betterthanvery-bot.conf << 'EOF'
[program:betterthanvery-bot]
command=/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/web_apps/betterthanvery/bot.py
directory=/opt/rspotify-bot/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/betterthanvery_error.log
stdout_logfile=/opt/rspotify-bot/logs/betterthanvery_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin"
EOF
fi

if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    echo "🎨 Setting up Perfect Circle bot..."
    
    # Add to .env
    cat >> /opt/rspotify-bot/repo/.env << EOF
PERFECTCIRCLE_BOT_TOKEN=${PERFECTCIRCLE_BOT_TOKEN}
PERFECTCIRCLE_WEB_URL=https://shhvang.github.io/perfect-circle
EOF
    
    # Supervisor config
    cat > /etc/supervisor/conf.d/perfectcircle-bot.conf << 'EOF'
[program:perfectcircle-bot]
command=/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/web_apps/perfectcircle/bot.py
directory=/opt/rspotify-bot/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/perfectcircle_error.log
stdout_logfile=/opt/rspotify-bot/logs/perfectcircle_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin"
EOF
fi

# Reload supervisor
supervisorctl reread
supervisorctl update
supervisorctl restart rspotify-bot
supervisorctl restart rspotify-oauth

# Restart web app bots if configured
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    supervisorctl restart betterthanvery-bot
fi
if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    supervisorctl restart perfectcircle-bot
fi

echo "✅ Deployment complete!"
echo ""
echo "📊 Bot Status:"
supervisorctl status rspotify-bot
supervisorctl status rspotify-oauth
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    supervisorctl status betterthanvery-bot
fi
if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    supervisorctl status perfectcircle-bot
fi

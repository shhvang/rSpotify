#!/bin/bash
set -e

echo "🚀 Starting rSpotify Bot deployment..."

# Update system
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3-pip git supervisor nginx

# Create app user
useradd -m -s /bin/bash rspotify || true

# Create directories
mkdir -p /opt/rspotify-bot/{logs,backups}

# Fix git ownership issue
git config --global --add safe.directory /opt/rspotify-bot/src

# Clone/update repository
if [ -d "/opt/rspotify-bot/src" ]; then
    cd /opt/rspotify-bot/src
    git pull origin main
else
    git clone https://github.com/shhvang/rSpotify.git /opt/rspotify-bot/src
    git config --global --add safe.directory /opt/rspotify-bot/src
fi

chown -R rspotify:rspotify /opt/rspotify-bot

# Setup virtual environment
cd /opt/rspotify-bot
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r src/rspotify-bot/requirements.txt
pip install -e src/rspotify-bot

# Create .env file
cat > /opt/rspotify-bot/.env << EOF
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
DUCKDNS_TOKEN=${DUCKDNS_TOKEN:-placeholder}
DUCKDNS_DOMAIN=${DUCKDNS_DOMAIN:-localhost}
SPOTIFY_REDIRECT_URI=https://${DUCKDNS_DOMAIN:-localhost}/callback
EOF

chown rspotify:rspotify /opt/rspotify-bot/.env
chmod 600 /opt/rspotify-bot/.env

# Setup supervisor
cat > /etc/supervisor/conf.d/rspotify-bot.conf << 'EOF'
[program:rspotify-bot]
command=/opt/rspotify-bot/venv/bin/python -m rspotify_bot.bot
directory=/opt/rspotify-bot
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/bot_error.log
stdout_logfile=/opt/rspotify-bot/logs/bot_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin"
EOF

# Reload supervisor
supervisorctl reread
supervisorctl update
supervisorctl restart rspotify-bot

echo " Deployment complete! Bot is running."
supervisorctl status rspotify-bot

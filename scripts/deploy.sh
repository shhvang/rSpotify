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

# Setup virtual environment
cd /opt/rspotify-bot/repo
python3.11 -m venv /opt/rspotify-bot/venv
source /opt/rspotify-bot/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

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
DUCKDNS_TOKEN=${DUCKDNS_TOKEN:-placeholder}
DUCKDNS_DOMAIN=${DUCKDNS_DOMAIN:-localhost}
SPOTIFY_REDIRECT_URI=https://${DUCKDNS_DOMAIN:-localhost}/callback
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

# Setup supervisor for Flask OAuth callback service (Story 1.4)
cat > /etc/supervisor/conf.d/rspotify-flask.conf << 'EOF'
[program:rspotify-flask]
command=/opt/rspotify-bot/venv/bin/python /opt/rspotify-bot/repo/web_callback/app.py
directory=/opt/rspotify-bot/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=/opt/rspotify-bot/logs/flask_error.log
stdout_logfile=/opt/rspotify-bot/logs/flask_output.log
environment=HOME="/opt/rspotify-bot",PATH="/opt/rspotify-bot/venv/bin"
EOF

# Setup nginx for OAuth callback routing (Story 1.4)
cat > /etc/nginx/sites-available/rspotify << 'EOF'
server {
    listen 80;
    server_name rspotify.shhvang.space;
    
    # OAuth callback endpoint
    location /spotify/callback {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable nginx site
ln -sf /etc/nginx/sites-available/rspotify /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

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
supervisorctl restart rspotify-flask

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
supervisorctl status rspotify-flask
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    supervisorctl status betterthanvery-bot
fi
if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    supervisorctl status perfectcircle-bot
fi

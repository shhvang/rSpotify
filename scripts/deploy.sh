#!/bin/bash
set -e

# ============================================
# PRODUCTION CONFIGURATION
# ============================================
ENVIRONMENT="production"
BRANCH="main"
APP_DIR="/opt/rspotify-bot"
DB_NAME="rspotify"
SUPERVISOR_BOT_NAME="rspotify-bot"
SUPERVISOR_OAUTH_NAME="rspotify-oauth"
DOMAIN="rspotify.shhvang.space"
OAUTH_HTTP_PORT="6969"
OAUTH_HTTPS_PORT="6970"
# ============================================

echo "🚀 Starting rSpotify Bot deployment..."
echo "Environment: ${ENVIRONMENT}"
echo "Branch: ${BRANCH}"
echo "App Directory: ${APP_DIR}"
echo "Database: ${DB_NAME}"
echo "Domain: ${DOMAIN}"
echo "OAuth Ports: HTTP ${OAUTH_HTTP_PORT}, HTTPS ${OAUTH_HTTPS_PORT}"

echo ""
echo "⬆️ Updating packages and installing dependencies..."
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3-pip git supervisor libcap2-bin

# Ensure application user exists
useradd -m -s /bin/bash rspotify || true

# Create directories required for deployment
mkdir -p ${APP_DIR}/{logs,backups,letsencrypt,repo}

# Fix git ownership warnings for repeated deployments
git config --global --add safe.directory ${APP_DIR}/repo || true

# Clone or update repository to provide deployment scripts
if [ -d "${APP_DIR}/repo/.git" ]; then
    cd ${APP_DIR}/repo
    echo "📥 Fetching latest code..."
    git fetch --tags origin ${BRANCH}
    echo "🧼 Resetting repository to match remote ${BRANCH}"
    git reset --hard origin/${BRANCH}
    git clean -fd
else
    rm -rf ${APP_DIR}/repo
    git clone -b ${BRANCH} https://github.com/shhvang/rSpotify.git ${APP_DIR}/repo
    cd ${APP_DIR}/repo
    git checkout ${BRANCH}
    git config --global --add safe.directory ${APP_DIR}/repo || true
fi

# Ensure correct ownership
chown -R rspotify:rspotify ${APP_DIR}

echo ""
echo "🔍 Checking OAuth domain and SSL setup..."
SETUP_SCRIPT="${APP_DIR}/repo/scripts/setup-oauth-domain.sh"
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    echo "⚠️  SSL certificates not found for ${DOMAIN}"
    echo "🚀 Running OAuth domain setup script..."
    if [ -f "${SETUP_SCRIPT}" ]; then
        bash "${SETUP_SCRIPT}"
    else
        echo "❌ Error: setup-oauth-domain.sh not found at ${SETUP_SCRIPT}!"
        echo "Please ensure the repository contains the script before deploying."
        exit 1
    fi
else
    echo "✅ OAuth domain setup already complete (SSL certificates found)"
fi

# Setup virtual environment
cd ${APP_DIR}/repo
python3.11 -m venv ${APP_DIR}/venv
source ${APP_DIR}/venv/bin/activate
pip install --upgrade pip
pip install --upgrade -r requirements.txt
pip install --upgrade -e .

# Grant Python capability to bind to privileged ports (80, 443) without root
PYTHON_VENV=${APP_DIR}/venv/bin/python3.11
if [ -L "$PYTHON_VENV" ]; then
    PYTHON_BIN=$(readlink -f "$PYTHON_VENV")
else
    PYTHON_BIN="$PYTHON_VENV"
fi

echo "Setting CAP_NET_BIND_SERVICE capability on $PYTHON_BIN"
setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"

# Verify capability assignment
if getcap "$PYTHON_BIN" | grep -q cap_net_bind_service; then
    echo "✅ Successfully granted CAP_NET_BIND_SERVICE to Python"
else
    echo "❌ Failed to set capabilities"
    exit 1
fi

# Create .env file in repo directory (where the bot loads from)
cat > ${APP_DIR}/repo/.env << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
OWNER_TELEGRAM_ID=${OWNER_TELEGRAM_ID}
SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MONGODB_URI=${MONGODB_URI}
MONGODB_DATABASE=${DB_NAME}
ENVIRONMENT=${ENVIRONMENT}
DEBUG=false
LOG_LEVEL=INFO
RS_BOT_PID_FILE=/tmp/rspotify-bot-production.pid
PASTEBIN_API_KEY=${PASTEBIN_API_KEY}
PASTEBIN_USER_KEY=${PASTEBIN_USER_KEY}
DOMAIN=${DOMAIN}
BOT_USERNAME=${BOT_USERNAME}
CERTBOT_EMAIL=${CERTBOT_EMAIL}
SPOTIFY_REDIRECT_URI=https://${DOMAIN}/spotify/callback
OAUTH_HTTP_PORT=${OAUTH_HTTP_PORT}
OAUTH_HTTPS_PORT=${OAUTH_HTTPS_PORT}
EOF

chown rspotify:rspotify ${APP_DIR}/repo/.env
chmod 600 ${APP_DIR}/repo/.env

# Setup supervisor for rSpotify bot
cat > /etc/supervisor/conf.d/${SUPERVISOR_BOT_NAME}.conf << EOF
[program:${SUPERVISOR_BOT_NAME}]
command=${APP_DIR}/venv/bin/python ${APP_DIR}/repo/rspotify.py
directory=${APP_DIR}/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=${APP_DIR}/logs/bot_error.log
stdout_logfile=${APP_DIR}/logs/bot_output.log
environment=HOME="${APP_DIR}",PATH="${APP_DIR}/venv/bin"
EOF

# Setup supervisor for aiohttp OAuth callback service (Story 1.4)
cat > /etc/supervisor/conf.d/${SUPERVISOR_OAUTH_NAME}.conf << EOF
[program:${SUPERVISOR_OAUTH_NAME}]
command=${APP_DIR}/venv/bin/python ${APP_DIR}/repo/web_callback/app.py
directory=${APP_DIR}/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=${APP_DIR}/logs/oauth_error.log
stdout_logfile=${APP_DIR}/logs/oauth_output.log
environment=HOME="${APP_DIR}",PATH="${APP_DIR}/venv/bin"
EOF
# Setup web app bots if tokens are provided
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    echo "📱 Setting up Better Than Very bot..."
    
    # Add to .env
    cat >> ${APP_DIR}/repo/.env << EOF
BETTERTHANVERY_BOT_TOKEN=${BETTERTHANVERY_BOT_TOKEN}
BETTERTHANVERY_WEB_URL=https://shhvang.github.io/betterthanvery
EOF
    
    # Supervisor config
    cat > /etc/supervisor/conf.d/betterthanvery-bot.conf << EOF
[program:betterthanvery-bot]
command=${APP_DIR}/venv/bin/python ${APP_DIR}/repo/web_apps/betterthanvery/bot.py
directory=${APP_DIR}/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=${APP_DIR}/logs/betterthanvery_error.log
stdout_logfile=${APP_DIR}/logs/betterthanvery_output.log
environment=HOME="${APP_DIR}",PATH="${APP_DIR}/venv/bin"
EOF
fi

if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    echo "🎨 Setting up Perfect Circle bot..."
    
    # Add to .env
    cat >> ${APP_DIR}/repo/.env << EOF
PERFECTCIRCLE_BOT_TOKEN=${PERFECTCIRCLE_BOT_TOKEN}
PERFECTCIRCLE_WEB_URL=https://shhvang.github.io/perfect-circle
EOF
    
    # Supervisor config
    cat > /etc/supervisor/conf.d/perfectcircle-bot.conf << EOF
[program:perfectcircle-bot]
command=${APP_DIR}/venv/bin/python ${APP_DIR}/repo/web_apps/perfectcircle/bot.py
directory=${APP_DIR}/repo
user=rspotify
autostart=true
autorestart=true
stderr_logfile=${APP_DIR}/logs/perfectcircle_error.log
stdout_logfile=${APP_DIR}/logs/perfectcircle_output.log
environment=HOME="${APP_DIR}",PATH="${APP_DIR}/venv/bin"
EOF
fi


# Reload supervisor and restart services
supervisorctl reread
supervisorctl update
supervisorctl restart ${SUPERVISOR_BOT_NAME}
supervisorctl restart ${SUPERVISOR_OAUTH_NAME}

if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    supervisorctl restart betterthanvery-bot
fi
if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    supervisorctl restart perfectcircle-bot
fi

echo "✅ Deployment complete!"
echo ""
echo "📊 Bot Status:"
supervisorctl status ${SUPERVISOR_BOT_NAME}
supervisorctl status ${SUPERVISOR_OAUTH_NAME}
if [ ! -z "${BETTERTHANVERY_BOT_TOKEN}" ]; then
    supervisorctl status betterthanvery-bot
fi
if [ ! -z "${PERFECTCIRCLE_BOT_TOKEN}" ]; then
    supervisorctl status perfectcircle-bot
fi

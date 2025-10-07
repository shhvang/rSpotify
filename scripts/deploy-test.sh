#!/bin/bash
set -e

# ============================================
# TEST DEPLOYMENT CONFIGURATION
# ============================================
ENVIRONMENT="test"
BRANCH="develop"
APP_DIR="/opt/rspotify-bot-test"
DB_NAME="rspotify_test"
SUPERVISOR_BOT_NAME="rspotify-bot-test"
SUPERVISOR_OAUTH_NAME="rspotify-oauth-test"
DOMAIN="${PRODUCTION_HOST}"  # Set via GitHub secrets PRODUCTION_HOST_TEST
OAUTH_HTTP_PORT="8080"  # Different from production (80)
OAUTH_HTTPS_PORT="8443"  # Different from production (443)
# ============================================

echo "🧪 Starting rSpotify Bot TEST environment deployment..."
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

# Ensure application user exists (shared with production)
useradd -m -s /bin/bash rspotify || true

# Create TEST environment directories
mkdir -p ${APP_DIR}/{logs,backups,letsencrypt,repo}

# Fix git ownership issue for repeated deployments
git config --global --add safe.directory ${APP_DIR}/repo || true

# Clone or update repository so auxiliary scripts are available
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
echo "🔍 Checking OAuth domain and SSL setup for TEST environment..."
SETUP_SCRIPT="${APP_DIR}/repo/scripts/setup-oauth-domain.sh"
if [ -n "${DOMAIN}" ]; then
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
        echo "✅ OAuth domain setup already complete for ${DOMAIN} (SSL certificates found)"
    fi
else
    echo "⚠️  DOMAIN not set, skipping OAuth setup check"
fi

# Setup virtual environment for TEST
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

# Create .env file for TEST environment
cat > ${APP_DIR}/repo/.env << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
OWNER_TELEGRAM_ID=${OWNER_TELEGRAM_ID}
SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MONGODB_URI=${MONGODB_URI}
MONGODB_DATABASE=${DB_NAME}
ENVIRONMENT=${ENVIRONMENT}
DEBUG=true
LOG_LEVEL=DEBUG
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

# Setup supervisor for TEST rSpotify bot
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

# Setup supervisor for TEST aiohttp OAuth callback service
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

# Reload supervisor and restart services
supervisorctl reread
supervisorctl update
supervisorctl restart ${SUPERVISOR_BOT_NAME}
supervisorctl restart ${SUPERVISOR_OAUTH_NAME}

echo "✅ TEST environment deployment complete!"
echo ""
echo "📊 TEST Bot Status:"
supervisorctl status ${SUPERVISOR_BOT_NAME}
supervisorctl status ${SUPERVISOR_OAUTH_NAME}

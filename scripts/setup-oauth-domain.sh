#!/bin/bash
# Automated OAuth Domain Setup Script for rSpotify
# Run this on a fresh VPS to set up DNS, Nginx, and SSL for OAuth

set -e  # Exit on any error

echo "🚀 Starting OAuth domain setup for rspotify.shhvang.space..."

# Get VPS IP automatically
VPS_IP=$(hostname -I | awk '{print $1}')
DOMAIN="rspotify.shhvang.space"
ROOT_DOMAIN="shhvang.space"

echo "📍 Detected VPS IP: $VPS_IP"
echo "🌐 Setting up domain: $DOMAIN"

# ===== Step 1: Install and Configure DNS Server =====
echo ""
echo "📦 Step 1: Installing BIND DNS server..."
apt update -qq
DEBIAN_FRONTEND=noninteractive apt install -y bind9 bind9utils bind9-doc

echo "⚙️  Configuring DNS zone for $ROOT_DOMAIN..."
cat > /etc/bind/named.conf.local << EOF
zone "$ROOT_DOMAIN" {
    type master;
    file "/etc/bind/zones/db.$ROOT_DOMAIN";
};
EOF

mkdir -p /etc/bind/zones

cat > /etc/bind/zones/db.$ROOT_DOMAIN << EOF
\$TTL    604800
@       IN      SOA     rspotify.$ROOT_DOMAIN. admin.$ROOT_DOMAIN. (
                              1         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL
;
@       IN      NS      rspotify.$ROOT_DOMAIN.
rspotify IN     A       $VPS_IP
EOF

# Validate DNS config
named-checkconf
named-checkzone $ROOT_DOMAIN /etc/bind/zones/db.$ROOT_DOMAIN

# Start and enable BIND
systemctl restart bind9
systemctl enable bind9

# Configure firewall for DNS
ufw allow 53/tcp
ufw allow 53/udp

echo "✅ DNS server configured!"
dig @localhost $DOMAIN +short

# ===== Step 2: Install and Configure Nginx =====
echo ""
echo "📦 Step 2: Setting up Nginx..."
DEBIAN_FRONTEND=noninteractive apt install -y nginx

cat > /etc/nginx/sites-available/rspotify-oauth << 'NGINXEOF'
server {
    listen 80;
    server_name rspotify.shhvang.space;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /spotify/callback {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/rspotify-oauth /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
systemctl enable nginx

ufw allow 80/tcp
ufw allow 443/tcp

echo "✅ Nginx configured!"

# ===== Step 3: Install Certbot =====
echo ""
echo "📦 Step 3: Installing Certbot for SSL..."
DEBIAN_FRONTEND=noninteractive apt install -y certbot python3-certbot-nginx

echo ""
echo "🎉 Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Wait for DNS propagation (5-60 minutes)"
echo "   Test with: dig $DOMAIN @8.8.8.8 +short"
echo ""
echo "2️⃣  Once DNS resolves, run SSL certificate setup:"
echo "   certbot --nginx -d $DOMAIN"
echo ""
echo "3️⃣  Deploy Flask OAuth service:"
echo "   cd /opt/rspotify-bot/repo"
echo "   git pull origin feature/story-1.4-spotify-oauth-authentication-flow"
echo "   ./scripts/deploy.sh"
echo ""
echo "4️⃣  Update Spotify Developer App redirect URI:"
echo "   https://$DOMAIN/spotify/callback"
echo ""
echo "5️⃣  Test OAuth flow:"
echo "   Send /login to your Telegram bot"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ DNS Server: Running on port 53"
echo "✅ Nginx: Running on port 80"
echo "✅ Firewall: Ports 22, 53, 80, 443 open"
echo ""
echo "📊 DNS Status:"
dig @localhost $DOMAIN +short
echo ""
echo "💡 Save this script for reuse on future VPS migrations!"
